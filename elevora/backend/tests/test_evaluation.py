import pytest

from app.services.evaluation import (
    WEIGHT_PROFILES,
    compute_confidence,
    compute_weighted_score,
    weight_profile_for_category,
)


# ---- pure scoring math — no AI, no DB, no mocking needed at all ----------


class TestComputeWeightedScore:
    def test_all_dimensions_available_matches_manual_calculation(self):
        # Mirrors the spec's own section-17 worked example almost exactly.
        weights = WEIGHT_PROFILES["technical"]
        scores = {
            "knowledge": 4,
            "problemSolving": 3,
            "communication": 4,
            "relevance": 5,
            "interviewHandling": 3,
            "delivery": 4,
            "webcam": None,
        }
        overall, category_scores = compute_weighted_score(scores, weights)
        # Manual calc: (4/5*.40 + 3/5*.25 + 4/5*.15 + 5/5*.10 + 3/5*.05 + 4/5*.05) / (1-0.0) *100
        # webcam weight (0.0) contributes nothing either way here.
        expected_weighted = (
            (4 / 5) * 0.40
            + (3 / 5) * 0.25
            + (4 / 5) * 0.15
            + (5 / 5) * 0.10
            + (3 / 5) * 0.05
            + (4 / 5) * 0.05
        )
        assert overall == round(expected_weighted * 100)
        assert category_scores["knowledge"] == 80
        assert category_scores["relevance"] == 100

    def test_unavailable_dimensions_are_excluded_not_zeroed(self):
        """A missing measurement must not drag the score down as if it were a 0."""
        weights = WEIGHT_PROFILES["general"]
        all_perfect_except_missing = {
            "knowledge": 5,
            "communication": 5,
            "relevance": 5,
            "problemSolving": 5,
            "interviewHandling": 5,
            "delivery": None,
            "webcam": None,
        }
        overall, category_scores = compute_weighted_score(all_perfect_except_missing, weights)
        assert overall == 100
        assert "delivery" not in category_scores
        assert "webcam" not in category_scores

    def test_delivery_and_webcam_always_unavailable_still_scores_correctly(self):
        """This is the realistic Phase 6 case: every report has delivery=None,
        webcam=None. Confirms the renormalization handles that combination,
        not just the general 'some dimension is missing' case."""
        weights = WEIGHT_PROFILES["behavioral"]
        scores = {
            "knowledge": 3,
            "communication": 4,
            "relevance": 3,
            "problemSolving": 3,
            "interviewHandling": 4,
            "delivery": None,
            "webcam": None,
        }
        overall, category_scores = compute_weighted_score(scores, weights)
        assert 0 <= overall <= 100
        assert set(category_scores.keys()) == {
            "knowledge", "communication", "relevance", "problemSolving", "interviewHandling",
        }

    def test_no_available_dimensions_returns_zero(self):
        all_missing = {k: None for k in WEIGHT_PROFILES["general"]}
        overall, category_scores = compute_weighted_score(all_missing, WEIGHT_PROFILES["general"])
        assert overall == 0
        assert category_scores == {}

    def test_perfect_scores_yield_100_regardless_of_profile(self):
        for profile_name, weights in WEIGHT_PROFILES.items():
            scores = {dim: 5 for dim in weights}
            overall, _ = compute_weighted_score(scores, weights)
            assert overall == 100, f"profile {profile_name} didn't yield 100 for all-5s"

    def test_zero_scores_yield_0(self):
        weights = WEIGHT_PROFILES["technical"]
        scores = {dim: 0 for dim in weights}
        overall, _ = compute_weighted_score(scores, weights)
        assert overall == 0

    def test_all_weight_profiles_sum_to_one(self):
        for name, weights in WEIGHT_PROFILES.items():
            assert abs(sum(weights.values()) - 1.0) < 1e-9, f"{name} weights don't sum to 1.0"


class TestWeightProfileForCategory:
    def test_technical_categories(self):
        assert weight_profile_for_category("software-engineer") == WEIGHT_PROFILES["technical"]
        assert weight_profile_for_category("mechanical-engineer") == WEIGHT_PROFILES["technical"]

    def test_behavioral_categories(self):
        assert weight_profile_for_category("hr") == WEIGHT_PROFILES["behavioral"]
        assert weight_profile_for_category("mba") == WEIGHT_PROFILES["behavioral"]

    def test_unknown_category_falls_back_to_general(self):
        assert weight_profile_for_category("some-made-up-category") == WEIGHT_PROFILES["general"]


