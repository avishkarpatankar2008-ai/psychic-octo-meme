from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.ai import AnswerAnalysis
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile
from app.schemas.speech import SpeechMetrics

InterviewCategory = Literal[
    "campus-placement",
    "software-engineer",
    "mechanical-engineer",
    "hr",
    "mba",
    "upsc",
    "mpsc",
    "ssc",
    "banking",
    "company-specific",
    "other",
]
"""The Phase 1-7 fixed category set. Kept as a reference/typing aid — Phase 8
onward, an interview's `category` field is a free-form string (see
InterviewCreate/InterviewOut below) so it can also hold a custom
InterviewProfile's own category (e.g. "frontend-developer" or something a
user typed when creating their own profile), while every value in this
literal remains a valid category too."""

InterviewStatus = Literal["draft", "in_progress", "completed", "abandoned"]


class InterviewCreate(BaseModel):
    """Configuration submitted by the interview setup wizard.

    In Phase 1 this is stored directly on the interview document, sourced
    from a hardcoded category. Phase 8 adds `profileId`: pick a reusable,
    database-backed InterviewProfile instead of (or alongside) a category.
    `category` is still accepted on its own for backward compatibility and
    to keep the door open for a profile-less quick-create; at least one of
    `category` / `profileId` is required.
    """

    category: Optional[str] = Field(default=None, max_length=60)
    profileId: Optional[str] = Field(default=None, description="An InterviewProfile's id.")
    role: Optional[str] = Field(default=None, max_length=120)
    company: Optional[str] = Field(default=None, max_length=120)
    exam: Optional[str] = Field(default=None, max_length=120)
    industry: Optional[str] = Field(default=None, max_length=120)
    experienceLevel: Optional[str] = Field(default="entry-level", max_length=60)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    language: str = Field(default="English", max_length=40)
    durationMinutes: int = Field(default=20, ge=5, le=90)

    @model_validator(mode="after")
    def _require_category_or_profile(self) -> "InterviewCreate":
        if not self.category and not self.profileId:
            raise ValueError("Provide either 'category' or 'profileId'.")
        return self


class PendingQuestionOut(BaseModel):
    question: str
    topic: str
    difficulty: int
    isFollowUp: bool


class InterviewOut(BaseModel):
    id: str
    userId: str
    category: str
    profileId: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    exam: Optional[str] = None
    industry: Optional[str] = None
    experienceLevel: Optional[str] = None
    difficulty: str
    language: str
    durationMinutes: int
    status: InterviewStatus
    createdAt: datetime
    updatedAt: datetime

    # Phase 2 — present once an interview has been started; absent (defaulted)
    # for interviews still sitting in "draft" from before Phase 2 existed.
    questionNumber: int = 0
    maxQuestions: Optional[int] = None
    difficultyLevel: Optional[int] = None
    currentTopic: Optional[str] = None
    pendingQuestion: Optional[PendingQuestionOut] = None
    startedAt: Optional[datetime] = None

    # Phase 5 — present once a resume/JD has been uploaded for this interview.
    candidateProfile: Optional[CandidateProfile] = None
    jobProfile: Optional[JobProfile] = None


class ResumeUploadResponse(BaseModel):
    """Returned right after extraction so the candidate can check for
    hallucinated content before the interview grounds questions in it."""

    candidateProfile: CandidateProfile


class JobDescriptionUploadResponse(BaseModel):
    jobProfile: JobProfile


class ExitInterviewResponse(BaseModel):
    """Response for the Phase 4 'exit interview' flow — leaving early marks
    the interview abandoned rather than deleting it, so the partial
    transcript survives (matches the roadmap's 'exit interview flow')."""

    status: InterviewStatus
    questionNumber: int


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


class StartInterviewResponse(BaseModel):
    status: InterviewStatus
    questionNumber: int
    maxQuestions: int
    difficultyLevel: int
    pendingQuestion: PendingQuestionOut


class AnswerResponse(BaseModel):
    status: InterviewStatus
    questionNumber: int
    maxQuestions: int
    difficultyLevel: int
    pendingQuestion: Optional[PendingQuestionOut] = None
    lastEvaluation: AnswerAnalysis


class InterviewTurnOut(BaseModel):
    sequence: int
    question: str
    answer: str
    topic: str
    difficulty: int
    isFollowUp: bool
    createdAt: datetime
    speechMetrics: Optional[SpeechMetrics] = None


class AudioAnswerResponse(AnswerResponse):
    """Same shape as a text answer's response, plus what speech-to-text heard —
    surfaced so the candidate can catch a bad transcription rather than
    silently having the interview react to words they didn't say."""

    transcript: str
