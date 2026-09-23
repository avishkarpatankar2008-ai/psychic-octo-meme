"""
Phase 6 evaluation engine.

Split deliberately the same way the rest of this codebase is: the AI scores
five dimensions with evidence (EvaluationDraft); everything about turning
those into a final weighted score is plain, deterministic Python with no
model involved. That split means the weighting math below is fully unit-
testable without any AI mock at all — same category of confidence as
services/documents.py, not the "unverified" bucket the actual OpenAI calls
live in.
"""

from datetime import datetime, timezone
from typing import Any

from app.schemas.ai_evaluation import EvaluationDraft
from app.schemas.profile import InterviewProfile
from app.schemas.report import DIMENSION_NAMES, Confidence, DimensionScore, InterviewReport
from app.schemas.webcam import WebcamMetrics
from app.services import prompts
from app.services.ai_client import AIClient
from app.services.deterministic_scoring import score_delivery, score_webcam
from app.services.interview_engine import InterviewStateError
from app.services.profiles import load_profile
from app.services.speech_analytics import aggregate_speech_metrics

UNAVAILABLE_EVIDENCE = {
    "delivery": (
        "No voice answers were given in this interview — Delivery metrics (pace, pauses, "
        "fillers) need speech to measure. Answer at least one question by voice to get this "
        "scored."
    ),
    "webcam": (
        "No webcam metrics were submitted for this interview — either the camera wasn't used, "
        "or the browser-side measurement didn't complete. This dimension isn't scored, not "
        "scored as zero."
    ),
}

# Weight profiles. All weights across the 7 dimensions sum to 1.0 for each
# profile; unavailable dimensions (delivery, webcam — always unavailable
# until Phase 7/8) have their weight redistributed proportionally among the
# dimensions that ARE available, rather than silently dropped or counted
# against the candidate. See compute_weighted_score().
WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "technical": {
        "knowledge": 0.40,
        "problemSolving": 0.25,
        "communication": 0.15,
        "relevance": 0.10,
        "interviewHandling": 0.05,
        "delivery": 0.05,
        "webcam": 0.00,
    },
    "behavioral": {
        "communication": 0.30,
        "relevance": 0.20,
        "interviewHandling": 0.20,
        "knowledge": 0.10,
        "problemSolving": 0.10,
        "delivery": 0.10,
        "webcam": 0.00,
    },
    "general": {
        "knowledge": 0.30,
        "communication": 0.20,
        "relevance": 0.15,
        "problemSolving": 0.15,
        "interviewHandling": 0.10,
        "delivery": 0.05,
        "webcam": 0.05,
    },
}

# Which weight profile applies to each interview category. A simple,
# reviewable heuristic — not claimed to be precisely calibrated, and worth
# revisiting once real reports exist to compare against.
CATEGORY_WEIGHT_PROFILE: dict[str, str] = {
    "software-engineer": "technical",
    "mechanical-engineer": "technical",
    "campus-placement": "technical",
    "hr": "behavioral",
    "mba": "behavioral",
    "upsc": "general",
    "mpsc": "general",
    "ssc": "general",
    "banking": "general",
    "company-specific": "general",
    "other": "general",
}


def weight_profile_for_category(category: str) -> dict[str, float]:
    profile_name = CATEGORY_WEIGHT_PROFILE.get(category, "general")
    return WEIGHT_PROFILES[profile_name]


def compute_weighted_score(
    dimension_scores: dict[str, int | None], weights: dict[str, float]
) -> tuple[int, dict[str, int]]:
    """Spec section 17's normalization: WeightedScore = Σ(dimensionScore/5 × weight),
    scaled to 0-100. Dimensions with score=None are excluded from both the
    numerator and the weight total (renormalized among what's available)
    rather than treated as a zero — a missing measurement isn't a bad score.

    Returns (overallScore 0-100, categoryScores per available dimension 0-100).
    """
    available = {dim: score for dim, score in dimension_scores.items() if score is not None}
    if not available:
        return 0, {}

    total_weight = sum(weights.get(dim, 0.0) for dim in available)
    if total_weight <= 0:
        # Every available dimension has zero weight in this profile (shouldn't
        # happen with the profiles above, but don't divide by zero if it does).
        category_scores = {dim: round((score / 5) * 100) for dim, score in available.items()}
        return round(sum(category_scores.values()) / len(category_scores)), category_scores

    weighted_sum = sum((score / 5) * weights.get(dim, 0.0) for dim, score in available.items())
    overall = round((weighted_sum / total_weight) * 100)
    category_scores = {dim: round((score / 5) * 100) for dim, score in available.items()}
    return overall, category_scores