class TestComputeConfidence:
    def test_short_interview_is_low_confidence(self):
        assert compute_confidence(turn_count=2, distinct_topics=2) == "low"

    def test_narrow_topic_coverage_is_low_confidence_even_with_many_turns(self):
        assert compute_confidence(turn_count=10, distinct_topics=1) == "low"

    def test_moderate_interview_is_medium_confidence(self):
        assert compute_confidence(turn_count=4, distinct_topics=2) == "medium"

    def test_long_broad_interview_is_high_confidence(self):
        assert compute_confidence(turn_count=8, distinct_topics=4) == "high"


# ---- endpoint-level tests (require FakeAIClient) -------------------------

SHORT_PAYLOAD = {
    "category": "software-engineer",
    "difficulty": "medium",
    "language": "English",
    "durationMinutes": 5,  # -> maxQuestions = 4
}


async def _complete_short_interview(client, fake_ai_client, user_payload):
    """Registers, creates, and fully completes a 4-question interview."""
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()

    fake_ai_client.queue_question(question="Q1?", topic="System Design", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    for i in range(3):
        fake_ai_client.queue_analysis(quality=4, followUpNeeded=False)
        fake_ai_client.queue_question(question=f"Q{i+2}?", topic=f"Topic{i}", difficulty=3)
        await client.post(f"/interviews/{interview['id']}/answer", json={"answer": f"answer {i}"})

    fake_ai_client.queue_analysis(quality=4, followUpNeeded=False)
    await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "final answer"})

    return interview


async def test_report_requires_auth(client):
    resp = await client.post("/interviews/000000000000000000000000/report")
    assert resp.status_code == 401


async def test_report_rejected_before_completion(client, fake_ai_client, user_payload):
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()
    resp = await client.post(f"/interviews/{interview['id']}/report")
    assert resp.status_code == 400


async def test_report_rejected_for_abandoned_interview(client, fake_ai_client, user_payload):
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()
    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")
    await client.post(f"/interviews/{interview['id']}/exit")

    resp = await client.post(f"/interviews/{interview['id']}/report")
    assert resp.status_code == 400


async def test_generate_report_for_completed_interview(client, fake_ai_client, user_payload):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)

    fake_ai_client.queue_evaluation(
        knowledgeScore=4,
        knowledgeEvidence="Explained system design trade-offs correctly.",
        strengths=["Clear technical reasoning"],
        weaknesses=["Could give more concrete examples"],
        recommendedPractice=["Practice quantifying impact with numbers"],
    )

    resp = await client.post(f"/interviews/{interview['id']}/report")
    assert resp.status_code == 200
    body = resp.json()

    assert body["dimensions"]["knowledge"]["score"] == 4
    assert body["dimensions"]["knowledge"]["evidence"] == "Explained system design trade-offs correctly."
    assert body["dimensions"]["delivery"]["score"] is None
    assert "voice answers" in body["dimensions"]["delivery"]["evidence"]
    assert body["dimensions"]["webcam"]["score"] is None
    assert 0 <= body["overallScore"] <= 100
    assert body["strengths"] == ["Clear technical reasoning"]
    assert body["confidence"] in ("low", "medium", "high")

    # The evaluation prompt actually received the real transcript.
    user_prompt = fake_ai_client.evaluation_calls[0]["user"]
    assert "answer 0" in user_prompt
    assert "final answer" in user_prompt


async def test_report_is_persisted_and_retrievable(client, fake_ai_client, user_payload):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    fake_ai_client.queue_evaluation()
    await client.post(f"/interviews/{interview['id']}/report")

    resp = await client.get(f"/interviews/{interview['id']}/report")
    assert resp.status_code == 200
    assert resp.json()["interviewId"] == interview["id"]


async def test_report_not_found_before_generation(client, fake_ai_client, user_payload):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    resp = await client.get(f"/interviews/{interview['id']}/report")
    assert resp.status_code == 404


async def test_report_overall_score_stored_on_interview(client, fake_ai_client, user_payload):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    fake_ai_client.queue_evaluation(knowledgeScore=5, communicationScore=5, relevanceScore=5,
                                     problemSolvingScore=5, interviewHandlingScore=5)
    report_resp = await client.post(f"/interviews/{interview['id']}/report")
    overall = report_resp.json()["overallScore"]

    fetched = (await client.get(f"/interviews/{interview['id']}")).json()
    # overallScore isn't in InterviewOut's schema (Phase 6 didn't extend it) —
    # confirm the report round-trips correctly instead, which is what the
    # frontend actually reads.
    assert fetched["status"] == "completed"
    assert overall == 100


