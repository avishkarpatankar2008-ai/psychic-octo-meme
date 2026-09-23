from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile
from app.schemas.profile import InterviewProfile


def _context_suffix(profile: InterviewProfile) -> str:
    parts = []
    if profile.role:
        parts.append(f"for the role of {profile.role}")
    if profile.company:
        parts.append(f"at {profile.company}")
    if profile.exam:
        parts.append(f"for the {profile.exam} exam")
    return " " + " ".join(parts) if parts else ""


def _bulleted(items: list[str], limit: int = 6) -> str:
    return "\n".join(f"- {item}" for item in items[:limit])


def candidate_context_block(candidate: CandidateProfile) -> str:
    """A compact, labeled summary of the candidate's resume, fed into
    question generation once uploaded. Labeled 'CANDIDATE-PROVIDED' rather
    than 'VERIFIED' — per the spec's information-class distinction (section
    16), a resume is what the candidate claims about themselves, not an
    independently verified fact. Only non-empty sections are included."""
    sections = []
    if candidate.projects:
        sections.append("Projects:\n" + _bulleted(candidate.projects))
    if candidate.experience:
        sections.append("Experience:\n" + _bulleted(candidate.experience))
    if candidate.skills:
        sections.append("Skills:\n" + _bulleted(candidate.skills))
    if candidate.technologies:
        sections.append("Technologies:\n" + _bulleted(candidate.technologies))
    if candidate.achievements:
        sections.append("Achievements:\n" + _bulleted(candidate.achievements))
    if candidate.education:
        sections.append("Education:\n" + _bulleted(candidate.education))
    if not sections:
        return ""
    return (
        "\n\nCANDIDATE-PROVIDED BACKGROUND (from their resume — treat as their claims about "
        "themselves, not independently verified facts; never invent anything beyond this):\n"
        + "\n\n".join(sections)
    )


def job_context_block(job: JobProfile) -> str:
    """Same idea as candidate_context_block, for the job description."""
    sections = []
    if job.responsibilities:
        sections.append("Responsibilities:\n" + _bulleted(job.responsibilities))
    if job.requiredSkills:
        sections.append("Required skills:\n" + _bulleted(job.requiredSkills))
    if job.preferredSkills:
        sections.append("Preferred skills:\n" + _bulleted(job.preferredSkills))
    if not sections:
        return ""
    role_line = f" for {job.role}" if job.role else ""
    company_line = f" at {job.company}" if job.company else ""
    return (
        f"\n\nJOB DESCRIPTION CONTEXT{role_line}{company_line} (candidate-provided; never invent "
        f"technologies or requirements beyond what's listed):\n" + "\n\n".join(sections)
    )


def question_system_prompt(
    profile: InterviewProfile,
    *,
    candidate: CandidateProfile | None = None,
    job: JobProfile | None = None,
) -> str:
    base = (
        f"You are an experienced, {profile.interviewerStyle} interviewer conducting a "
        f"{profile.category.replace('-', ' ')} interview{_context_suffix(profile)}. "
        f"Ask exactly one interview question at a time, grounded in one of these subjects: "
        f"{', '.join(profile.subjects)}. Question types you may draw on: "
        f"{', '.join(profile.questionTypes)}. Never repeat or closely rephrase a question that "
        "has already been asked in this interview."
    )
    candidate_block = candidate_context_block(candidate) if candidate else ""
    job_block = job_context_block(job) if job else ""

    if candidate_block or job_block:
        base += (
            candidate_block
            + job_block
            + "\n\nWhen relevant to the current topic, ground your question in a specific "
            "project, skill, or claim from the background above — name it directly rather than "
            "asking generically. If nothing above is relevant to the topic, ask a normal "
            "subject-based question instead. Never attribute a technology, employer, or claim "
            "to the candidate that isn't in the background above."
        )
    else:
        base += (
            " Do not invent facts about the candidate — no resume or job description has been "
            "provided for this interview, so keep questions general to the subject rather than "
            "referencing specific (fabricated) candidate history."
        )
    return base


def baseline_question_user_prompt(
    topic: str, difficulty: int, previously_asked: list[str], *, opening: bool = False
) -> str:
    lines = [
        f"Ask a new baseline question on the topic '{topic}' at difficulty {difficulty} out of 5 "
        "(1 = very easy / introductory, 5 = very hard / expert).",
    ]
    if opening:
        lines.append(
            "This is the opening question of the interview — keep it welcoming but substantive."
        )
    if previously_asked:
        joined = "; ".join(f'"{q}"' for q in previously_asked[-10:])
        lines.append(f"Questions already asked (do not repeat or closely rephrase these): {joined}")
    lines.append("Set isFollowUp to false and targetClaim to null.")
    return "\n".join(lines)


def follow_up_question_user_prompt(
    topic: str,
    difficulty: int,
    previous_question: str,
    previous_answer: str,
    missing_evidence: str | None,
    previously_asked: list[str],
) -> str:
    probe = missing_evidence or "more concrete detail or evidence behind their claim"
    lines = [
        f'The candidate was just asked: "{previous_question}"',
        f'They answered: "{previous_answer}"',
        f"Ask one targeted follow-up question on the topic '{topic}' at difficulty {difficulty} "
        f"out of 5 that probes specifically for: {probe}.",
        "Set isFollowUp to true, and set targetClaim to the specific claim or statement from "
        "their answer that you are probing.",
    ]
    if previously_asked:
        joined = "; ".join(f'"{q}"' for q in previously_asked[-10:])
        lines.append(f"Questions already asked (do not repeat or closely rephrase these): {joined}")
    return "\n".join(lines)


