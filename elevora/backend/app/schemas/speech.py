from pydantic import BaseModel


class SpeechMetrics(BaseModel):
    """Computed once per voice answer from the actual audio + its transcript.
    Text answers never get this — there's no audio to measure timing from."""

    durationSeconds: float
    wordCount: int
    wordsPerMinute: float
    pauseCount: int
    averagePauseSeconds: float
    longestPauseSeconds: float
    fillerCount: int
    fillerRate: float  # fillerCount / wordCount, 0.0 if wordCount is 0
    repeatedWordCount: int


class AggregateSpeechMetrics(BaseModel):
    """SpeechMetrics from every voice answer in one interview, combined.
    Only exists when at least one answer was given by voice — see
    aggregate_speech_metrics() in services/speech_analytics.py."""

    turnsWithAudio: int
    totalDurationSeconds: float
    averageWordsPerMinute: float
    totalPauseCount: int
    longestPauseSeconds: float
    overallFillerRate: float
    totalRepeatedWordCount: int
