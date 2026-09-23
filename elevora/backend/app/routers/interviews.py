from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.ai_deps import get_ai_client
from app.core.deps import get_current_user
from app.database import get_database
from app.models.interview import interview_doc_to_out, new_interview_document
from app.schemas.interview import (
    AnswerRequest,
    AnswerResponse,
    AudioAnswerResponse,
    ExitInterviewResponse,
    InterviewCreate,
    InterviewOut,
    InterviewTurnOut,
    JobDescriptionUploadResponse,
    ResumeUploadResponse,
    StartInterviewResponse,
)
from app.schemas.report import InterviewReport
from app.schemas.webcam import WebcamMetrics
from app.services import prompts, speech_analytics
from app.services.ai_client import AIClient, AIServiceError
from app.services.documents import DocumentParseError, extract_text
from app.services.evaluation import generate_report
from app.services.interview_engine import (
    InterviewStateError,
    abandon_interview,
    set_candidate_profile,
    set_job_profile,
    start_interview,
    submit_answer,
)
from app.services.interview_profiles import get_visible_profile

router = APIRouter(prefix="/interviews", tags=["interviews"])

# Keep recorded answers to a sane size — this is an application-level check,
# not a substitute for a request-size limit at the reverse proxy in production.
MAX_AUDIO_BYTES = 15 * 1024 * 1024  # ~15MB, comfortably more than a few minutes of speech
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/x-m4a",
}

# pydub/ffmpeg format strings for each allowed content type — lets
# compute_speech_metrics skip format auto-detection and decode directly.
_AUDIO_FORMAT_HINTS: dict[str, str] = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "audio/x-m4a": "m4a",
}


