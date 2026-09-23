from typing import Optional

from pydantic import BaseModel


class JobProfile(BaseModel):
    """Extracted from a pasted or uploaded job description. Fields default
    to empty/None rather than invented — same anti-hallucination rule as
    CandidateProfile."""

    role: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    requiredSkills: list[str]
    preferredSkills: list[str]
    responsibilities: list[str]
    seniority: Optional[str] = None
