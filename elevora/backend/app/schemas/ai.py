from typing import Optional

from pydantic import BaseModel, Field


class QuestionGeneration(BaseModel):
    """What the model returns when asked to generate the next interview question."""

    question: str
    topic: str
    difficulty: int = Field(ge=1, le=5)
    isFollowUp: bool
    targetClaim: Optional[str] = None


class AnswerAnalysis(BaseModel):
    """What the model returns when asked to analyze a candidate's answer.

    Deliberately mirrors the Day-9 shape from the product spec:
    {"quality": 3, "strengths": [], "weaknesses": [], "followUpNeeded": true}
    plus the extra fields needed to ground follow-ups in a specific claim
    (spec section 16: "the follow-up generator must cite the answer element
    it is probing").
    """

    quality: int = Field(ge=1, le=5)
    strengths: list[str]
    weaknesses: list[str]
    isRelevant: bool
    hasContradiction: bool
    followUpNeeded: bool
    followUpReason: Optional[str] = None
    missingEvidence: Optional[str] = None
