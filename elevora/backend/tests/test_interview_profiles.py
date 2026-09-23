import pytest

from app.services.interview_profiles import DEFAULT_PROFILES, seed_default_profiles

pytestmark = pytest.mark.asyncio

USER_A = {"name": "Ada Lovelace", "email": "ada@example.com", "password": "supersecret123"}
USER_B = {"name": "Bob Builder", "email": "bob@example.com", "password": "anothersecret123"}

CUSTOM_PROFILE_PAYLOAD = {
    "name": "My Full Stack Interview",
    "description": "React, Node.js, and MongoDB, adaptive difficulty.",
    "category": "full-stack",
    "subjects": ["React", "Node.js", "MongoDB"],
    "questionTypes": ["technical", "scenario", "behavioral"],
    "interviewerStyle": "professional",
    "difficulty": "adaptive",
    "maxQuestions": 10,
    "followUpEnabled": True,
    "adaptiveDifficulty": True,
    "resumeGrounding": True,
    "jdGrounding": True,
}


async def _register(client, payload):
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201


# ---- Seeding -----------------------------------------------------------


async def test_seed_default_profiles_creates_all_system_profiles(test_db):
    inserted = await seed_default_profiles(test_db)
    assert inserted == len(DEFAULT_PROFILES)

    count = await test_db.interview_profiles.count_documents({"isSystem": True})
    assert count == len(DEFAULT_PROFILES)


async def test_seed_default_profiles_is_idempotent(test_db):
    first = await seed_default_profiles(test_db)
    second = await seed_default_profiles(test_db)

    assert first == len(DEFAULT_PROFILES)
    assert second == 0  # nothing new inserted the second time

    count = await test_db.interview_profiles.count_documents({"isSystem": True})
    assert count == len(DEFAULT_PROFILES)  # still no duplicates


async def test_seeded_profiles_include_practical_roles(test_db):
    await seed_default_profiles(test_db)
    names = {doc["name"] async for doc in test_db.interview_profiles.find({"isSystem": True})}
    assert {
        "Software Engineer",
        "Frontend Developer",
        "Backend Developer",
        "Data Analyst",
        "HR / Behavioral",
        "System Design",
    }.issubset(names)


# ---- CRUD: create --------------------------------------------------------


async def test_create_custom_profile_requires_auth(client):
    resp = await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)
    assert resp.status_code == 401


async def test_create_custom_profile(client, test_db):
    await _register(client, USER_A)
    resp = await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Full Stack Interview"
    assert body["subjects"] == ["React", "Node.js", "MongoDB"]
    assert body["isSystem"] is False
    assert body["isActive"] is True
    assert body["createdBy"] is not None


async def test_create_custom_profile_rejects_empty_subjects(client):
    await _register(client, USER_A)
    payload = {**CUSTOM_PROFILE_PAYLOAD, "subjects": []}
    resp = await client.post("/interview-profiles", json=payload)
    assert resp.status_code == 422


async def test_duplicate_named_custom_profiles_are_both_allowed(client):
    """Unlike system profiles, nothing stops a user from creating two custom
    profiles that happen to share a name — no uniqueness constraint is
    specified for user-owned profiles."""
    await _register(client, USER_A)
    first = await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)
    second = await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


# ---- CRUD: list / get -----------------------------------------------------


async def test_list_profiles_includes_system_and_own_custom_only(client, test_db):
    await seed_default_profiles(test_db)
    await _register(client, USER_A)
    await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)

    resp = await client.get("/interview-profiles")
    assert resp.status_code == 200
    body = resp.json()
    names = {p["name"] for p in body}
    assert "Software Engineer" in names  # system profile visible
    assert "My Full Stack Interview" in names  # own custom profile visible
    assert all(p["isActive"] for p in body)

    # A second user shouldn't see user A's custom profile.
    await _register(client, USER_B)
    resp_b = await client.get("/interview-profiles")
    names_b = {p["name"] for p in resp_b.json()}
    assert "Software Engineer" in names_b
    assert "My Full Stack Interview" not in names_b