def _object_id_or_404(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")


async def _get_owned_interview_or_404(
    db: AsyncIOMotorDatabase, interview_id: str, user: dict
) -> dict:
    object_id = _object_id_or_404(interview_id)
    doc = await db.interviews.find_one({"_id": object_id, "userId": str(user["_id"])})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return doc


@router.post("", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
async def create_interview(
    payload: InterviewCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> InterviewOut:
    user_id = str(current_user["_id"])

    if payload.profileId:
        profile_doc = await get_visible_profile(db, payload.profileId, user_id)
        if not profile_doc or not profile_doc.get("isActive", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Interview profile not found"
            )
        if not payload.category:
            # category stays populated on the interview document itself (used by
            # report weighting and shown in interview history) even though the
            # profile — not this string — now drives question generation.
            payload = payload.model_copy(update={"category": profile_doc["category"]})

    doc = new_interview_document(user_id=user_id, payload=payload)
    result = await db.interviews.insert_one(doc)
    doc["_id"] = result.inserted_id
    return interview_doc_to_out(doc)


@router.get("", response_model=list[InterviewOut])
async def list_interviews(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[InterviewOut]:
    cursor = db.interviews.find({"userId": str(current_user["_id"])}).sort("createdAt", -1)
    return [interview_doc_to_out(doc) async for doc in cursor]


@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> InterviewOut:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    return interview_doc_to_out(doc)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    object_id = _object_id_or_404(interview_id)
    result = await db.interviews.delete_one(
        {"_id": object_id, "userId": str(current_user["_id"])}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    await db.interview_turns.delete_many({"interviewId": interview_id})


@router.post("/{interview_id}/start", response_model=StartInterviewResponse)
async def start_interview_endpoint(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> StartInterviewResponse:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    try:
        return await start_interview(db, ai_client, doc)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/{interview_id}/answer", response_model=AnswerResponse)
async def answer_endpoint(
    interview_id: str,
    payload: AnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> AnswerResponse:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    try:
        return await submit_answer(db, ai_client, doc, payload.answer)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/{interview_id}/turns", response_model=list[InterviewTurnOut])
async def list_turns(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[InterviewTurnOut]:
    await _get_owned_interview_or_404(db, interview_id, current_user)
    cursor = db.interview_turns.find({"interviewId": interview_id}).sort("sequence", 1)
    return [InterviewTurnOut(**turn) async for turn in cursor]


@router.post("/{interview_id}/exit", response_model=ExitInterviewResponse)
async def exit_interview_endpoint(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ExitInterviewResponse:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    try:
        result = await abandon_interview(db, doc)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ExitInterviewResponse(**result)


@router.get("/{interview_id}/question-audio")
async def get_question_audio(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> Response:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    if doc["status"] != "in_progress" or not doc.get("pendingQuestion"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="There's no active question to speak."
        )
    try:
        audio_bytes = await ai_client.synthesize_speech(text=doc["pendingQuestion"]["question"])
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/{interview_id}/answer/audio", response_model=AudioAnswerResponse)
async def answer_audio_endpoint(
    interview_id: str,
    audio_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> AudioAnswerResponse:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)

    if audio_file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {audio_file.content_type}",
        )

    raw = await audio_file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file.")
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file too large — keep answers under a few minutes.",
        )

    try:
        transcript = await ai_client.transcribe_audio(
            audio_bytes=raw, filename=audio_file.filename or "answer.webm"
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    transcript = transcript.strip()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't make out any speech in that recording. Try again, closer to the mic.",
        )

    # Phase 7: measure the actual audio before it's discarded (this project never
    # persists raw audio — see Phase 5's equivalent decision about resume files).
    # Failure here degrades gracefully: analytics are a bonus, not a requirement
    # for the interview to proceed, so a decode problem just means no metrics
    # for this turn rather than a failed answer submission.
    speech_metrics: dict | None = None
    try:
        format_hint = _AUDIO_FORMAT_HINTS.get(audio_file.content_type)
        metrics = speech_analytics.compute_speech_metrics(raw, transcript, format_hint=format_hint)
        speech_metrics = metrics.model_dump()
    except speech_analytics.SpeechAnalyticsError:
        pass

    try:
        result = await submit_answer(db, ai_client, doc, transcript, speech_metrics=speech_metrics)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return AudioAnswerResponse(**result.model_dump(), transcript=transcript)


@router.post("/{interview_id}/resume", response_model=ResumeUploadResponse)
async def upload_resume(
    interview_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> ResumeUploadResponse:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)

    raw = await file.read()
    try:
        resume_text = extract_text(filename=file.filename or "resume", content_type=file.content_type, raw=raw)
    except DocumentParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    try:
        candidate_profile = await ai_client.extract_candidate_profile(
            system=prompts.RESUME_EXTRACTION_SYSTEM_PROMPT,
            user=prompts.resume_extraction_user_prompt(resume_text),
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    try:
        await set_candidate_profile(db, doc, candidate_profile)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ResumeUploadResponse(candidateProfile=candidate_profile)


@router.post("/{interview_id}/job-description", response_model=JobDescriptionUploadResponse)
async def upload_job_description(
    interview_id: str,
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> JobDescriptionUploadResponse:
    """Accepts either a pasted text field or an uploaded PDF/DOCX file — job
    descriptions are more often copy-pasted from a posting than uploaded as
    a document, so both paths are supported rather than forcing a file."""
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)

    if file is None and not (text and text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a 'text' field or a 'file' upload.",
        )

    if file is not None:
        raw = await file.read()
        try:
            jd_text = extract_text(
                filename=file.filename or "job-description", content_type=file.content_type, raw=raw
            )
        except DocumentParseError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    else:
        assert text is not None
        jd_text = text.strip()[:15_000]
        if not jd_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Job description text is empty."
            )

    try:
        job_profile = await ai_client.extract_job_profile(
            system=prompts.JOB_EXTRACTION_SYSTEM_PROMPT,
            user=prompts.job_extraction_user_prompt(jd_text),
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    try:
        await set_job_profile(db, doc, job_profile)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return JobDescriptionUploadResponse(jobProfile=job_profile)


@router.post("/{interview_id}/webcam-metrics", response_model=WebcamMetrics)
async def submit_webcam_metrics(
    interview_id: str,
    metrics: WebcamMetrics,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> WebcamMetrics:
    """Client-computed aggregate signals only — see WebcamMetrics' docstring.
    No raw video ever reaches this endpoint or this backend at all."""
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    if doc["status"] not in ("in_progress", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webcam metrics can only be submitted for a session that has started.",
        )
    await db.interviews.update_one(
        {"_id": doc["_id"]}, {"$set": {"webcamMetrics": metrics.model_dump()}}
    )
    return metrics


@router.post("/{interview_id}/report", response_model=InterviewReport)
async def generate_report_endpoint(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    ai_client: AIClient = Depends(get_ai_client),
) -> InterviewReport:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    try:
        return await generate_report(db, ai_client, doc)
    except InterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/{interview_id}/report", response_model=InterviewReport)
async def get_report_endpoint(
    interview_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> InterviewReport:
    doc = await _get_owned_interview_or_404(db, interview_id, current_user)
    report = doc.get("report")
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report has been generated for this interview yet.",
        )
    return InterviewReport(**report)
