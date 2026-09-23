"""
Phase 7 speech analytics.

Two genuinely different confidence levels live in this one file:

1. Text-based metrics (fillers, repeated words, word count) are pure string
   processing — as testable as anything in this codebase, no dependencies
   beyond the standard library.

2. Audio-based metrics (duration, pauses, WPM) go through pydub + ffmpeg.
   Unlike the OpenAI calls elsewhere in this project, this WAS verified
   against real audio: the sandbox this was built in has ffmpeg installed,
   so tests/test_speech_analytics.py generates actual audio clips with known
   silence gaps (using pydub's tone/silence generators), exports them to
   real webm/wav bytes, and checks the detected pauses match. What's NOT
   verified is how real browser-recorded speech (background noise, varying
   volume, actual human pauses) behaves against the same silence-threshold
   heuristic — synthetic tone-and-silence clips are a clean test of the
   *mechanism*, not a guarantee the default threshold suits real recordings.
"""

import io
import re

from pydub import AudioSegment
from pydub.silence import detect_silence

from app.schemas.speech import AggregateSpeechMetrics, SpeechMetrics

# Default English filler vocabulary. The spec calls for this to be
# language-configurable — that's why every function here takes it as a
# parameter with this as the default, rather than a hardcoded constant deep
# in the logic.
DEFAULT_FILLER_WORDS = ["um", "uh", "uhh", "umm", "like", "you know", "actually", "basically", "so"]

# Silence detection tuning. A silence shorter than this doesn't count as a
# "pause" worth reporting (natural speech has tiny gaps between words at
# this scale) — these are reasonable starting values, not calibrated
# against real recordings (see module docstring).
MIN_PAUSE_MS = 500
SILENCE_THRESHOLD_DBFS = -40


class SpeechAnalyticsError(Exception):
    """Raised when audio can't be decoded. Callers should treat this as
    'metrics unavailable', not fail the whole answer-submission flow —
    analytics are a bonus, not a requirement for the interview to proceed."""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def word_count(text: str) -> int:
    return len(_tokenize(text))


def count_fillers(text: str, filler_words: list[str] | None = None) -> tuple[int, float]:
    """Returns (count, rate). Rate is count / total word count (0.0 if the
    answer has no words at all). Multi-word fillers ('you know') are matched
    against a punctuation-stripped, space-joined token stream, so "you
    know," or "you know." still match — matching on raw text would miss
    these since punctuation sits right up against the words in normal
    writing/transcripts."""
    fillers = filler_words or DEFAULT_FILLER_WORDS
    tokens = _tokenize(text)
    normalized = f" {' '.join(tokens)} "
    total_words = len(tokens)

    count = 0
    for filler in fillers:
        filler_tokens = " ".join(_tokenize(filler))
        count += normalized.count(f" {filler_tokens} ")

    rate = count / total_words if total_words > 0 else 0.0
    return count, rate


def count_repeated_words(text: str) -> int:
    """Counts immediately-repeated words ('the the', 'I I think') — a common
    verbal stumble marker. Deliberately not counting words repeated later in
    the answer (e.g. reusing 'basically' twice in different sentences is
    normal usage, not a stutter)."""
    tokens = _tokenize(text)
    return sum(1 for i in range(1, len(tokens)) if tokens[i] == tokens[i - 1])


def get_audio_duration_seconds(raw: bytes, *, format_hint: str | None = None) -> float:
    try:
        segment = AudioSegment.from_file(io.BytesIO(raw), format=format_hint)
    except Exception as exc:
        raise SpeechAnalyticsError(f"Couldn't decode audio to measure duration: {exc}") from exc
    return len(segment) / 1000.0


def detect_pauses(
    raw: bytes,
    *,
    format_hint: str | None = None,
    min_pause_ms: int = MIN_PAUSE_MS,
    silence_thresh_dbfs: int = SILENCE_THRESHOLD_DBFS,
) -> tuple[int, float, float]:
    """Returns (pause_count, average_pause_seconds, longest_pause_seconds).
    All zero if no pauses meeting the threshold were found — that's a valid
    result (continuous speech), not a failure."""
    try:
        segment = AudioSegment.from_file(io.BytesIO(raw), format=format_hint)
    except Exception as exc:
        raise SpeechAnalyticsError(f"Couldn't decode audio to detect pauses: {exc}") from exc

    silences = detect_silence(
        segment, min_silence_len=min_pause_ms, silence_thresh=silence_thresh_dbfs
    )
    if not silences:
        return 0, 0.0, 0.0

    durations_ms = [end - start for start, end in silences]
    pause_count = len(durations_ms)
    average_pause = (sum(durations_ms) / pause_count) / 1000.0
    longest_pause = max(durations_ms) / 1000.0
    return pause_count, average_pause, longest_pause


def compute_speech_metrics(
    raw: bytes, transcript: str, *, format_hint: str | None = None
) -> SpeechMetrics:
    """The one function callers actually use — combines everything above
    into the shape stored on an interview_turns document."""
    duration_seconds = get_audio_duration_seconds(raw, format_hint=format_hint)
    pause_count, avg_pause, longest_pause = detect_pauses(raw, format_hint=format_hint)

    words = word_count(transcript)
    words_per_minute = (words / duration_seconds) * 60 if duration_seconds > 0 else 0.0
    filler_count, filler_rate = count_fillers(transcript)
    repeated = count_repeated_words(transcript)

    return SpeechMetrics(
        durationSeconds=round(duration_seconds, 2),
        wordCount=words,
        wordsPerMinute=round(words_per_minute, 1),
        pauseCount=pause_count,
        averagePauseSeconds=round(avg_pause, 2),
        longestPauseSeconds=round(longest_pause, 2),
        fillerCount=filler_count,
        fillerRate=round(filler_rate, 4),
        repeatedWordCount=repeated,
    )


def aggregate_speech_metrics(turns: list[dict]) -> AggregateSpeechMetrics | None:
    """Combines every turn's speechMetrics (if any) into one session-level
    summary. Returns None if the interview had no voice answers at all —
    that's the signal evaluation.py uses to leave the Delivery dimension as
    "not available" rather than scoring an all-text interview on speech."""
    with_audio = [t for t in turns if t.get("speechMetrics")]
    if not with_audio:
        return None

    total_duration = sum(t["speechMetrics"]["durationSeconds"] for t in with_audio)
    total_words = sum(t["speechMetrics"]["wordCount"] for t in with_audio)
    total_pauses = sum(t["speechMetrics"]["pauseCount"] for t in with_audio)
    total_fillers = sum(t["speechMetrics"]["fillerCount"] for t in with_audio)
    total_repeated = sum(t["speechMetrics"]["repeatedWordCount"] for t in with_audio)
    longest_pause = max((t["speechMetrics"]["longestPauseSeconds"] for t in with_audio), default=0.0)

    average_wpm = (total_words / total_duration) * 60 if total_duration > 0 else 0.0
    overall_filler_rate = total_fillers / total_words if total_words > 0 else 0.0

    return AggregateSpeechMetrics(
        turnsWithAudio=len(with_audio),
        totalDurationSeconds=round(total_duration, 2),
        averageWordsPerMinute=round(average_wpm, 1),
        totalPauseCount=total_pauses,
        longestPauseSeconds=round(longest_pause, 2),
        overallFillerRate=round(overall_filler_rate, 4),
        totalRepeatedWordCount=total_repeated,
    )
