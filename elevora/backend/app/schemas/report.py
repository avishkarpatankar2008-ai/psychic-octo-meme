from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Confidence = Literal["low", "medium", "high"]

DIMENSION_NAMES = (
    "knowledge",
    "communication",
    "relevance",
    "problemSolving",
    "interviewHandling",
    "delivery",
    "webcam",
)


class DimensionScore(BaseModel):
    """One evaluation dimension. `score` is None when the dimension can't be
    computed yet (delivery/webcam — see EvaluationDraft's docstring) — the
    spec's rule that every score needs evidence applies just as much to
    explaining an absence as a number."""

    score: Optional[int] = None  # 0-5, None if not available
    evidence: str


class InterviewReport(BaseModel):
    interviewId: str
    overallScore: int  # 0-100, computed deterministically from available dimensions
    categoryScores: dict[str, int]  # 0-100 per dimension, only dimensions that are available
    dimensions: dict[str, DimensionScore]  # all 7 names from DIMENSION_NAMES, always present
    strengths: list[str]
    weaknesses: list[str]
    recommendedPractice: list[str]
    improvedAnswer: Optional[str] = None
    confidence: Confidence
    generatedAt: datetime
