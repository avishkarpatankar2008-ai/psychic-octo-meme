import pytest

pytestmark = pytest.mark.asyncio


async def test_register_creates_user_and_sets_cookie(client, user_payload):
    resp = await client.post("/auth/register", json=user_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == user_payload["email"]
    assert "passwordHash" not in body
    assert "elevora_session" in resp.cookies


async def test_register_duplicate_email_returns_409(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    resp = await client.post("/auth/register", json=user_payload)
    assert resp.status_code == 409


async def test_register_rejects_short_password(client, user_payload):
    user_payload["password"] = "short"
    resp = await client.post("/auth/register", json=user_payload)
    assert resp.status_code == 422


async def test_login_with_correct_credentials(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    resp = await client.post(
        "/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert resp.status_code == 200
    assert "elevora_session" in resp.cookies


async def test_login_with_wrong_password_returns_401(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    resp = await client.post(
        "/auth/login", json={"email": user_payload["email"], "password": "wrongpassword"}
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user_when_authenticated(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    resp = await client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == user_payload["email"]


async def test_logout_clears_session(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    await client.post("/auth/logout")
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
