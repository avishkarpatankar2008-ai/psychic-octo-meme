from app.schemas.speech import AggregateSpeechMetrics
from app.schemas.webcam import WebcamMetrics
from app.services.deterministic_scoring import score_delivery, score_webcam


def _speech(**overrides) -> AggregateSpeechMetrics:
    defaults = dict(
        turnsWithAudio=3,
        totalDurationSeconds=60.0,
        averageWordsPerMinute=135.0,
        totalPauseCount=2,
        longestPauseSeconds=1.5,
        overallFillerRate=0.02,
        totalRepeatedWordCount=0,
    )
    defaults.update(overrides)
    return AggregateSpeechMetrics(**defaults)


def _webcam(**overrides) -> WebcamMetrics:
    defaults = dict(faceVisibleRate=0.95, lookingAwayRate=0.05, movementRate=0.1, sampledFrames=200)
    defaults.update(overrides)
    return WebcamMetrics(**defaults)


class TestScoreDelivery:
    def test_ideal_pace_and_low_fillers_scores_high(self):
        score, evidence = score_delivery(_speech(averageWordsPerMinute=135, overallFillerRate=0.01))
        assert score == 5
        assert "135" in evidence

    def test_very_fast_pace_is_penalized(self):
        score, _ = score_delivery(_speech(averageWordsPerMinute=220))
        assert score < 5

    def test_very_slow_pace_is_penalized(self):
        score, _ = score_delivery(_speech(averageWordsPerMinute=60))
        assert score < 5

    def test_slightly_off_pace_penalized_less_than_very_off_pace(self):
        slightly_off, _ = score_delivery(_speech(averageWordsPerMinute=170))
        very_off, _ = score_delivery(_speech(averageWordsPerMinute=250))
        assert very_off < slightly_off

    def test_high_filler_rate_is_penalized(self):
        score, evidence = score_delivery(_speech(overallFillerRate=0.15))
        assert score < 5
        assert "15.0%" in evidence

    def test_long_pause_is_penalized(self):
        score, evidence = score_delivery(_speech(longestPauseSeconds=8.0))
        assert score < 5
        assert "8.0s" in evidence

    def test_score_never_goes_below_zero(self):
        score, _ = score_delivery(
            _speech(averageWordsPerMinute=300, overallFillerRate=0.5, longestPauseSeconds=20.0)
        )
        assert score == 0

    def test_score_never_exceeds_five(self):
        score, _ = score_delivery(_speech(averageWordsPerMinute=135, overallFillerRate=0.0))
        assert score <= 5

    def test_evidence_cites_turn_count_and_duration(self):
        _, evidence = score_delivery(_speech(turnsWithAudio=4, totalDurationSeconds=120.0))
        assert "4 voice answer" in evidence
        assert "120" in evidence


class TestScoreWebcam:
    def test_high_visibility_low_movement_scores_high(self):
        score, evidence = score_webcam(_webcam(faceVisibleRate=0.98, lookingAwayRate=0.02, movementRate=0.05))
        assert score == 5
        assert "98%" in evidence

    def test_low_face_visibility_heavily_penalized(self):
        score, _ = score_webcam(_webcam(faceVisibleRate=0.3))
        assert score <= 2

    def test_moderate_face_visibility_penalized_less(self):
        low, _ = score_webcam(_webcam(faceVisibleRate=0.3))
        moderate, _ = score_webcam(_webcam(faceVisibleRate=0.7))
        assert low < moderate

    def test_high_looking_away_rate_penalized(self):
        score, evidence = score_webcam(_webcam(lookingAwayRate=0.6))
        assert score < 5
        assert "60%" in evidence

    def test_high_movement_rate_penalized(self):
        score, _ = score_webcam(_webcam(movementRate=0.8))
        assert score < 5

    def test_score_never_negative(self):
        score, _ = score_webcam(_webcam(faceVisibleRate=0.1, lookingAwayRate=0.9, movementRate=0.9))
        assert score == 0

    def test_evidence_cites_sampled_frame_count(self):
        _, evidence = score_webcam(_webcam(sampledFrames=42))
        assert "42 sampled frames" in evidence
