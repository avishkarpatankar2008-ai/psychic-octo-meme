"""
Phase 8: reusable, database-backed Interview Profiles.

This replaces the Phase 2 hardcoded CATEGORY_DEFAULTS lookup (still kept in
app/services/profiles.py for legacy interviews with no profileId — see that
module's load_profile()) with named, stored profiles that a user can select,
customize, or create from scratch.
"""

from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.interview_profile import new_profile_document
from app.schemas.interview_profile import InterviewProfileCreate

# The six seeded system profiles. Built from the same practical categories
# Phase 2's CATEGORY_DEFAULTS already covered, expanded with the engine
# controls (maxQuestions/followUpEnabled/adaptiveDifficulty/grounding) that
# were previously implicit constants inside interview_engine.py.
DEFAULT_PROFILES: list[dict[str, Any]] = [
    dict(
        name="Software Engineer",
        description="General software engineering interview covering data structures, "
        "system design, APIs, and debugging.",
        category="software-engineer",
        subjects=["Data Structures", "System Design", "APIs", "Debugging", "Testing", "Databases"],
        questionTypes=["technical", "problem-solving"],
        interviewerStyle="professional",
        difficulty="medium",
        maxQuestions=8,
        followUpEnabled=True,
        adaptiveDifficulty=True,
        resumeGrounding=True,
        jdGrounding=True,
    ),
    dict(
        name="Frontend Developer",
        description="Frontend-focused interview covering JavaScript, browser fundamentals, "
        "UI architecture, and performance.",
        category="frontend-developer",
        subjects=[
            "JavaScript",
            "HTML/CSS",
            "Component Architecture",
            "State Management",
            "Browser Performance",
            "Accessibility",
        ],
        questionTypes=["technical", "problem-solving"],
        interviewerStyle="professional",
        difficulty="medium",
        maxQuestions=8,
        followUpEnabled=True,
        adaptiveDifficulty=True,
        resumeGrounding=True,
        jdGrounding=True,
    ),
    dict(
        name="Backend Developer",
        description="Backend-focused interview covering APIs, databases, scalability, and "
        "system reliability.",
        category="backend-developer",
        subjects=[
            "API Design",
            "Databases",
            "Caching",
            "Scalability",
            "Concurrency",
            "System Design",
        ],
        questionTypes=["technical", "problem-solving"],
        interviewerStyle="professional",
        difficulty="medium",
        maxQuestions=8,
        followUpEnabled=True,
        adaptiveDifficulty=True,
        resumeGrounding=True,
        jdGrounding=True,
    ),
    dict(
        name="Data Analyst",
        description="Data analysis interview covering SQL, statistics, data visualization, "
        "and business reasoning.",
        category="data-analyst",
        subjects=["SQL", "Statistics", "Data Visualization", "Data Cleaning", "Business Reasoning"],
        questionTypes=["technical", "case-study"],
        interviewerStyle="professional",
        difficulty="medium",
        maxQuestions=8,
        followUpEnabled=True,
        adaptiveDifficulty=True,
        resumeGrounding=True,
        jdGrounding=True,
    ),
    dict(
        name="HR / Behavioral",
        description="Behavioral interview covering teamwork, conflict resolution, and "
        "career motivation.",
        category="hr",
        subjects=["Teamwork", "Conflict Resolution", "Career Goals", "Strengths and Weaknesses", "Work Ethic"],
        questionTypes=["behavioral"],
        interviewerStyle="conversational",
        difficulty="medium",
        maxQuestions=6,
        followUpEnabled=True,
        adaptiveDifficulty=False,
        resumeGrounding=True,
        jdGrounding=False,
    ),
    dict(
        name="System Design",
        description="Deep-dive system design interview for experienced engineers — "
        "scalability, trade-offs, and architecture.",
        category="system-design",
        subjects=[
            "Scalability",
            "Data Modeling",
            "Caching",
            "Load Balancing",
            "Trade-off Analysis",
            "Reliability",
        ],
        questionTypes=["technical", "problem-solving"],
        interviewerStyle="professional",
        difficulty="hard",
        maxQuestions=6,
        followUpEnabled=True,
        adaptiveDifficulty=True,
        resumeGrounding=False,
        jdGrounding=True,
    ),
]


async def seed_default_profiles(db: AsyncIOMotorDatabase) -> int:
    """Insert any system profiles that don't already exist. Idempotent and
    safe to call on every app startup: matches on (name, isSystem) with an
    atomic upsert, so a profile is never duplicated across restarts or
    concurrent workers, and a profile a user has since edited (isSystem
    profiles are protected from edits, but this stays defensive) is left
    alone rather than overwritten.
    """
    inserted = 0
    for spec in DEFAULT_PROFILES:
        payload = InterviewProfileCreate(**spec)
        doc = new_profile_document(payload, created_by=None, is_system=True)
        result = await db.interview_profiles.update_one(
            {"name": spec["name"], "isSystem": True},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
    return inserted


def _to_object_id(profile_id: str) -> Optional[ObjectId]:
    try:
        return ObjectId(profile_id)
    except InvalidId:
        return None


async def get_visible_profile(
    db: AsyncIOMotorDatabase, profile_id: str, user_id: str
) -> Optional[dict[str, Any]]:
    """A profile is visible to a user — for GET/PATCH/DELETE and for
    selecting it on a new interview — if it's active AND either a system
    profile or one they created themselves. Soft-deleted (isActive=False)
    profiles behave as if they don't exist here; interview_engine.load_profile
    deliberately does NOT use this helper, so already-started interviews
    keep working against a profile a user has since deleted."""
    object_id = _to_object_id(profile_id)
    if object_id is None:
        return None
    doc = await db.interview_profiles.find_one({"_id": object_id})
    if not doc or not doc.get("isActive", True):
        return None
    if doc.get("isSystem") or doc.get("createdBy") == user_id:
        return doc
    return None


async def get_owned_custom_profile(
    db: AsyncIOMotorDatabase, profile_id: str, user_id: str
) -> Optional[dict[str, Any]]:
    """Stricter than get_visible_profile: only a user's own *custom* profile
    qualifies — system profiles are never editable/deletable by users."""
    doc = await get_visible_profile(db, profile_id, user_id)
    if not doc or doc.get("isSystem"):
        return None
    return doc
