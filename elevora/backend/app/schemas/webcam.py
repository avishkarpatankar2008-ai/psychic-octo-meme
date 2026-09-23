from pydantic import BaseModel, Field


class WebcamMetrics(BaseModel):
    """Aggregate observable signals computed CLIENT-SIDE over the session
    (spec's own preferred architecture: Camera -> Browser -> MediaPipe ->
    Metrics -> Backend, never raw frames uploaded). All rates are 0.0-1.0
    fractions of the measured session, not percentages.

    Deliberately just these three. The spec is explicit that only
    observable signals belong here — no emotion, confidence, or attention
    "detection" of any kind, and these three are the ones a face/pose
    landmarker can measure without pretending to read intent."""

    faceVisibleRate: float = Field(ge=0.0, le=1.0)
    lookingAwayRate: float = Field(ge=0.0, le=1.0)
    movementRate: float = Field(ge=0.0, le=1.0)
    sampledFrames: int = Field(ge=0)
