"""
Delivery and Webcam are the two dimensions where the underlying data is
purely objective numbers (WPM, filler rate, face-visible percentage) — there's
nothing for a language model to interpret that plain arithmetic can't. Scoring
them with rules instead of an AI call means:
  - No risk of the model overclaiming ("nervous pacing" from a WPM number
    is exactly the kind of unsupported inference the spec prohibits).
  - Every score traces to a specific threshold in this file, fully
    unit-testable with no mock at all — see tests/test_deterministic_scoring.py.
The thresholds below are reasonable starting points, not calibrated against
real interview recordings — expect to tune them once real usage data exists.
"""

from app.schemas.speech import AggregateSpeechMetrics
from app.schemas.webcam import WebcamMetrics


def score_delivery(aggregate: AggregateSpeechMetrics) -> tuple[int, str]:
    score = 5
    notes: list[str] = []

    wpm = aggregate.averageWordsPerMinute
    if wpm < 90 or wpm > 190:
        score -= 2
        notes.append(f"pace was {wpm:.0f} WPM, well outside the typical 110-160 WPM range")
    elif wpm < 110 or wpm > 160:
        score -= 1
        notes.append(f"pace was {wpm:.0f} WPM, slightly outside the typical 110-160 WPM range")
    else:
        notes.append(f"pace was {wpm:.0f} WPM, within a comfortable conversational range")

    filler_rate = aggregate.overallFillerRate
    if filler_rate > 0.09:
        score -= 2
        notes.append(f"filler words made up {filler_rate * 100:.1f}% of words spoken, quite high")
    elif filler_rate > 0.05:
        score -= 1
        notes.append(f"filler words made up {filler_rate * 100:.1f}% of words spoken, somewhat high")
    else:
        notes.append(f"filler words made up {filler_rate * 100:.1f}% of words spoken, low")

    if aggregate.longestPauseSeconds > 5:
        score -= 1
        notes.append(f"the longest single pause was {aggregate.longestPauseSeconds:.1f}s")

    score = max(0, min(5, score))
    evidence = (
        f"Based on {aggregate.turnsWithAudio} voice answer(s) totaling "
        f"{aggregate.totalDurationSeconds:.0f}s of speech: " + "; ".join(notes) + "."
    )
    return score, evidence


def score_webcam(metrics: WebcamMetrics) -> tuple[int, str]:
    score = 5
    notes: list[str] = []

    if metrics.faceVisibleRate < 0.5:
        score -= 3
        notes.append(f"face was visible in only {metrics.faceVisibleRate * 100:.0f}% of sampled frames")
    elif metrics.faceVisibleRate < 0.8:
        score -= 1
        notes.append(f"face was visible in {metrics.faceVisibleRate * 100:.0f}% of sampled frames")
    else:
        notes.append(f"face was visible in {metrics.faceVisibleRate * 100:.0f}% of sampled frames")

    if metrics.lookingAwayRate > 0.4:
        score -= 2
        notes.append(
            f"estimated looking away from the camera {metrics.lookingAwayRate * 100:.0f}% of the time"
        )
    elif metrics.lookingAwayRate > 0.2:
        score -= 1
        notes.append(
            f"estimated looking away from the camera {metrics.lookingAwayRate * 100:.0f}% of the time"
        )

    if metrics.movementRate > 0.5:
        score -= 1
        notes.append(f"frequent movement detected in {metrics.movementRate * 100:.0f}% of measured windows")

    score = max(0, min(5, score))
    evidence = "; ".join(notes) + f". Based on {metrics.sampledFrames} sampled frames."
    return score, evidence
