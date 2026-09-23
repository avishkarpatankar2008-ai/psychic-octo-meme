import pytest

pytestmark = pytest.mark.asyncio

SHORT_PAYLOAD = {
    "category": "hr",
    "difficulty": "medium",
    "language": "English",
    "durationMinutes": 5,  # -> maxQuestions = 4, see _compute_max_questions
}


async def _register_and_create(client, user_payload, payload=None):
    await client.post("/auth/register", json=user_payload)
    resp = await client.post("/interviews", json=payload or SHORT_PAYLOAD)
    return resp.json()


# ---- start_interview -------------------------------------------------


async def test_start_requires_auth(client, fake_ai_client):
    resp = await client.post("/interviews/000000000000000000000000/start")
    assert resp.status_code == 401


async def test_start_returns_first_question(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Tell me about yourself.", topic="Teamwork", difficulty=3)

    resp = await client.post(f"/interviews/{interview['id']}/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["questionNumber"] == 0
    assert body["maxQuestions"] == 4
    assert body["pendingQuestion"]["question"] == "Tell me about yourself."
    assert body["pendingQuestion"]["isFollowUp"] is False


async def test_cannot_start_interview_twice(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")

    resp = await client.post(f"/interviews/{interview['id']}/start")
    assert resp.status_code == 400


async def test_cannot_answer_before_starting(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "Hi"})
    assert resp.status_code == 400


# ---- submit_answer: baseline advancement ------------------------------


async def test_answer_advances_to_next_baseline_question(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Career Goals", difficulty=3, isFollowUp=False)

    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "My answer."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["questionNumber"] == 1
    assert body["status"] == "in_progress"
    assert body["pendingQuestion"]["question"] == "Q2?"
    assert body["pendingQuestion"]["isFollowUp"] is False

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    assert len(turns) == 1
    assert turns[0]["question"] == "Q1?"
    assert turns[0]["answer"] == "My answer."
    assert turns[0]["sequence"] == 1


# ---- dynamic follow-ups -------------------------------------------------


async def test_follow_up_triggered_when_analysis_requests_it(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Describe a project.", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    fake_ai_client.queue_analysis(
        quality=3, followUpNeeded=True, missingEvidence="no metric given for the improvement"
    )
    fake_ai_client.queue_question(
        question="How did you measure that improvement?",
        topic="Teamwork",
        difficulty=3,
        isFollowUp=True,
        targetClaim="improved team velocity",
    )

    resp = await client.post(
        f"/interviews/{interview['id']}/answer", json={"answer": "We improved velocity a lot."}
    )
    body = resp.json()
    assert body["pendingQuestion"]["isFollowUp"] is True
    assert body["pendingQuestion"]["topic"] == "Teamwork"

    # the analysis prompt should have been asked to justify probing this specific answer
    assert "improved velocity a lot" in fake_ai_client.analysis_calls[0]["user"]


async def test_follow_up_not_chained_twice_on_same_topic(client, fake_ai_client, user_payload):
    """Phase 2 caps follow-up depth at 1 per topic — a follow-up answer that
    itself looks like it needs probing should advance to a new topic instead
    of chaining indefinitely (that's Phase 5 territory)."""
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    # First answer triggers a follow-up.
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=True, missingEvidence="detail missing")
    fake_ai_client.queue_question(
        question="Follow-up on Q1?", topic="Teamwork", difficulty=3, isFollowUp=True
    )
    await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "answer 1"})

    # Second answer (to the follow-up) also flags followUpNeeded=True, but
    # since we're already answering a follow-up, the engine must advance
    # to a new baseline topic instead of chaining another follow-up.
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=True, missingEvidence="still vague")
    fake_ai_client.queue_question(
        question="New topic question?", topic="Career Goals", difficulty=3, isFollowUp=False
    )
    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "answer 2"})
    body = resp.json()
    assert body["pendingQuestion"]["isFollowUp"] is False
    assert body["pendingQuestion"]["topic"] == "Career Goals"


# ---- adaptive difficulty ------------------------------------------------


async def test_difficulty_increases_on_strong_answer(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    start_body = (await client.post(f"/interviews/{interview['id']}/start")).json()
    assert start_body["difficultyLevel"] == 3  # medium baseline

    fake_ai_client.queue_analysis(quality=5, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Career Goals", difficulty=4)

    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "Great answer."})
    assert resp.json()["difficultyLevel"] == 4


async def test_difficulty_decreases_on_weak_answer_and_clamps_at_floor(
    client, fake_ai_client, user_payload
):
    interview = await _register_and_create(client, user_payload, {**SHORT_PAYLOAD, "difficulty": "easy"})
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=2)
    start_body = (await client.post(f"/interviews/{interview['id']}/start")).json()
    assert start_body["difficultyLevel"] == 2  # easy baseline

    fake_ai_client.queue_analysis(quality=1, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Career Goals", difficulty=1)
    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "I don't know."})
    assert resp.json()["difficultyLevel"] == 1

    # already at the floor — another weak answer must not go below 1
    fake_ai_client.queue_analysis(quality=1, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q3?", topic="Work Ethic", difficulty=1)
    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "Still unsure."})
    assert resp.json()["difficultyLevel"] == 1


# ---- repeated-question prevention ---------------------------------------


async def test_colliding_question_triggers_one_retry(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    opening = "Tell me about a time you resolved a conflict with a teammate."
    fake_ai_client.queue_question(question=opening, topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.question_calls.clear()  # only count calls made during this answer round
    # First candidate is a near-exact repeat of the opening question -> should trigger a retry.
    fake_ai_client.queue_question(
        question="Tell me about a time you resolved a conflict with a teammate!",
        topic="Conflict Resolution",
        difficulty=3,
    )
    fake_ai_client.queue_question(
        question="Describe how you handle disagreements with a manager.",
        topic="Conflict Resolution",
        difficulty=3,
    )

    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "Some answer."})
    body = resp.json()
    assert body["pendingQuestion"]["question"] == "Describe how you handle disagreements with a manager."
    # two generate_question calls happened for this single answer: the collision + the retry
    assert len(fake_ai_client.question_calls) == 2


# ---- completion -----------------------------------------------------------


async def test_interview_completes_at_max_questions(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)  # maxQuestions = 4
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    for i in range(2, 5):  # answer Q1, Q2, Q3 -> each advances to a new question
        fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
        fake_ai_client.queue_question(question=f"Q{i}?", topic="Career Goals", difficulty=3)
        resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "ok"})
        assert resp.json()["status"] == "in_progress"

    # 4th answer reaches maxQuestions=4 -> completes, no further question generated
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "final answer"})
    body = resp.json()
    assert body["status"] == "completed"
    assert body["questionNumber"] == 4
    assert body["pendingQuestion"] is None

    interview_after = (await client.get(f"/interviews/{interview['id']}")).json()
    assert interview_after["status"] == "completed"

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    assert len(turns) == 4
    assert [t["sequence"] for t in turns] == [1, 2, 3, 4]


async def test_cannot_answer_a_completed_interview(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    for i in range(3):
        fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
        fake_ai_client.queue_question(question=f"Next question {i}?", topic="Career Goals", difficulty=3)
        await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "ok"})

    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "final"})

    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "one more?"})
    assert resp.status_code == 400


# ---- ownership / isolation -----------------------------------------------


async def test_turns_are_isolated_per_owner(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    other_user = {"name": "Bob", "email": "bob@example.com", "password": "anothersecret123"}
    await client.post("/auth/register", json=other_user)

    resp = await client.get(f"/interviews/{interview['id']}/turns")
    assert resp.status_code == 404
