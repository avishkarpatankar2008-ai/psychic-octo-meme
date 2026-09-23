from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.interview_profile import InterviewProfileCreate, InterviewProfileOut


def new_profile_document(
    payload: InterviewProfileCreate, *, created_by: Optional[str], is_system: bool = False
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update(
        {
            "isActive": True,
            "isSystem": is_system,
            "createdBy": created_by,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return doc


def profile_doc_to_out(doc: dict[str, Any]) -> InterviewProfileOut:
    return InterviewProfileOut(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description", ""),
        category=doc["category"],
        subjects=doc["subjects"],
        questionTypes=doc["questionTypes"],
        interviewerStyle=doc.get("interviewerStyle", "professional"),
        difficulty=doc.get("difficulty", "medium"),
        maxQuestions=doc.get("maxQuestions", 8),
        followUpEnabled=doc.get("followUpEnabled", True),
        adaptiveDifficulty=doc.get("adaptiveDifficulty", True),
        resumeGrounding=doc.get("resumeGrounding", True),
        jdGrounding=doc.get("jdGrounding", True),
        isActive=doc.get("isActive", True),
        isSystem=doc.get("isSystem", False),
        createdBy=doc.get("createdBy"),
        createdAt=doc["createdAt"],
        updatedAt=doc["updatedAt"],
    )
