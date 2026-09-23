import io

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from app.services.speech_analytics import (
    SpeechAnalyticsError,
    compute_speech_metrics,
    count_fillers,
    count_repeated_words,
    detect_pauses,
    get_audio_duration_seconds,
    word_count,
)


def make_audio_bytes(segments_ms: list[tuple[str, int]], fmt: str = "wav") -> bytes:
    """Builds a real audio clip from a list of ('tone'|'silence', duration_ms)
    segments and exports it to real bytes in the given format."""
    clip = AudioSegment.silent(duration=0)
    for kind, duration in segments_ms:
        if kind == "tone":
            clip += Sine(440).to_audio_segment(duration=duration)
        else:
            clip += AudioSegment.silent(duration=duration)
    buf = io.BytesIO()
    clip.export(buf, format=fmt)
    return buf.getvalue()


# ---- text-only metrics (pure functions, no audio) ------------------------


def test_word_count():
    assert word_count("This is a test answer.") == 5
    assert word_count("") == 0
    assert word_count("one") == 1


def test_count_fillers_single_word():
    count, rate = count_fillers("Um, I think, uh, this is basically the answer.")
    assert count == 3  # um, uh, basically
    assert rate == pytest.approx(3 / 9, abs=0.01)


def test_count_fillers_multi_word_phrase():
    count, _ = count_fillers("It was, you know, a difficult problem to solve.")
    assert count == 1  # "you know"


def test_count_fillers_does_not_match_substrings():
    # "basically" shouldn't match inside "basically" twice or bleed into other words
    count, _ = count_fillers("The soul of the matter is complex.")  # contains "so" nowhere as a word
    assert count == 0


def test_count_fillers_empty_text_has_zero_rate():
    count, rate = count_fillers("")
    assert count == 0
    assert rate == 0.0


def test_count_repeated_words():
    assert count_repeated_words("I I think the the answer is clear") == 2
    assert count_repeated_words("This is a perfectly normal sentence") == 0
    assert count_repeated_words("") == 0


def test_count_repeated_words_case_insensitive():
    assert count_repeated_words("The The cat sat") == 1


# ---- audio-based metrics (real generated audio, real ffmpeg decode) ------


def test_get_audio_duration_matches_real_clip():
    raw = make_audio_bytes([("tone", 3000)])
    duration = get_audio_duration_seconds(raw, format_hint="wav")
    assert duration == pytest.approx(3.0, abs=0.05)


def test_get_audio_duration_rejects_garbage():
    with pytest.raises(SpeechAnalyticsError):
        get_audio_duration_seconds(b"this is not audio data at all", format_hint="wav")


def test_detect_pauses_finds_known_silence_gap():
    # 2s tone, 1.5s silence, 2s tone -> exactly one pause of ~1.5s
    raw = make_audio_bytes([("tone", 2000), ("silence", 1500), ("tone", 2000)], fmt="wav")
    pause_count, avg_pause, longest_pause = detect_pauses(raw, format_hint="wav")
    assert pause_count == 1
    assert avg_pause == pytest.approx(1.5, abs=0.05)
    assert longest_pause == pytest.approx(1.5, abs=0.05)


def test_detect_pauses_finds_multiple_gaps():
    raw = make_audio_bytes(
        [("tone", 1000), ("silence", 700), ("tone", 1000), ("silence", 900), ("tone", 1000)],
        fmt="wav",
    )
    pause_count, avg_pause, longest_pause = detect_pauses(raw, format_hint="wav")
    assert pause_count == 2
    assert longest_pause == pytest.approx(0.9, abs=0.05)
    assert avg_pause == pytest.approx((0.7 + 0.9) / 2, abs=0.05)


def test_detect_pauses_ignores_gaps_shorter_than_threshold():
    # 300ms silence is below the 500ms MIN_PAUSE_MS threshold — shouldn't count
    raw = make_audio_bytes([("tone", 1000), ("silence", 300), ("tone", 1000)], fmt="wav")
    pause_count, _, _ = detect_pauses(raw, format_hint="wav")
    assert pause_count == 0


def test_detect_pauses_continuous_speech_has_no_pauses():
    raw = make_audio_bytes([("tone", 3000)], fmt="wav")
    pause_count, avg_pause, longest_pause = detect_pauses(raw, format_hint="wav")
    assert pause_count == 0
    assert avg_pause == 0.0
    assert longest_pause == 0.0


def test_compute_speech_metrics_real_webm_roundtrip():
    """The realistic end-to-end case: a webm/opus clip (what MediaRecorder
    actually produces in Chrome) with a real pause, plus a transcript with
    known filler words."""
    raw = make_audio_bytes([("tone", 2000), ("silence", 1000), ("tone", 2000)], fmt="webm")
    transcript = "Um, I think the answer is, you know, fairly straightforward."

    metrics = compute_speech_metrics(raw, transcript, format_hint="webm")

    assert metrics.durationSeconds == pytest.approx(5.0, abs=0.1)
    assert metrics.pauseCount == 1
    assert metrics.longestPauseSeconds == pytest.approx(1.0, abs=0.1)
    assert metrics.fillerCount == 2  # "um" and "you know"
    assert metrics.wordCount == word_count(transcript)
    assert metrics.wordsPerMinute > 0


def test_compute_speech_metrics_zero_words_has_zero_wpm_and_filler_rate():
    raw = make_audio_bytes([("tone", 2000)], fmt="wav")
    metrics = compute_speech_metrics(raw, "", format_hint="wav")
    assert metrics.wordCount == 0
    assert metrics.wordsPerMinute == 0.0
    assert metrics.fillerRate == 0.0
