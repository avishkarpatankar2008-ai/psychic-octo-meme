from typing import Optional

from pydantic import BaseModel


class InterviewProfile(BaseModel):
    """Grounds question generation in what's actually being practiced for.

    Phase 2 derives this from the interview's own configuration fields via a
    small static lookup table (see app/services/profiles.py). The product
    spec's full InterviewProfile system — named, reusable, stored profiles
    like "software-engineer-campus" — is Phase 8/9 work. This model's shape
    is deliberately close to that end state so upgrading later means
    swapping how a profile is *sourced*, not how it's *used* by the engine.
    """

    category: str
    role: Optional[str] = None
    company: Optional[str] = None
    exam: Optional[str] = None
    industry: Optional[str] = None
    subjects: list[str]
    questionTypes: list[str]
    interviewerStyle: str
