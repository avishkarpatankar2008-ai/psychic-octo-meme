import pytest

pytestmark = pytest.mark.asyncio

INTERVIEW_PAYLOAD = {
    "category": "software-engineer",
    "role": "Backend Engineer",
    "experienceLevel": "entry-level",
    "difficulty": "medium",
    "language": "English",
    "durationMinutes": 20,
}


async def _register(client, user_payload):
    resp = await client.post("/auth/register", json=user_payload)
    assert resp.status_code == 201


async def test_create_interview_requires_auth(client):
    resp = await client.post("/interviews", json=INTERVIEW_PAYLOAD)
    assert resp.status_code == 401


async def test_create_and_fetch_interview(client, user_payload):
    await _register(client, user_payload)

    create_resp = await client.post("/interviews", json=INTERVIEW_PAYLOAD)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["status"] == "draft"
    assert created["category"] == "software-engineer"

    get_resp = await client.get(f"/interviews/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]


async def test_list_interviews_only_returns_own_interviews(client, user_payload):
    await _register(client, user_payload)
    await client.post("/interviews", json=INTERVIEW_PAYLOAD)
    await client.post("/interviews", json=INTERVIEW_PAYLOAD)

    list_resp = await client.get("/interviews")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2

    # A second, different user should see none of the first user's interviews.
    other_user = {"name": "Bob", "email": "bob@example.com", "password": "anothersecret123"}
    await _register(client, other_user)
    list_resp_other = await client.get("/interviews")
    assert list_resp_other.json() == []


async def test_interview_persists_after_refresh(client, user_payload):
    """Mirrors the Phase 1 'DONE' criterion: create -> refresh -> still exists."""
    await _register(client, user_payload)
    create_resp = await client.post("/interviews", json=INTERVIEW_PAYLOAD)
    interview_id = create_resp.json()["id"]

    # Simulate a page refresh: fetch /auth/me then the interview again.
    assert (await client.get("/auth/me")).status_code == 200
    get_resp = await client.get(f"/interviews/{interview_id}")
    assert get_resp.status_code == 200


async def test_delete_interview(client, user_payload):
    await _register(client, user_payload)
    created = (await client.post("/interviews", json=INTERVIEW_PAYLOAD)).json()

    delete_resp = await client.delete(f"/interviews/{created['id']}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/interviews/{created['id']}")
    assert get_resp.status_code == 404


async def test_get_nonexistent_interview_returns_404(client, user_payload):
    await _register(client, user_payload)
    resp = await client.get("/interviews/000000000000000000000000")
    assert resp.status_code == 404


async def test_invalid_interview_id_returns_404_not_500(client, user_payload):
    await _register(client, user_payload)
    resp = await client.get("/interviews/not-a-valid-object-id")
    assert resp.status_code == 404