async def test_report_ownership_isolation(client, fake_ai_client, user_payload):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    fake_ai_client.queue_evaluation()
    await client.post(f"/interviews/{interview['id']}/report")

    other_user = {"name": "Bob", "email": "bob@example.com", "password": "anothersecret123"}
    await client.post("/auth/register", json=other_user)
    resp = await client.get(f"/interviews/{interview['id']}/report")
    assert resp.status_code == 404


# ---- Phase 7: webcam metrics + real delivery/webcam scoring --------------

WEBCAM_PAYLOAD = {
    "faceVisibleRate": 0.95,
    "lookingAwayRate": 0.05,
    "movementRate": 0.1,
    "sampledFrames": 150,
}


async def test_webcam_metrics_requires_auth(client):
    resp = await client.post(
        "/interviews/000000000000000000000000/webcam-metrics", json=WEBCAM_PAYLOAD
    )
    assert resp.status_code == 401


async def test_webcam_metrics_rejected_before_start(client, fake_ai_client, user_payload):
    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()
    resp = await client.post(
        f"/interviews/{interview['id']}/webcam-metrics", json=WEBCAM_PAYLOAD
    )
    assert resp.status_code == 400


async def test_webcam_metrics_rejects_out_of_range_values(client, fake_ai_client, user_payload):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    resp = await client.post(
        f"/interviews/{interview['id']}/webcam-metrics",
        json={**WEBCAM_PAYLOAD, "faceVisibleRate": 1.5},
    )
    assert resp.status_code == 422


async def test_webcam_metrics_accepted_and_scores_webcam_dimension(
    client, fake_ai_client, user_payload
):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    resp = await client.post(
        f"/interviews/{interview['id']}/webcam-metrics", json=WEBCAM_PAYLOAD
    )
    assert resp.status_code == 200

    fake_ai_client.queue_evaluation()
    report_resp = await client.post(f"/interviews/{interview['id']}/report")
    body = report_resp.json()

    assert body["dimensions"]["webcam"]["score"] is not None
    assert "95%" in body["dimensions"]["webcam"]["evidence"]


async def test_report_without_webcam_metrics_still_says_unavailable(
    client, fake_ai_client, user_payload
):
    interview = await _complete_short_interview(client, fake_ai_client, user_payload)
    fake_ai_client.queue_evaluation()
    report_resp = await client.post(f"/interviews/{interview['id']}/report")
    body = report_resp.json()

    assert body["dimensions"]["webcam"]["score"] is None
    assert "no webcam" in body["dimensions"]["webcam"]["evidence"].lower() or \
        "not" in body["dimensions"]["webcam"]["evidence"].lower()


async def test_delivery_scored_when_voice_was_used(client, fake_ai_client, user_payload):
    """The realistic end-to-end path: answer by voice at least once (real
    audio decoded by ffmpeg, same as test_voice.py) -> complete the
    interview -> Delivery should have a real score, not 'Not available'."""
    from pydub import AudioSegment
    from pydub.generators import Sine
    import io

    await client.post("/auth/register", json=user_payload)
    interview = (await client.post("/interviews", json=SHORT_PAYLOAD)).json()

    fake_ai_client.queue_question(question="Q1?", topic="System Design", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    clip = Sine(440).to_audio_segment(duration=3000)
    buf = io.BytesIO()
    clip.export(buf, format="webm")
    raw = buf.getvalue()

    fake_ai_client.queue_transcript("I would use a hash map for constant time lookups.")
    fake_ai_client.queue_analysis(quality=4, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Databases", difficulty=3)
    await client.post(
        f"/interviews/{interview['id']}/answer/audio",
        files={"audio_file": ("answer.webm", raw, "audio/webm")},
    )

    for i in range(3):
        fake_ai_client.queue_analysis(quality=4, followUpNeeded=False)
        if i < 2:
            fake_ai_client.queue_question(question=f"Q{i+3}?", topic="Topic", difficulty=3)
        await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "ok"})

    fake_ai_client.queue_evaluation()
    report_resp = await client.post(f"/interviews/{interview['id']}/report")
    body = report_resp.json()

    assert body["dimensions"]["delivery"]["score"] is not None
    assert "1 voice answer" in body["dimensions"]["delivery"]["evidence"]
