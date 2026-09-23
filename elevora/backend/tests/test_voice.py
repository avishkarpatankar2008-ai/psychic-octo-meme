import pytest

pytestmark = pytest.mark.asyncio

SHORT_PAYLOAD = {
    "category": "hr",
    "difficulty": "medium",
    "language": "English",
    "durationMinutes": 5,
}


async def _register_start(client, fake_ai_client, user_payload, opening_question="Q1?"):
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()
    fake_ai_client.queue_question(question=opening_question, topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")
    return interview


# ---- question audio (TTS) -------------------------------------------------


async def test_question_audio_requires_auth(client):
    resp = await client.get("/interviews/000000000000000000000000/question-audio")
    assert resp.status_code == 401


async def test_question_audio_requires_active_question(client, fake_ai_client, user_payload):
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()
    # still a draft — never started
    resp = await client.get(f"/interviews/{interview['id']}/question-audio")
    assert resp.status_code == 400


async def test_question_audio_returns_audio_bytes(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload, "Tell me about yourself.")
    fake_ai_client.queue_audio(b"FAKE_MP3_BYTES")

    resp = await client.get(f"/interviews/{interview['id']}/question-audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"FAKE_MP3_BYTES"
    assert fake_ai_client.speech_calls[0]["text"] == "Tell me about yourself."


async def test_question_audio_surfaces_ai_service_error(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload)
    # no audio queued -> FakeAIClient raises AssertionError, not AIServiceError,
    # so this should bubble as a 500 rather than a handled 502 — confirms we're
    # not accidentally swallowing unexpected errors as if they were AI failures.
    with pytest.raises(AssertionError):
        await client.get(f"/interviews/{interview['id']}/question-audio")


# ---- audio answers (STT) ---------------------------------------------------


async def test_answer_audio_requires_auth(client):
    resp = await client.post(
        "/interviews/000000000000000000000000/answer/audio",
        files={"audio_file": ("a.webm", b"data", "audio/webm")},
    )
    assert resp.status_code == 401


async def test_answer_audio_transcribes_and_advances(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload, "Describe a project.")

    fake_ai_client.queue_transcript("I led a team of four to ship a new feature.")
    fake_ai_client.queue_analysis(quality=4, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Career Goals", difficulty=4)

    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("answer.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "I led a team of four to ship a new feature."
    assert body["pendingQuestion"]["question"] == "Q2?"
    assert body["questionNumber"] == 1

    assert fake_ai_client.transcribe_calls[0]["filename"] == "answer.webm"
    assert fake_ai_client.transcribe_calls[0]["audio_bytes"] == b"fake-audio-bytes"

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    assert turns[0]["answer"] == "I led a team of four to ship a new feature."


async def test_answer_audio_rejects_unsupported_content_type(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload)
    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("a.txt", b"not audio", "text/plain")},
    )
    assert resp.status_code == 415


async def test_answer_audio_rejects_empty_file(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload)
    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("a.webm", b"", "audio/webm")},
    )
    assert resp.status_code == 400


async def test_answer_audio_rejects_oversized_file(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload)
    oversized = b"0" * (15 * 1024 * 1024 + 1)
    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("a.webm", oversized, "audio/webm")},
    )
    assert resp.status_code == 413


async def test_answer_audio_rejects_silent_transcript(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload)
    fake_ai_client.queue_transcript("   ")

    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("a.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert resp.status_code == 422


async def test_answer_audio_before_start_fails(client, fake_ai_client, user_payload):
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()
    fake_ai_client.queue_transcript("Some answer")

    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("a.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert resp.status_code == 400


# ---- Phase 7: real audio -> stored speech metrics -------------------------


def _make_real_audio_with_pause() -> bytes:
    """A real webm clip: 2s tone, 1s silence, 2s tone. Same helper pattern
    as test_speech_analytics.py, kept local here so this file doesn't need
    a cross-test-file import."""
    from pydub import AudioSegment
    from pydub.generators import Sine
    import io

    clip = Sine(440).to_audio_segment(duration=2000)
    clip += AudioSegment.silent(duration=1000)
    clip += Sine(440).to_audio_segment(duration=2000)
    buf = io.BytesIO()
    clip.export(buf, format="webm")
    return buf.getvalue()


async def test_answer_audio_computes_and_stores_real_speech_metrics(
    client, fake_ai_client, user_payload
):
    """End-to-end: upload real audio with a known pause -> transcribe (faked)
    -> confirm the ACTUAL ffmpeg-decoded metrics (not a mock) show up on the
    stored turn, fetched back through the public API."""
    interview = await _register_start(client, fake_ai_client, user_payload)
    raw = _make_real_audio_with_pause()

    fake_ai_client.queue_transcript("Um, I think the answer is fairly straightforward.")
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Career Goals", difficulty=3)

    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("answer.webm", raw, "audio/webm")},
    )
    assert resp.status_code == 200

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    metrics = turns[0]["speechMetrics"]
    assert metrics is not None
    assert metrics["durationSeconds"] == pytest.approx(5.0, abs=0.1)
    assert metrics["pauseCount"] == 1
    assert metrics["longestPauseSeconds"] == pytest.approx(1.0, abs=0.1)
    assert metrics["fillerCount"] == 1  # "um"


async def test_answer_audio_degrades_gracefully_on_undecodable_audio(
    client, fake_ai_client, user_payload
):
    """Transcription can succeed (OpenAI is more tolerant of odd containers)
    even when our local ffmpeg decode can't handle the bytes. The turn
    should still save, just with speechMetrics: null."""
    interview = await _register_start(client, fake_ai_client, user_payload)

    fake_ai_client.queue_transcript("This transcribed fine somehow.")
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.queue_question()

    resp = await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("answer.webm", b"not actually valid audio bytes", "audio/webm")},
    )
    assert resp.status_code == 200

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    assert turns[0]["speechMetrics"] is None


async def test_text_answers_never_have_speech_metrics(client, fake_ai_client, user_payload):
    interview = await _register_start(client, fake_ai_client, user_payload)
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.queue_question()

    await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "typed answer"})

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    assert turns[0]["speechMetrics"] is None
