from datetime import datetime, timezone
from typing import Any

from app.schemas.ai import QuestionGeneration
from app.schemas.candidate import CandidateProfile
from app.schemas.interview import AnswerResponse, PendingQuestionOut, StartInterviewResponse
from app.schemas.job import JobProfile
from app.schemas.profile import InterviewProfile
from app.services import prompts, similarity
from app.services.ai_client import AIClient
from app.services.profiles import DIFFICULTY_BASELINE, load_profile


class InterviewStateError(Exception):
    """Raised when an action is attempted in the wrong interview state
    (e.g. answering when there's no pending question)."""


def _load_candidate_and_job(
    interview: dict,
) -> tuple[CandidateProfile | None, JobProfile | None]:
    """Phase 5: resume/JD context, if it's been uploaded for this interview."""
    candidate_raw = interview.get("candidateProfile")
    job_raw = interview.get("jobProfile")
    candidate = CandidateProfile.model_validate(candidate_raw) if candidate_raw else None
    job = JobProfile.model_validate(job_raw) if job_raw else None
    return candidate, job


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _dedup_append(existing: list[str], new_items: list[str], cap: int) -> list[str]:
    result = list(existing)
    for item in new_items:
        if item and item not in result:
            result.append(item)
    return result[-cap:]


def _difficulty_delta(quality: int) -> int:
    if quality <= 2:
        return -1
    if quality >= 4:
        return 1
    return 0


def _compute_max_questions(duration_minutes: int) -> int:
    """Heuristic: roughly one question (with its follow-ups) per 3 minutes.
    Tune this once real sessions show how long people actually take per turn."""
    return max(4, min(20, round(duration_minutes / 3)))


def _pick_next_topic(profile: InterviewProfile, asked_topics: list[str]) -> str:
    for subject in profile.subjects:
        if subject not in asked_topics:
            return subject
    # Every subject has come up at least once — cycle back through the list
    # rather than getting stuck, so a long interview still has something to ask.
    return profile.subjects[len(asked_topics) % len(profile.subjects)]


async def _generate_unique_question(
    ai_client: AIClient,
    profile: InterviewProfile,
    *,
    mode: str,
    topic: str,
    difficulty: int,
    previously_asked: list[str],
    candidate: CandidateProfile | None = None,
    job: JobProfile | None = None,
    previous_question: str | None = None,
    previous_answer: str | None = None,
    missing_evidence: str | None = None,
    opening: bool = False,
) -> QuestionGeneration:
    system = prompts.question_system_prompt(profile, candidate=candidate, job=job)
    if mode == "follow_up":
        assert previous_question is not None and previous_answer is not None
        user = prompts.follow_up_question_user_prompt(
            topic, difficulty, previous_question, previous_answer, missing_evidence, previously_asked
        )
    else:
        user = prompts.baseline_question_user_prompt(topic, difficulty, previously_asked, opening=opening)

    question = await ai_client.generate_question(system=system, user=user)

    collision = similarity.find_too_similar(question.question, previously_asked)
    if collision:
        # One retry with an explicit nudge. If it still collides we proceed anyway —
        # per the architecture rule against unbounded retry loops, and because a
        # near-miss that slips through is a far smaller problem than a stuck request.
        retry_user = user + prompts.regenerate_unique_suffix(collision)
        question = await ai_client.generate_question(system=system, user=retry_user)

    return question


async def start_interview(db: Any, ai_client: AIClient, interview: dict) -> StartInterviewResponse:
    if interview["status"] != "draft":
        raise InterviewStateError("This interview has already been started.")

    profile, engine_settings = await load_profile(db, interview)
    candidate, job = _load_candidate_and_job(interview)
    if not engine_settings["resumeGrounding"]:
        candidate = None
    if not engine_settings["jdGrounding"]:
        job = None
    difficulty_level = DIFFICULTY_BASELINE[interview["difficulty"]]
    max_questions = engine_settings["maxQuestions"] or _compute_max_questions(
        interview["durationMinutes"]
    )
    first_topic = profile.subjects[0]

    question = await _generate_unique_question(
        ai_client,
        profile,
        mode="baseline",
        topic=first_topic,
        difficulty=difficulty_level,
        previously_asked=[],
        candidate=candidate,
        job=job,
        opening=True,
    )

    now_ts = datetime.now(timezone.utc)
    updates = {
        "status": "in_progress",
        "questionNumber": 0,
        "maxQuestions": max_questions,
        "difficultyLevel": difficulty_level,
        "currentTopic": question.topic,
        "askedTopics": [],
        "askedQuestions": [question.question],
        "followUpCounts": {},
        "strengths": [],
        "weaknesses": [],
        "pendingQuestion": question.model_dump(),
        "startedAt": now_ts,
        "updatedAt": now_ts,
    }
    await db.interviews.update_one({"_id": interview["_id"]}, {"$set": updates})

    return StartInterviewResponse(
        status="in_progress",
        questionNumber=0,
        maxQuestions=max_questions,
        difficultyLevel=difficulty_level,
        pendingQuestion=PendingQuestionOut(**question.model_dump()),
    )


