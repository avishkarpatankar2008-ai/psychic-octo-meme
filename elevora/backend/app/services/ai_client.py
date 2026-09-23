"""
AI client for the interview engine (Phase 2: question generation, answer
analysis) and voice layer (Phase 3: transcription, speech synthesis).

IMPORTANT — this is the one piece of the AI engine that could NOT be
exercised against the real OpenAI API while building this: the sandbox this
was built in has no network access to api.openai.com (only package
registries and api.anthropic.com are reachable). Everything else is
covered by tests using FakeAIClient (see tests/conftest.py); this class
itself is not. That goes double for the Phase 3 additions below — the
audio.transcriptions and audio.speech endpoints were never exercised, not
even the request shape checked against a live error response.

The request shape for question/answer generation (client.responses.create
with text.format.type = "json_schema", strict=True) matches current OpenAI
documentation as of when this was written, and additionalProperties: False
+ all fields listed in `required` is deliberate — that's what strict mode
requires even for "optional" fields (which become nullable-typed instead of
omittable).

Before trusting this: set OPENAI_API_KEY and run
    python -m scripts.smoke_test_ai
and read its output. Don't assume this file is correct just because it's
well-commented.
"""

import json
from typing import Protocol

from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.ai import AnswerAnalysis, QuestionGeneration
from app.schemas.ai_evaluation import EvaluationDraft
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile

settings = get_settings()


class AIServiceError(Exception):
    """Raised for any failure talking to the AI provider or parsing its output."""


QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "topic": {"type": "string"},
        "difficulty": {"type": "integer"},
        "isFollowUp": {"type": "boolean"},
        "targetClaim": {"type": ["string", "null"]},
    },
    "required": ["question", "topic", "difficulty", "isFollowUp", "targetClaim"],
    "additionalProperties": False,
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "quality": {"type": "integer"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "isRelevant": {"type": "boolean"},
        "hasContradiction": {"type": "boolean"},
        "followUpNeeded": {"type": "boolean"},
        "followUpReason": {"type": ["string", "null"]},
        "missingEvidence": {"type": ["string", "null"]},
    },
    "required": [
        "quality",
        "strengths",
        "weaknesses",
        "isRelevant",
        "hasContradiction",
        "followUpNeeded",
        "followUpReason",
        "missingEvidence",
    ],
    "additionalProperties": False,
}

CANDIDATE_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "string"}},
        "experience": {"type": "array", "items": {"type": "string"}},
        "projects": {"type": "array", "items": {"type": "string"}},
        "technologies": {"type": "array", "items": {"type": "string"}},
        "achievements": {"type": "array", "items": {"type": "string"}},
        "claims": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "skills",
        "education",
        "experience",
        "projects",
        "technologies",
        "achievements",
        "claims",
    ],
    "additionalProperties": False,
}

JOB_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": ["string", "null"]},
        "company": {"type": ["string", "null"]},
        "industry": {"type": ["string", "null"]},
        "requiredSkills": {"type": "array", "items": {"type": "string"}},
        "preferredSkills": {"type": "array", "items": {"type": "string"}},
        "responsibilities": {"type": "array", "items": {"type": "string"}},
        "seniority": {"type": ["string", "null"]},
    },
    "required": [
        "role",
        "company",
        "industry",
        "requiredSkills",
        "preferredSkills",
        "responsibilities",
        "seniority",
    ],
    "additionalProperties": False,
}

EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "knowledgeScore": {"type": "integer"},
        "knowledgeEvidence": {"type": "string"},
        "communicationScore": {"type": "integer"},
        "communicationEvidence": {"type": "string"},
        "relevanceScore": {"type": "integer"},
        "relevanceEvidence": {"type": "string"},
        "problemSolvingScore": {"type": "integer"},
        "problemSolvingEvidence": {"type": "string"},
        "interviewHandlingScore": {"type": "integer"},
        "interviewHandlingEvidence": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "recommendedPractice": {"type": "array", "items": {"type": "string"}},
        "improvedAnswer": {"type": ["string", "null"]},
    },
    "required": [
        "knowledgeScore",
        "knowledgeEvidence",
        "communicationScore",
        "communicationEvidence",
        "relevanceScore",
        "relevanceEvidence",
        "problemSolvingScore",
        "problemSolvingEvidence",
        "interviewHandlingScore",
        "interviewHandlingEvidence",
        "strengths",
        "weaknesses",
        "recommendedPractice",
        "improvedAnswer",
    ],
    "additionalProperties": False,
}


class AIClient(Protocol):
    """Interface the interview engine depends on. FakeAIClient implements this for tests."""

    async def generate_question(self, *, system: str, user: str) -> QuestionGeneration: ...

    async def analyze_answer(self, *, system: str, user: str) -> AnswerAnalysis: ...

    async def transcribe_audio(self, *, audio_bytes: bytes, filename: str) -> str: ...

    async def synthesize_speech(self, *, text: str) -> bytes: ...

    async def extract_candidate_profile(self, *, system: str, user: str) -> CandidateProfile: ...

    async def extract_job_profile(self, *, system: str, user: str) -> JobProfile: ...

    async def generate_evaluation(self, *, system: str, user: str) -> EvaluationDraft: ...


class OpenAIClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None  # lazy: importing this module needs no key

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not settings.openai_api_key:
                raise AIServiceError(
                    "OPENAI_API_KEY is not set. Add it to backend/.env before starting an interview."
                )
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def _call(self, *, system: str, user: str, schema: dict, schema_name: str) -> dict:
        try:
            response = await self.client.responses.create(
                model=settings.openai_model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
        except AIServiceError:
            raise  # e.g. missing API key — already a clear message, don't wrap it further
        except Exception as exc:  # the openai SDK raises its own exception hierarchy
            raise AIServiceError(f"OpenAI request failed: {exc}") from exc

        raw = getattr(response, "output_text", None)
        if not raw:
            raise AIServiceError("OpenAI response contained no text output.")

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIServiceError(f"OpenAI did not return valid JSON: {exc}") from exc

    async def generate_question(self, *, system: str, user: str) -> QuestionGeneration:
        data = await self._call(
            system=system, user=user, schema=QUESTION_SCHEMA, schema_name="question_generation"
        )
        try:
            return QuestionGeneration.model_validate(data)
        except Exception as exc:
            raise AIServiceError(f"OpenAI question output failed validation: {exc}") from exc

    async def analyze_answer(self, *, system: str, user: str) -> AnswerAnalysis:
        data = await self._call(
            system=system, user=user, schema=ANALYSIS_SCHEMA, schema_name="answer_analysis"
        )
        try:
            return AnswerAnalysis.model_validate(data)
        except Exception as exc:
            raise AIServiceError(f"OpenAI analysis output failed validation: {exc}") from exc

    async def transcribe_audio(self, *, audio_bytes: bytes, filename: str) -> str:
        """Speech-to-text for a recorded answer.

        UNVERIFIED (see module docstring): the (filename, bytes) tuple form
        for the `file` parameter matches how the openai-python SDK documents
        multipart file uploads elsewhere in its API (e.g. file uploads for
        fine-tuning), but this specific call was never made against the real
        endpoint.
        """
        try:
            transcript = await self.client.audio.transcriptions.create(
                model=settings.openai_transcribe_model,
                file=(filename, audio_bytes),
            )
        except AIServiceError:
            raise
        except Exception as exc:
            raise AIServiceError(f"OpenAI transcription failed: {exc}") from exc

        text = getattr(transcript, "text", None)
        if text is None:
            raise AIServiceError("OpenAI transcription response had no 'text' field.")
        return text

    async def synthesize_speech(self, *, text: str) -> bytes:
        """Text-to-speech for the current interview question.

        UNVERIFIED (see module docstring). `response.aread()` is my best
        understanding of how to pull raw bytes off the async binary response
        the SDK returns for this endpoint; if the installed SDK version
        exposes a different accessor, this will raise AIServiceError with
        the underlying exception message rather than silently returning
        garbage — check that message first if this breaks.
        """
        try:
            response = await self.client.audio.speech.create(
                model=settings.openai_tts_model,
                voice=settings.openai_tts_voice,
                input=text,
            )
        except AIServiceError:
            raise
        except Exception as exc:
            raise AIServiceError(f"OpenAI speech synthesis failed: {exc}") from exc

        try:
            return await response.aread()
        except AttributeError as exc:
            raise AIServiceError(
                f"Unexpected response shape from audio.speech.create(): {exc}"
            ) from exc

    async def extract_candidate_profile(self, *, system: str, user: str) -> CandidateProfile:
        data = await self._call(
            system=system,
            user=user,
            schema=CANDIDATE_PROFILE_SCHEMA,
            schema_name="candidate_profile",
        )
        try:
            return CandidateProfile.model_validate(data)
        except Exception as exc:
            raise AIServiceError(f"OpenAI candidate-profile output failed validation: {exc}") from exc

    async def extract_job_profile(self, *, system: str, user: str) -> JobProfile:
        data = await self._call(
            system=system, user=user, schema=JOB_PROFILE_SCHEMA, schema_name="job_profile"
        )
        try:
            return JobProfile.model_validate(data)
        except Exception as exc:
            raise AIServiceError(f"OpenAI job-profile output failed validation: {exc}") from exc

    async def generate_evaluation(self, *, system: str, user: str) -> EvaluationDraft:
        data = await self._call(
            system=system, user=user, schema=EVALUATION_SCHEMA, schema_name="evaluation_draft"
        )
        try:
            return EvaluationDraft.model_validate(data)
        except Exception as exc:
            raise AIServiceError(f"OpenAI evaluation output failed validation: {exc}") from exc