def compute_confidence(turn_count: int, distinct_topics: int) -> Confidence:
    """Deterministic, not AI-judged — see EvaluationDraft's docstring for why.
    A report from a short or narrow interview deserves less trust; that's a
    fact about the transcript, not a qualitative call."""
    if turn_count < 4 or distinct_topics < 2:
        return "low"
    if turn_count >= 6 and distinct_topics >= 3:
        return "high"
    return "medium"


async def generate_report(db: Any, ai_client: AIClient, interview: dict) -> InterviewReport:
    if interview["status"] != "completed":
        raise InterviewStateError(
            "Only a completed interview can be evaluated. Abandoned or in-progress "
            "interviews aren't scored."
        )

    turns = [
        turn
        async for turn in db.interview_turns.find({"interviewId": str(interview["_id"])}).sort(
            "sequence", 1
        )
    ]
    if not turns:
        raise InterviewStateError("This interview has no answered questions to evaluate.")

    profile, _engine_settings = await load_profile(db, interview)
    draft = await ai_client.generate_evaluation(
        system=prompts.evaluation_system_prompt(profile),
        user=prompts.evaluation_user_prompt(turns),
    )

    dimension_scores: dict[str, int | None] = {
        "knowledge": draft.knowledgeScore,
        "communication": draft.communicationScore,
        "relevance": draft.relevanceScore,
        "problemSolving": draft.problemSolvingScore,
        "interviewHandling": draft.interviewHandlingScore,
        "delivery": None,
        "webcam": None,
    }
    evidence: dict[str, str] = {
        "knowledge": draft.knowledgeEvidence,
        "communication": draft.communicationEvidence,
        "relevance": draft.relevanceEvidence,
        "problemSolving": draft.problemSolvingEvidence,
        "interviewHandling": draft.interviewHandlingEvidence,
        "delivery": UNAVAILABLE_EVIDENCE["delivery"],
        "webcam": UNAVAILABLE_EVIDENCE["webcam"],
    }

    # Phase 7: score Delivery/Webcam deterministically from real measurements
    # when they exist, instead of leaving them permanently unavailable.
    speech_aggregate = aggregate_speech_metrics(turns)
    if speech_aggregate is not None:
        delivery_score, delivery_evidence = score_delivery(speech_aggregate)
        dimension_scores["delivery"] = delivery_score
        evidence["delivery"] = delivery_evidence

    webcam_raw = interview.get("webcamMetrics")
    if webcam_raw is not None:
        webcam_score, webcam_evidence = score_webcam(WebcamMetrics(**webcam_raw))
        dimension_scores["webcam"] = webcam_score
        evidence["webcam"] = webcam_evidence

    weights = weight_profile_for_category(interview["category"])
    overall_score, category_scores = compute_weighted_score(dimension_scores, weights)

    distinct_topics = len({turn["topic"] for turn in turns})
    confidence = compute_confidence(turn_count=len(turns), distinct_topics=distinct_topics)

    report = InterviewReport(
        interviewId=str(interview["_id"]),
        overallScore=overall_score,
        categoryScores=category_scores,
        dimensions={
            name: DimensionScore(score=dimension_scores[name], evidence=evidence[name])
            for name in DIMENSION_NAMES
        },
        strengths=draft.strengths,
        weaknesses=draft.weaknesses,
        recommendedPractice=draft.recommendedPractice,
        improvedAnswer=draft.improvedAnswer,
        confidence=confidence,
        generatedAt=datetime.now(timezone.utc),
    )

    await db.interviews.update_one(
        {"_id": interview["_id"]},
        {"$set": {"report": report.model_dump(), "overallScore": overall_score}},
    )

    return report