async def submit_answer(
    db: Any,
    ai_client: AIClient,
    interview: dict,
    answer_text: str,
    speech_metrics: dict | None = None,
) -> AnswerResponse:
    if interview["status"] != "in_progress" or not interview.get("pendingQuestion"):
        raise InterviewStateError("There's no active question to answer right now.")

    pending = interview["pendingQuestion"]
    profile, engine_settings = await load_profile(db, interview)
    candidate, job = _load_candidate_and_job(interview)
    if not engine_settings["resumeGrounding"]:
        candidate = None
    if not engine_settings["jdGrounding"]:
        job = None

    analysis = await ai_client.analyze_answer(
        system=prompts.analysis_system_prompt(profile),
        user=prompts.analysis_user_prompt(pending["question"], answer_text, pending["difficulty"]),
    )

    sequence = interview["questionNumber"] + 1
    now_ts = datetime.now(timezone.utc)

    turn_doc = {
        "interviewId": str(interview["_id"]),
        "sequence": sequence,
        "question": pending["question"],
        "answer": answer_text,
        "topic": pending["topic"],
        "difficulty": pending["difficulty"],
        "isFollowUp": pending["isFollowUp"],
        "evaluation": analysis.model_dump(),
        "speechMetrics": speech_metrics,  # None for text answers — no audio to measure
        "createdAt": now_ts,
    }
    await db.interview_turns.insert_one(turn_doc)

    strengths = _dedup_append(interview.get("strengths", []), analysis.strengths, cap=8)
    weaknesses = _dedup_append(interview.get("weaknesses", []), analysis.weaknesses, cap=8)
    difficulty_delta = _difficulty_delta(analysis.quality) if engine_settings["adaptiveDifficulty"] else 0
    new_difficulty = _clamp(interview["difficultyLevel"] + difficulty_delta, 1, 5)

    asked_topics = list(interview.get("askedTopics", []))
    if not pending["isFollowUp"] and pending["topic"] not in asked_topics:
        asked_topics.append(pending["topic"])

    follow_up_counts = dict(interview.get("followUpCounts", {}))
    if pending["isFollowUp"]:
        follow_up_counts[pending["topic"]] = follow_up_counts.get(pending["topic"], 0) + 1

    asked_questions = list(interview.get("askedQuestions", []))
    reached_limit = sequence >= interview["maxQuestions"]

    next_pending: dict | None = None
    new_status = interview["status"]
    completed_at = None

    if reached_limit:
        new_status = "completed"
        completed_at = now_ts
    else:
        # Cap follow-up depth at 1 per topic for Phase 2 — chained probing,
        # pressure mode, and contradiction-challenge branches are Phase 5
        # ("Dynamic Interview Intelligence"), not this phase. Phase 8 adds a
        # profile-level on/off switch on top of that cap.
        want_follow_up = (
            engine_settings["followUpEnabled"]
            and analysis.followUpNeeded
            and not pending["isFollowUp"]
            and follow_up_counts.get(pending["topic"], 0) < 1
        )

        if want_follow_up:
            next_question = await _generate_unique_question(
                ai_client,
                profile,
                mode="follow_up",
                topic=pending["topic"],
                difficulty=new_difficulty,
                previously_asked=asked_questions,
                candidate=candidate,
                job=job,
                previous_question=pending["question"],
                previous_answer=answer_text,
                missing_evidence=analysis.missingEvidence,
            )
        else:
            next_topic = _pick_next_topic(profile, asked_topics)
            next_question = await _generate_unique_question(
                ai_client,
                profile,
                mode="baseline",
                topic=next_topic,
                difficulty=new_difficulty,
                previously_asked=asked_questions,
                candidate=candidate,
                job=job,
            )

        asked_questions.append(next_question.question)
        next_pending = next_question.model_dump()

    updates = {
        "questionNumber": sequence,
        "difficultyLevel": new_difficulty,
        "askedTopics": asked_topics,
        "askedQuestions": asked_questions,
        "followUpCounts": follow_up_counts,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "pendingQuestion": next_pending,
        "status": new_status,
        "currentTopic": next_pending["topic"] if next_pending else pending["topic"],
        "updatedAt": now_ts,
    }
    if completed_at:
        updates["completedAt"] = completed_at

    await db.interviews.update_one({"_id": interview["_id"]}, {"$set": updates})

    return AnswerResponse(
        status=new_status,
        questionNumber=sequence,
        maxQuestions=interview["maxQuestions"],
        difficultyLevel=new_difficulty,
        pendingQuestion=PendingQuestionOut(**next_pending) if next_pending else None,
        lastEvaluation=analysis,
    )


async def abandon_interview(db: Any, interview: dict) -> dict:
    """Leaving early (Phase 4's 'exit interview flow'). Marks the interview
    abandoned rather than deleting it — the partial transcript already
    recorded in interview_turns stays intact and visible."""
    if interview["status"] != "in_progress":
        raise InterviewStateError("Only an interview in progress can be exited early.")

    now_ts = datetime.now(timezone.utc)
    updates = {
        "status": "abandoned",
        "pendingQuestion": None,
        "completedAt": now_ts,
        "updatedAt": now_ts,
    }
    await db.interviews.update_one({"_id": interview["_id"]}, {"$set": updates})
    return {"status": "abandoned", "questionNumber": interview["questionNumber"]}


async def set_candidate_profile(db: Any, interview: dict, profile: CandidateProfile) -> None:
    """Phase 5: attach extracted resume data. Restricted to draft interviews
    — changing the candidate's background mid-interview would be a strange
    experience and isn't part of the spec's upload-then-start flow."""
    if interview["status"] != "draft":
        raise InterviewStateError("A resume can only be uploaded before the interview starts.")
    await db.interviews.update_one(
        {"_id": interview["_id"]},
        {"$set": {"candidateProfile": profile.model_dump(), "updatedAt": datetime.now(timezone.utc)}},
    )


async def set_job_profile(db: Any, interview: dict, profile: JobProfile) -> None:
    """Phase 5: attach extracted job-description data. Same restriction as
    set_candidate_profile."""
    if interview["status"] != "draft":
        raise InterviewStateError(
            "A job description can only be added before the interview starts."
        )
    await db.interviews.update_one(
        {"_id": interview["_id"]},
        {"$set": {"jobProfile": profile.model_dump(), "updatedAt": datetime.now(timezone.utc)}},
    )