async def test_get_profile_by_id(client):
    await _register(client, USER_A)
    created = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    resp = await client.get(f"/interview-profiles/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_another_users_profile_returns_404(client):
    await _register(client, USER_A)
    created = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    await _register(client, USER_B)
    resp = await client.get(f"/interview-profiles/{created['id']}")
    assert resp.status_code == 404


async def test_get_nonexistent_profile_returns_404(client):
    await _register(client, USER_A)
    resp = await client.get("/interview-profiles/000000000000000000000000")
    assert resp.status_code == 404


async def test_get_invalid_profile_id_returns_404_not_500(client):
    await _register(client, USER_A)
    resp = await client.get("/interview-profiles/not-a-valid-id")
    assert resp.status_code == 404


# ---- CRUD: update / ownership --------------------------------------------


async def test_owner_can_update_own_custom_profile(client):
    await _register(client, USER_A)
    created = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    resp = await client.patch(
        f"/interview-profiles/{created['id']}", json={"maxQuestions": 12, "name": "Updated name"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["maxQuestions"] == 12
    assert body["name"] == "Updated name"
    assert body["subjects"] == ["React", "Node.js", "MongoDB"]  # untouched fields survive


async def test_non_owner_cannot_update_others_custom_profile(client):
    await _register(client, USER_A)
    created = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    await _register(client, USER_B)
    resp = await client.patch(f"/interview-profiles/{created['id']}", json={"maxQuestions": 5})
    assert resp.status_code == 404  # not visible to user B at all


async def test_cannot_update_system_profile(client, test_db):
    await seed_default_profiles(test_db)
    await _register(client, USER_A)

    system_doc = await test_db.interview_profiles.find_one({"isSystem": True})
    resp = await client.patch(
        f"/interview-profiles/{str(system_doc['_id'])}", json={"maxQuestions": 5}
    )
    assert resp.status_code == 403


# ---- CRUD: delete / ownership --------------------------------------------


async def test_owner_can_delete_own_custom_profile(client):
    await _register(client, USER_A)
    created = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    resp = await client.delete(f"/interview-profiles/{created['id']}")
    assert resp.status_code == 204

    # Soft-deleted: no longer visible in the list or by id.
    list_resp = await client.get("/interview-profiles")
    assert created["id"] not in {p["id"] for p in list_resp.json()}
    get_resp = await client.get(f"/interview-profiles/{created['id']}")
    assert get_resp.status_code == 404


async def test_non_owner_cannot_delete_others_custom_profile(client):
    await _register(client, USER_A)
    created = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    await _register(client, USER_B)
    resp = await client.delete(f"/interview-profiles/{created['id']}")
    assert resp.status_code == 404


async def test_cannot_delete_system_profile(client, test_db):
    await seed_default_profiles(test_db)
    await _register(client, USER_A)

    system_doc = await test_db.interview_profiles.find_one({"isSystem": True})
    resp = await client.delete(f"/interview-profiles/{str(system_doc['_id'])}")
    assert resp.status_code == 403

    still_there = await test_db.interview_profiles.find_one({"_id": system_doc["_id"]})
    assert still_there is not None
    assert still_there["isActive"] is True


# ---- Profile-based interview creation ------------------------------------


async def test_create_interview_with_profile_id(client, test_db):
    await _register(client, USER_A)
    profile = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    resp = await client.post(
        "/interviews",
        json={
            "profileId": profile["id"],
            "difficulty": "medium",
            "language": "English",
            "durationMinutes": 20,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["profileId"] == profile["id"]
    # category is backfilled from the profile for backward-compat display/report-weighting.
    assert body["category"] == "full-stack"


async def test_create_interview_without_category_or_profile_fails(client):
    await _register(client, USER_A)
    resp = await client.post(
        "/interviews",
        json={"difficulty": "medium", "language": "English", "durationMinutes": 20},
    )
    assert resp.status_code == 422


async def test_create_interview_with_nonexistent_profile_id_returns_404(client):
    await _register(client, USER_A)
    resp = await client.post(
        "/interviews",
        json={
            "profileId": "000000000000000000000000",
            "difficulty": "medium",
            "language": "English",
            "durationMinutes": 20,
        },
    )
    assert resp.status_code == 404


async def test_create_interview_with_another_users_profile_id_returns_404(client):
    await _register(client, USER_A)
    profile = (await client.post("/interview-profiles", json=CUSTOM_PROFILE_PAYLOAD)).json()

    await _register(client, USER_B)
    resp = await client.post(
        "/interviews",
        json={
            "profileId": profile["id"],
            "difficulty": "medium",
            "language": "English",
            "durationMinutes": 20,
        },
    )
    assert resp.status_code == 404


async def test_create_interview_with_category_only_still_works(client):
    """Phase 1-7 flow, untouched."""
    await _register(client, USER_A)
    resp = await client.post(
        "/interviews",
        json={
            "category": "software-engineer",
            "difficulty": "medium",
            "language": "English",
            "durationMinutes": 20,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["profileId"] is None


# ---- Interview engine actually uses the profile's configuration ----------


async def test_engine_uses_profile_subjects_and_max_questions(client, fake_ai_client):
    await _register(client, USER_A)
    profile_payload = {**CUSTOM_PROFILE_PAYLOAD, "maxQuestions": 3, "subjects": ["Kubernetes"]}
    profile = (await client.post("/interview-profiles", json=profile_payload)).json()

    interview = (
        await client.post(
            "/interviews",
            json={
                "profileId": profile["id"],
                "difficulty": "medium",
                "language": "English",
                "durationMinutes": 60,  # would normally give a much higher maxQuestions
            },
        )
    ).json()

    fake_ai_client.queue_question(question="Explain a Kubernetes concept.", topic="Kubernetes", difficulty=3)
    resp = await client.post(f"/interviews/{interview['id']}/start")
    assert resp.status_code == 200
    body = resp.json()
    # The profile's maxQuestions (3) wins over the duration heuristic (60min -> 20).
    assert body["maxQuestions"] == 3
    assert body["pendingQuestion"]["topic"] == "Kubernetes"

    # The prompt sent to the AI client should reference the profile's own subject.
    system_prompt = fake_ai_client.question_calls[0]["system"]
    assert "Kubernetes" in system_prompt


async def test_engine_respects_follow_up_disabled(client, fake_ai_client):
    await _register(client, USER_A)
    profile_payload = {**CUSTOM_PROFILE_PAYLOAD, "followUpEnabled": False, "maxQuestions": 5}
    profile = (await client.post("/interview-profiles", json=profile_payload)).json()
    interview = (
        await client.post(
            "/interviews",
            json={
                "profileId": profile["id"],
                "difficulty": "medium",
                "language": "English",
                "durationMinutes": 20,
            },
        )
    ).json()

    fake_ai_client.queue_question(question="Q1", topic="React", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    # Even though the AI analysis says a follow-up is needed, the profile
    # forbids it — the engine must move straight to the next baseline topic.
    fake_ai_client.queue_analysis(quality=3, followUpNeeded=True)
    fake_ai_client.queue_question(question="Q2", topic="Node.js", difficulty=3)

    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "An answer."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pendingQuestion"]["isFollowUp"] is False
    assert body["pendingQuestion"]["topic"] == "Node.js"


async def test_engine_respects_adaptive_difficulty_disabled(client, fake_ai_client):
    await _register(client, USER_A)
    profile_payload = {**CUSTOM_PROFILE_PAYLOAD, "adaptiveDifficulty": False, "maxQuestions": 5}
    profile = (await client.post("/interview-profiles", json=profile_payload)).json()
    interview = (
        await client.post(
            "/interviews",
            json={
                "profileId": profile["id"],
                "difficulty": "medium",  # DIFFICULTY_BASELINE["medium"] == 3
                "language": "English",
                "durationMinutes": 20,
            },
        )
    ).json()

    fake_ai_client.queue_question(question="Q1", topic="React", difficulty=3)
    await client.post(f"/interviews/{interview['id']}/start")

    # A top-quality answer would normally push difficulty up by 1.
    fake_ai_client.queue_analysis(quality=5, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2", topic="Node.js", difficulty=3)

    resp = await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "Great answer."})
    body = resp.json()
    assert body["difficultyLevel"] == 3  # unchanged — adaptive difficulty is off


# ---- Old interview compatibility -----------------------------------------


async def test_old_category_only_interview_starts_normally(client, fake_ai_client):
    """An interview created the Phase 1-7 way (no profileId at all) must
    still start and run exactly as before, via the legacy category lookup."""
    await _register(client, USER_A)
    interview = (
        await client.post(
            "/interviews",
            json={
                "category": "hr",
                "difficulty": "medium",
                "language": "English",
                "durationMinutes": 5,
            },
        )
    ).json()
    assert interview["profileId"] is None

    fake_ai_client.queue_question(question="Tell me about a conflict you resolved.", topic="Conflict Resolution")
    resp = await client.post(f"/interviews/{interview['id']}/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["maxQuestions"] == 4  # duration heuristic, unaffected by any profile
    assert body["pendingQuestion"]["question"] == "Tell me about a conflict you resolved."


async def test_old_interview_document_without_profile_field_still_reports(
    client, fake_ai_client, test_db
):
    """Simulates a genuinely pre-Phase-8 Mongo document that predates the
    profileId field existing at all (not just set to null)."""
    await _register(client, USER_A)
    interview = (
        await client.post(
            "/interviews",
            json={
                "category": "hr",
                "difficulty": "medium",
                "language": "English",
                "durationMinutes": 5,
            },
        )
    ).json()

    from bson import ObjectId

    await test_db.interviews.update_one(
        {"_id": ObjectId(interview["id"])}, {"$unset": {"profileId": ""}}
    )
    doc = await test_db.interviews.find_one({"_id": ObjectId(interview["id"])})
    assert "profileId" not in doc

    fake_ai_client.queue_question(question="Q1", topic="Conflict Resolution")
    resp = await client.post(f"/interviews/{interview['id']}/start")
    assert resp.status_code == 200
