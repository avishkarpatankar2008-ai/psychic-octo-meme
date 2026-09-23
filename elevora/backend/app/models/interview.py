from datetime import datetime, timezone
from typing import Any

from app.schemas.candidate import CandidateProfile
from app.schemas.interview import InterviewCreate, InterviewOut, PendingQuestionOut
from app.schemas.job import JobProfile


def new_interview_document(user_id: str, payload: InterviewCreate) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update(
        {
            "userId": user_id,
            "status": "draft",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return doc


def interview_doc_to_out(doc: dict[str, Any]) -> InterviewOut:
    pending = doc.get("pendingQuestion")
    return InterviewOut(
        id=str(doc["_id"]),
        userId=doc["userId"],
        category=doc["category"],
        profileId=doc.get("profileId"),
        role=doc.get("role"),
        company=doc.get("company"),
        exam=doc.get("exam"),
        industry=doc.get("industry"),
        experienceLevel=doc.get("experienceLevel"),
        difficulty=doc["difficulty"],
        language=doc["language"],
        durationMinutes=doc["durationMinutes"],
        status=doc["status"],
        createdAt=doc["createdAt"],
        updatedAt=doc["updatedAt"],
        questionNumber=doc.get("questionNumber", 0),
        maxQuestions=doc.get("maxQuestions"),
        difficultyLevel=doc.get("difficultyLevel"),
        currentTopic=doc.get("currentTopic"),
        pendingQuestion=PendingQuestionOut(**pending) if pending else None,
        startedAt=doc.get("startedAt"),
        candidateProfile=CandidateProfile(**doc["candidateProfile"]) if doc.get("candidateProfile") else None,
        jobProfile=JobProfile(**doc["jobProfile"]) if doc.get("jobProfile") else None,
    )
