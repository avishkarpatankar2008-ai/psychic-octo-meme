from pydantic import BaseModel


class CandidateProfile(BaseModel):
    """Extracted from a resume. Every field defaults to an empty list rather
    than being invented — the extraction prompt is explicit that an absent
    section means an empty list, not a guess (see prompts.py,
    resume_extraction_system_prompt)."""

    skills: list[str]
    education: list[str]
    experience: list[str]
    projects: list[str]
    technologies: list[str]
    achievements: list[str]
    claims: list[str]
    """Specific, checkable statements worth possibly probing later — e.g.
    'reduced query latency by 40%'. Distinct from achievements: a claim is
    something a good interviewer might ask 'how did you measure that?'
    about; not every achievement needs that treatment."""
