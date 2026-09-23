import pytest

pytestmark = pytest.mark.asyncio

SHORT_PAYLOAD = {
    "category": "hr",
    "difficulty": "medium",
    "language": "English",
    "durationMinutes": 5,
}


async def _register_and_create(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    return (await client.post("/interviews", json=SHORT_PAYLOAD)).json()


async def test_exit_requires_auth(client):
    resp = await client.post("/interviews/000000000000000000000000/exit")
    assert resp.status_code == 401


async def test_exit_before_start_fails(client, user_payload):
    interview = await _register_and_create(client, user_payload)
    resp = await client.post(f"/interviews/{interview['id']}/exit")
    assert resp.status_code == 400


async def test_exit_marks_interview_abandoned(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    resp = await client.post(f"/interviews/{interview['id']}/exit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "abandoned"
    assert body["questionNumber"] == 0

    fetched = (await client.get(f"/interviews/{interview['id']}")).json()
    assert fetched["status"] == "abandoned"
    assert fetched["pendingQuestion"] is None


async def test_exit_twice_fails(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")
    await client.post(f"/interviews/{interview['id']}/exit")

    resp = await client.post(f"/interviews/{interview['id']}/exit")
    assert resp.status_code == 400


async def test_exit_after_completion_fails(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)  # maxQuestions = 4
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    for i in range(4):
        fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
        if i < 3:
            fake_ai_client.queue_question(question=f"Q{i+2}?", topic="Career Goals", difficulty=3)
        await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "ok"})

    resp = await client.post(f"/interviews/{interview['id']}/exit")
    assert resp.status_code == 400


async def test_exit_preserves_transcript_so_far(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question(question="Q1?", topic="Teamwork", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?", topic="Career Goals", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "first answer"})

    await client.post(f"/interviews/{interview['id']}/exit")

    turns = (await client.get(f"/interviews/{interview['id']}/turns")).json()
    assert len(turns) == 1
    assert turns[0]["answer"] == "first answer"


async def test_started_at_exposed_for_timer(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    assert (await client.get(f"/interviews/{interview['id']}")).json()["startedAt"] is None

    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")

    fetched = (await client.get(f"/interviews/{interview['id']}")).json()
    assert fetched["startedAt"] is not None
