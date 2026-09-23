from typing import Optional

from pydantic import BaseModel, Field


class EvaluationDraft(BaseModel):
    """What the model returns when scoring a completed interview.

    Only the five dimensions we can actually ground in transcript data are
    AI-scored. Delivery (speech timing/pace) and Webcam (observable video
    signals) require analytics pipelines that don't exist until Phase 7/8 —
    asking the model to score them anyway would mean fabricating a number
    with no real evidence behind it, which is exactly what the spec's own
    "Mistake 6 — Random AI scores" warns against. Those two dimensions are
    filled in deterministically as "not yet available" in
    services/evaluation.py, not scored here.

    `confidence` (how much weight the report deserves) is also deliberately
    NOT an AI field — it's computed from turn count in evaluation.py.
    Self-rated confidence is exactly the kind of qualitative self-assessment
    LLMs are unreliable at; turn count is a fact, not a judgment call.
    """

    knowledgeScore: int = Field(ge=0, le=5)
    knowledgeEvidence: str
    communicationScore: int = Field(ge=0, le=5)
    communicationEvidence: str
    relevanceScore: int = Field(ge=0, le=5)
    relevanceEvidence: str
    problemSolvingScore: int = Field(ge=0, le=5)
    problemSolvingEvidence: str
    interviewHandlingScore: int = Field(ge=0, le=5)
    interviewHandlingEvidence: str
    strengths: list[str]
    weaknesses: list[str]
    recommendedPractice: list[str]
    improvedAnswer: Optional[str] = None
