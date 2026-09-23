"""
Run this after setting a real OPENAI_API_KEY, before trusting the AI engine.

This exercises app/services/ai_client.py against the actual OpenAI API — the
one piece of Phase 2 that could not be tested while building it (no network
access to api.openai.com from that sandbox). Everything else in Phase 2 is
covered by pytest with a mocked AI client; this is the real thing.

Usage:
    cd backend
    source venv/bin/activate  (or however you activated your env)
    python -m scripts.smoke_test_ai
"""

import asyncio

from app.schemas.profile import InterviewProfile
from app.services import prompts
from app.services.ai_client import AIServiceError, OpenAIClient


async def main() -> None:
    client = OpenAIClient()
    profile = InterviewProfile(
        category="software-engineer",
        role="Backend Engineer",
        subjects=["Databases", "System Design"],
        questionTypes=["technical"],
        interviewerStyle="professional",
    )

    print("1. Generating an opening question...")
    try:
        question = await client.generate_question(
            system=prompts.question_system_prompt(profile),
            user=prompts.baseline_question_user_prompt("Databases", difficulty=3, previously_asked=[], opening=True),
        )
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        print("   Check OPENAI_API_KEY, OPENAI_MODEL, and your account's API access.")
        return

    print(f"   question = {question.question!r}")
    print(f"   topic = {question.topic!r}, difficulty = {question.difficulty}, isFollowUp = {question.isFollowUp}")

    print("\n2. Analyzing a deliberately weak answer...")
    weak_answer = "I used a database once. It worked fine."
    try:
        analysis = await client.analyze_answer(
            system=prompts.analysis_system_prompt(profile),
            user=prompts.analysis_user_prompt(question.question, weak_answer, question.difficulty),
        )
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        return

    print(f"   quality = {analysis.quality}")
    print(f"   strengths = {analysis.strengths}")
    print(f"   weaknesses = {analysis.weaknesses}")
    print(f"   followUpNeeded = {analysis.followUpNeeded}  missingEvidence = {analysis.missingEvidence!r}")

    print("\n3. Analyzing a deliberately strong, specific answer...")
    strong_answer = (
        "I optimized a Postgres query that scanned 2M rows by adding a composite "
        "index on (user_id, created_at), which cut p95 latency from 800ms to 40ms — "
        "verified with EXPLAIN ANALYZE before and after."
    )
    try:
        analysis2 = await client.analyze_answer(
            system=prompts.analysis_system_prompt(profile),
            user=prompts.analysis_user_prompt(question.question, strong_answer, question.difficulty),
        )
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        return

    print(f"   quality = {analysis2.quality} (expect this higher than the weak answer's {analysis.quality})")
    print(f"   strengths = {analysis2.strengths}")

    print("\n4. Synthesizing speech for the opening question (Phase 3)...")
    try:
        audio_bytes = await client.synthesize_speech(text=question.question)
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        print("   This is the least-tested part of the whole build — check OPENAI_TTS_MODEL")
        print("   and OPENAI_TTS_VOICE are valid, and read the exception message closely.")
        return
    print(f"   got {len(audio_bytes)} bytes back.")
    with open("smoke_test_question.mp3", "wb") as f:
        f.write(audio_bytes)
    print("   wrote smoke_test_question.mp3 in the current directory — play it and confirm")
    print("   it's actually the question being read aloud, not silence or garbage.")

    print("\n5. Transcribing that same audio back (Phase 3, round-trip sanity check)...")
    try:
        transcript = await client.transcribe_audio(audio_bytes=audio_bytes, filename="question.mp3")
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        return
    print(f"   transcript = {transcript!r}")
    print("   Compare this to the original question text above — it won't match exactly")
    print("   (TTS/STT roundtrips rarely do) but it should be recognizably the same content.")

    print("\n6. Extracting a candidate profile from sample resume text (Phase 5)...")
    sample_resume = (
        "Jane Doe. Skills: Python, PostgreSQL, System Design. "
        "Experience: Backend Engineer at Acme Corp, 2021-2024. "
        "Projects: Rebuilt the payments service, reducing p95 latency by 40%. "
        "Education: BS Computer Science, State University."
    )
    try:
        candidate = await client.extract_candidate_profile(
            system=prompts.RESUME_EXTRACTION_SYSTEM_PROMPT,
            user=prompts.resume_extraction_user_prompt(sample_resume),
        )
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        return
    print(f"   skills = {candidate.skills}")
    print(f"   projects = {candidate.projects}")
    print("   Check nothing here was invented beyond what's in sample_resume above.")

    print("\n7. Generating an evaluation report from a tiny fake transcript (Phase 6)...")
    fake_turns = [
        {
            "sequence": 1,
            "topic": "Databases",
            "difficulty": 3,
            "isFollowUp": False,
            "question": "Tell me about a time you optimized a slow query.",
            "answer": strong_answer,
            "evaluation": {"quality": 5, "hasContradiction": False},
        },
        {
            "sequence": 2,
            "topic": "System Design",
            "difficulty": 3,
            "isFollowUp": False,
            "question": "How would you design a URL shortener?",
            "answer": weak_answer,
            "evaluation": {"quality": 2, "hasContradiction": False},
        },
    ]
    try:
        evaluation = await client.generate_evaluation(
            system=prompts.evaluation_system_prompt(profile),
            user=prompts.evaluation_user_prompt(fake_turns),
        )
    except AIServiceError as exc:
        print(f"   FAILED: {exc}")
        print("   This call has never been made against the real API before now — if it")
        print("   fails, check the exception message closely before assuming it's your key.")
        return
    print(f"   knowledgeScore = {evaluation.knowledgeScore}  evidence = {evaluation.knowledgeEvidence!r}")
    print(f"   strengths = {evaluation.strengths}")
    print(f"   weaknesses = {evaluation.weaknesses}")
    print("   Check each score's evidence actually references the fake transcript above,")
    print("   not something invented.")

    print("\nIf all seven steps produced sensible output, the integration is basically sound.")
    print("Things worth checking manually beyond this script:")
    print("  - Run start_interview -> submit_answer several times in a row via the API")
    print("    and confirm no repeated questions across ~10 turns.")
    print("  - Try an off-topic or contradictory answer and see whether hasContradiction/")
    print("    followUpNeeded behave sensibly — the prompts are a first draft, not tuned.")
    print("  - Run the full report generation via POST /interviews/{id}/report on a real")
    print("    completed interview and read the whole thing, not just this one call.")


if __name__ == "__main__":
    asyncio.run(main())