def regenerate_unique_suffix(collision: str) -> str:
    return (
        f'\n\nThe question you just proposed is too similar to one already asked: "{collision}". '
        "Ask a clearly different question — different angle or sub-topic, not a reworded version."
    )


def analysis_system_prompt(profile: InterviewProfile) -> str:
    return (
        "You are scoring a single interview answer for an interview-practice tool. Be concise "
        "and objective, and base every strength or weakness only on what the candidate actually "
        "said — never invent facts, numbers, or claims they did not make. Interview context: a "
        f"{profile.category.replace('-', ' ')} interview{_context_suffix(profile)}."
    )


def analysis_user_prompt(question: str, answer: str, difficulty: int) -> str:
    return (
        f'Question asked (difficulty {difficulty}/5): "{question}"\n'
        f'Candidate\'s answer: "{answer}"\n\n'
        "Rate quality from 1 (poor) to 5 (excellent). List at most 2 strengths and 2 weaknesses, "
        "each a short specific phrase grounded in the answer. Set followUpNeeded to true only if "
        "the answer contains a specific claim, number, or decision that deserves probing — if so, "
        "describe exactly what's missing in missingEvidence (e.g. 'no measurement method given for "
        "the 40% improvement'). Set hasContradiction to true only if the answer contradicts "
        "something clearly stated in the question or your own instructions imply prior context; "
        "otherwise leave it false — do not speculate about contradictions with information you "
        "don't have."
    )


RESUME_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured information from resumes for an interview-practice tool. "
    "Extract ONLY what is explicitly stated in the text. If a section isn't present or you're "
    "not confident something belongs in a category, leave that list empty rather than guessing "
    "or inferring. Never invent a skill, employer, project, or number that isn't in the text. "
    "For 'claims', extract specific checkable statements a good interviewer might probe further "
    "— things with numbers, outcomes, or decisions (e.g. 'reduced query latency by 40%', 'led a "
    "team of 5'), not generic statements like 'hardworking team player'."
)


def resume_extraction_user_prompt(resume_text: str) -> str:
    return f"Resume text:\n\n{resume_text}"


JOB_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured information from job descriptions for an interview-practice tool. "
    "Extract ONLY what is explicitly stated in the text. If a field isn't present, leave it null "
    "(for role/company/industry/seniority) or an empty list (for skills/responsibilities). Never "
    "invent a requirement, technology, or responsibility that isn't in the text."
)


def job_extraction_user_prompt(jd_text: str) -> str:
    return f"Job description text:\n\n{jd_text}"


EVALUATION_SYSTEM_PROMPT_TEMPLATE = (
    "You are scoring a completed {category} interview{context} for an interview-practice tool. "
    "Score five dimensions from 0 (very poor) to 5 (excellent): knowledge, communication, "
    "relevance, problemSolving, and interviewHandling. "
    "CRITICAL RULE: every score must be justified by a specific evidence string that quotes or "
    "closely paraphrases something the candidate actually said — never give a score without "
    "pointing to what justifies it, and never invent an example that didn't happen. "
    "Definitions: knowledge = factual/technical correctness and depth; communication = clarity, "
    "structure, and use of terminology; relevance = how directly answers addressed what was "
    "asked, without unnecessary deviation; problemSolving = quality of reasoning, assumptions, "
    "and trade-off analysis; interviewHandling = how well the candidate handled follow-up "
    "questions and any contradictions, including whether they recovered well when probed. "
    "List at most 4 overall strengths and 4 weaknesses, grounded in specific moments. Suggest at "
    "most 3 concrete recommendedPractice items (e.g. 'practice explaining trade-offs with "
    "concrete metrics'). Optionally rewrite ONE of the candidate's weaker answers as "
    "improvedAnswer — a better version of what they could have said, clearly derived from their "
    "actual answer rather than a generic model answer. Do not evaluate delivery (speech pace/"
    "fillers) or webcam behavior — you weren't given that data and it isn't part of your output."
)


def evaluation_system_prompt(profile: InterviewProfile) -> str:
    context = _context_suffix(profile)
    return EVALUATION_SYSTEM_PROMPT_TEMPLATE.format(
        category=profile.category.replace("-", " "), context=context
    )


def _format_turn_for_evaluation(turn: dict) -> str:
    kind = "Follow-up" if turn.get("isFollowUp") else "Question"
    evaluation = turn.get("evaluation", {})
    quality = evaluation.get("quality")
    answer = turn.get("answer", "")
    if len(answer) > 800:
        answer = answer[:800] + "... [truncated]"
    lines = [
        f'{kind} {turn["sequence"]} (topic: {turn["topic"]}, difficulty {turn["difficulty"]}/5): '
        f'"{turn["question"]}"',
        f'Answer: "{answer}"',
    ]
    if quality is not None:
        lines.append(f"(scored {quality}/5 in the moment)")
    if evaluation.get("hasContradiction"):
        lines.append("(flagged as contradicting an earlier statement)")
    return "\n".join(lines)


def evaluation_user_prompt(turns: list[dict]) -> str:
    transcript = "\n\n".join(_format_turn_for_evaluation(t) for t in turns)
    contradiction_count = sum(1 for t in turns if t.get("evaluation", {}).get("hasContradiction"))
    follow_up_count = sum(1 for t in turns if t.get("isFollowUp"))

    summary_lines = [
        f"Total questions answered: {len(turns)}",
        f"Follow-up questions among them: {follow_up_count}",
        f"Times a contradiction was flagged during the interview: {contradiction_count}",
    ]

    return (
        "Full interview transcript:\n\n"
        + transcript
        + "\n\nSummary stats:\n"
        + "\n".join(summary_lines)
    )
