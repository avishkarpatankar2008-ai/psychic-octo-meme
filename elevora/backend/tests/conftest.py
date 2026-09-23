import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.ai_deps import get_ai_client
from app.database import ensure_indexes, get_database
from app.main import app
from app.schemas.ai import AnswerAnalysis, QuestionGeneration
from app.schemas.ai_evaluation import EvaluationDraft
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile


class FakeAIClient:
    """Scriptable stand-in for OpenAIClient. Tests queue up responses and
    assert on what the engine did with them — no network calls, no real
    model, but the same interface (see AIClient Protocol)."""

    def __init__(self):
        self._questions: list[QuestionGeneration] = []
        self._analyses: list[AnswerAnalysis] = []
        self._transcripts: list[str] = []
        self._audio_chunks: list[bytes] = []
        self._candidate_profiles: list[CandidateProfile] = []
        self._job_profiles: list[JobProfile] = []
        self._evaluations: list[EvaluationDraft] = []
        self.question_calls: list[dict] = []
        self.analysis_calls: list[dict] = []
        self.transcribe_calls: list[dict] = []
        self.speech_calls: list[dict] = []
        self.candidate_extraction_calls: list[dict] = []
        self.job_extraction_calls: list[dict] = []
        self.evaluation_calls: list[dict] = []

    def queue_question(self, **kwargs) -> None:
        defaults = dict(question="Default question?", topic="General", difficulty=3, isFollowUp=False)
        defaults.update(kwargs)
        self._questions.append(QuestionGeneration(**defaults))

    def queue_analysis(self, **kwargs) -> None:
        defaults = dict(
            quality=3,
            strengths=[],
            weaknesses=[],
            isRelevant=True,
            hasContradiction=False,
            followUpNeeded=False,
        )
        defaults.update(kwargs)
        self._analyses.append(AnswerAnalysis(**defaults))

    def queue_transcript(self, text: str) -> None:
        self._transcripts.append(text)

    def queue_audio(self, data: bytes) -> None:
        self._audio_chunks.append(data)

    def queue_candidate_profile(self, **kwargs) -> None:
        defaults = dict(
            skills=[], education=[], experience=[], projects=[], technologies=[],
            achievements=[], claims=[],
        )
        defaults.update(kwargs)
        self._candidate_profiles.append(CandidateProfile(**defaults))

    def queue_job_profile(self, **kwargs) -> None:
        defaults = dict(
            role=None, company=None, industry=None, requiredSkills=[], preferredSkills=[],
            responsibilities=[], seniority=None,
        )
        defaults.update(kwargs)
        self._job_profiles.append(JobProfile(**defaults))

    def queue_evaluation(self, **kwargs) -> None:
        defaults = dict(
            knowledgeScore=3,
            knowledgeEvidence="Gave a reasonable technical explanation.",
            communicationScore=3,
            communicationEvidence="Answers were clear enough to follow.",
            relevanceScore=3,
            relevanceEvidence="Answers addressed what was asked.",
            problemSolvingScore=3,
            problemSolvingEvidence="Reasoning was present but not deeply explored.",
            interviewHandlingScore=3,
            interviewHandlingEvidence="Handled follow-ups adequately.",
            strengths=[],
            weaknesses=[],
            recommendedPractice=[],
            improvedAnswer=None,
        )
        defaults.update(kwargs)
        self._evaluations.append(EvaluationDraft(**defaults))

    async def generate_question(self, *, system: str, user: str) -> QuestionGeneration:
        self.question_calls.append({"system": system, "user": user})
        if not self._questions:
            raise AssertionError("FakeAIClient.generate_question called with no queued response")
        return self._questions.pop(0)

    async def analyze_answer(self, *, system: str, user: str) -> AnswerAnalysis:
        self.analysis_calls.append({"system": system, "user": user})
        if not self._analyses:
            raise AssertionError("FakeAIClient.analyze_answer called with no queued response")
        return self._analyses.pop(0)

    async def transcribe_audio(self, *, audio_bytes: bytes, filename: str) -> str:
        self.transcribe_calls.append({"audio_bytes": audio_bytes, "filename": filename})
        if not self._transcripts:
            raise AssertionError("FakeAIClient.transcribe_audio called with no queued response")
        return self._transcripts.pop(0)

    async def synthesize_speech(self, *, text: str) -> bytes:
        self.speech_calls.append({"text": text})
        if not self._audio_chunks:
            raise AssertionError("FakeAIClient.synthesize_speech called with no queued response")
        return self._audio_chunks.pop(0)

    async def extract_candidate_profile(self, *, system: str, user: str) -> CandidateProfile:
        self.candidate_extraction_calls.append({"system": system, "user": user})
        if not self._candidate_profiles:
            raise AssertionError(
                "FakeAIClient.extract_candidate_profile called with no queued response"
            )
        return self._candidate_profiles.pop(0)

    async def extract_job_profile(self, *, system: str, user: str) -> JobProfile:
        self.job_extraction_calls.append({"system": system, "user": user})
        if not self._job_profiles:
            raise AssertionError("FakeAIClient.extract_job_profile called with no queued response")
        return self._job_profiles.pop(0)

    async def generate_evaluation(self, *, system: str, user: str) -> EvaluationDraft:
        self.evaluation_calls.append({"system": system, "user": user})
        if not self._evaluations:
            raise AssertionError("FakeAIClient.generate_evaluation called with no queued response")
        return self._evaluations.pop(0)


@pytest.fixture
def fake_ai_client():
    fake = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_ai_client, None)


@pytest_asyncio.fixture
async def test_db():
    """A fresh in-memory Mongo database per test — no real MongoDB required."""
    client = AsyncMongoMockClient()
    db = client["elevora_test"]
    await ensure_indexes(db)

    async def _override_get_database():
        return db

    app.dependency_overrides[get_database] = _override_get_database
    yield db
    app.dependency_overrides.pop(get_database, None)


@pytest_asyncio.fixture
async def client(test_db):
    """An async test client. Uses app's routed dependency override for the DB,
    so app startup (which connects to a real Mongo) is intentionally skipped."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def user_payload():
    return {"name": "Ada Lovelace", "email": "ada@example.com", "password": "supersecret123"}
