from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

ProfileDifficulty = Literal["easy", "medium", "hard", "adaptive"]


class InterviewProfileBase(BaseModel):
    """Shared shape for creating/reading a reusable Interview Profile.

    This is the Phase 8 upgrade the Phase 2 InterviewProfile schema
    (app/schemas/profile.py) already anticipated: a named, stored,
    reusable configuration instead of one derived on the fly from a
    hardcoded category lookup table.
    """

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    category: str = Field(min_length=1, max_length=60)
    subjects: list[str] = Field(min_length=1, max_length=20)
    questionTypes: list[str] = Field(min_length=1, max_length=10)
    interviewerStyle: str = Field(default="professional", max_length=40)
    difficulty: ProfileDifficulty = "medium"
    maxQuestions: int = Field(default=8, ge=3, le=30)
    followUpEnabled: bool = True
    adaptiveDifficulty: bool = True
    resumeGrounding: bool = True
    jdGrounding: bool = True

    @model_validator(mode="after")
    def _clean_lists(self) -> "InterviewProfileBase":
        self.subjects = [s.strip() for s in self.subjects if s.strip()]
        self.questionTypes = [t.strip() for t in self.questionTypes if t.strip()]
        if not self.subjects:
            raise ValueError("At least one subject is required.")
        if not self.questionTypes:
            raise ValueError("At least one question type is required.")
        return self


class InterviewProfileCreate(InterviewProfileBase):
    """Payload for POST /interview-profiles. isActive/isSystem/createdBy are
    always server-assigned, never client-settable."""


class InterviewProfileUpdate(BaseModel):
    """Payload for PATCH /interview-profiles/{id}. Every field optional —
    only what's supplied gets changed."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, min_length=1, max_length=60)
    subjects: Optional[list[str]] = Field(default=None, min_length=1, max_length=20)
    questionTypes: Optional[list[str]] = Field(default=None, min_length=1, max_length=10)
    interviewerStyle: Optional[str] = Field(default=None, max_length=40)
    difficulty: Optional[ProfileDifficulty] = None
    maxQuestions: Optional[int] = Field(default=None, ge=3, le=30)
    followUpEnabled: Optional[bool] = None
    adaptiveDifficulty: Optional[bool] = None
    resumeGrounding: Optional[bool] = None
    jdGrounding: Optional[bool] = None
    isActive: Optional[bool] = None


class InterviewProfileOut(InterviewProfileBase):
    id: str
    isActive: bool
    isSystem: bool
    createdBy: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
