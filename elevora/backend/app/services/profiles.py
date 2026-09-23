from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.schemas.profile import InterviewProfile

# Seed catalog grounding question generation per category. Deliberately small
# and hand-picked rather than exhaustive — the spec's own guidance (Mistake 3,
# Mistake 9) is to avoid a huge curated question/subject database and instead
# expand a small set of strong templates over time. This becomes the seed
# data for the real InterviewProfile collection in Phase 8/9.
CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "campus-placement": {
        "subjects": ["DSA", "OOP", "DBMS", "Operating Systems", "Computer Networks"],
        "questionTypes": ["technical", "problem-solving", "behavioral"],
        "interviewerStyle": "professional",
    },
    "software-engineer": {
        "subjects": [
            "Data Structures",
            "System Design",
            "APIs",
            "Debugging",
            "Testing",
            "Databases",
        ],
        "questionTypes": ["technical", "problem-solving"],
        "interviewerStyle": "professional",
    },
    "mechanical-engineer": {
        "subjects": [
            "Thermodynamics",
            "Fluid Mechanics",
            "Manufacturing Processes",
            "Materials Science",
            "Machine Design",
        ],
        "questionTypes": ["technical", "problem-solving"],
        "interviewerStyle": "professional",
    },
    "hr": {
        "subjects": [
            "Teamwork",
            "Conflict Resolution",
            "Career Goals",
            "Strengths and Weaknesses",
            "Work Ethic",
        ],
        "questionTypes": ["behavioral"],
        "interviewerStyle": "conversational",
    },
    "mba": {
        "subjects": ["Leadership", "Case Analysis", "Career Vision", "Ethics", "Business Awareness"],
        "questionTypes": ["behavioral", "case-study"],
        "interviewerStyle": "professional",
    },
    "upsc": {
        "subjects": ["Current Affairs", "Governance", "Ethics", "Indian Polity", "Economy"],
        "questionTypes": ["knowledge", "situational"],
        "interviewerStyle": "formal",
    },
    "mpsc": {
        "subjects": [
            "State Governance",
            "Current Affairs",
            "Ethics",
            "Maharashtra History and Geography",
        ],
        "questionTypes": ["knowledge", "situational"],
        "interviewerStyle": "formal",
    },
    "ssc": {
        "subjects": ["General Awareness", "Quantitative Aptitude", "Reasoning", "English"],
        "questionTypes": ["knowledge"],
        "interviewerStyle": "formal",
    },
    "banking": {
        "subjects": ["Banking Awareness", "Current Affairs", "Quantitative Aptitude", "Reasoning"],
        "questionTypes": ["knowledge"],
        "interviewerStyle": "formal",
    },
    "company-specific": {
        "subjects": ["Role Fit", "Technical Fundamentals", "Behavioral", "Company Awareness"],
        "questionTypes": ["technical", "behavioral"],
        "interviewerStyle": "professional",
    },
    "other": {
        "subjects": ["General"],
        "questionTypes": ["behavioral"],
        "interviewerStyle": "professional",
    },
}

DIFFICULTY_BASELINE: dict[str, int] = {"easy": 2, "medium": 3, "hard": 4}


def derive_profile(interview: dict[str, Any]) -> InterviewProfile:
    defaults = CATEGORY_DEFAULTS.get(interview["category"], CATEGORY_DEFAULTS["other"])
    return InterviewProfile(
        category=interview["category"],
        role=interview.get("role"),
        company=interview.get("company"),
        exam=interview.get("exam"),
        industry=interview.get("industry"),
        subjects=defaults["subjects"],
        questionTypes=defaults["questionTypes"],
        interviewerStyle=defaults["interviewerStyle"],
    )


# Engine-level controls a Phase 8 InterviewProfile document carries that the
# Phase 2 category lookup never did. Legacy (profileId-less) interviews get
# these defaults, which reproduce the exact Phase 2-7 engine behavior.
_LEGACY_ENGINE_SETTINGS: dict[str, Any] = {
    "maxQuestions": None,  # None => interview_engine falls back to the duration heuristic
    "followUpEnabled": True,
    "adaptiveDifficulty": True,
    "resumeGrounding": True,
    "jdGrounding": True,
}


async def load_profile(db: Any, interview: dict[str, Any]) -> tuple[InterviewProfile, dict[str, Any]]:
    """Resolve the InterviewProfile (for prompting) and engine settings (for
    deterministic Python-side control) that apply to this interview.

    - If the interview has a profileId pointing at a real, stored
      InterviewProfile, use that (subjects/questionTypes/interviewerStyle
      plus its engine controls).
    - Otherwise (no profileId, or the profile it pointed at was deleted),
      fall back to the Phase 2 category-derived profile with legacy engine
      defaults — this is what keeps every pre-Phase-8 interview working
      exactly as it did before.
    """
    profile_id = interview.get("profileId")
    if profile_id:
        object_id: ObjectId | None
        try:
            object_id = ObjectId(profile_id)
        except InvalidId:
            object_id = None
        doc = await db.interview_profiles.find_one({"_id": object_id}) if object_id else None
        if doc:
            prompt_profile = InterviewProfile(
                category=doc["category"],
                role=interview.get("role"),
                company=interview.get("company"),
                exam=interview.get("exam"),
                industry=interview.get("industry"),
                subjects=doc["subjects"],
                questionTypes=doc["questionTypes"],
                interviewerStyle=doc.get("interviewerStyle", "professional"),
            )
            engine_settings = {
                "maxQuestions": doc.get("maxQuestions"),
                "followUpEnabled": doc.get("followUpEnabled", True),
                "adaptiveDifficulty": doc.get("adaptiveDifficulty", True),
                "resumeGrounding": doc.get("resumeGrounding", True),
                "jdGrounding": doc.get("jdGrounding", True),
            }
            return prompt_profile, engine_settings

    return derive_profile(interview), dict(_LEGACY_ENGINE_SETTINGS)
