import io

import docx
import pymupdf
import pytest

pytestmark = pytest.mark.asyncio

SHORT_PAYLOAD = {
    "category": "software-engineer",
    "difficulty": "medium",
    "language": "English",
    "durationMinutes": 5,
}


def make_pdf_bytes(lines: list[str]) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + i * 20), line)
    raw = pdf.tobytes()
    pdf.close()
    return raw


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


async def _register_and_create(client, user_payload):
    await client.post("/auth/register", json=user_payload)
    return (await client.post("/interviews", json=SHORT_PAYLOAD)).json()


# ---- resume upload ---------------------------------------------------


async def test_upload_resume_requires_auth(client):
    resp = await client.post(
        "/interviews/000000000000000000000000/resume",
        files={"file": ("resume.pdf", b"%PDF-fake", "application/pdf")},
    )
    assert resp.status_code == 401


async def test_upload_resume_extracts_and_stores_profile(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    raw = make_pdf_bytes(["Jane Doe", "Built a heat exchanger optimization project"])

    fake_ai_client.queue_candidate_profile(
        skills=["Python", "Thermal analysis"],
        projects=["Heat exchanger optimization"],
        claims=["reduced cost by 20%"],
    )

    resp = await client.post(
        f"/interviews/{interview['id']}/resume",
        files={"file": ("resume.pdf", raw, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidateProfile"]["projects"] == ["Heat exchanger optimization"]

    # the extraction call actually received the resume's real extracted text
    assert "heat exchanger" in fake_ai_client.candidate_extraction_calls[0]["user"].lower()

    fetched = (await client.get(f"/interviews/{interview['id']}")).json()
    assert fetched["candidateProfile"]["skills"] == ["Python", "Thermal analysis"]


async def test_upload_resume_accepts_real_docx(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    raw = make_docx_bytes(["John Smith", "Experience: Backend Engineer at Acme"])
    fake_ai_client.queue_candidate_profile(experience=["Backend Engineer at Acme"])

    resp = await client.post(
        f"/interviews/{interview['id']}/resume",
        files={
            "file": (
                "resume.docx",
                raw,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200
    assert resp.json()["candidateProfile"]["experience"] == ["Backend Engineer at Acme"]


async def test_upload_resume_rejects_invalid_file(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    resp = await client.post(
        f"/interviews/{interview['id']}/resume",
        files={"file": ("resume.pdf", b"not a real pdf", "application/pdf")},
    )
    assert resp.status_code == 422


async def test_upload_resume_rejects_after_interview_started(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")

    raw = make_pdf_bytes(["Some resume text"])
    fake_ai_client.queue_candidate_profile()
    resp = await client.post(
        f"/interviews/{interview['id']}/resume",
        files={"file": ("resume.pdf", raw, "application/pdf")},
    )
    assert resp.status_code == 400


# ---- job description upload -----------------------------------------------


async def test_upload_job_description_via_text(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_job_profile(
        role="Backend Engineer",
        company="Acme Corp",
        requiredSkills=["Python", "PostgreSQL"],
        responsibilities=["Design APIs", "Own the database layer"],
    )

    resp = await client.post(
        f"/interviews/{interview['id']}/job-description",
        data={"text": "We need a Backend Engineer at Acme Corp skilled in Python and PostgreSQL."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["jobProfile"]["company"] == "Acme Corp"
    assert "Acme Corp" in fake_ai_client.job_extraction_calls[0]["user"]

    fetched = (await client.get(f"/interviews/{interview['id']}")).json()
    assert fetched["jobProfile"]["requiredSkills"] == ["Python", "PostgreSQL"]


async def test_upload_job_description_via_file(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    raw = make_pdf_bytes(["Senior Backend Engineer", "Required: Go, Kubernetes"])
    fake_ai_client.queue_job_profile(role="Senior Backend Engineer", requiredSkills=["Go", "Kubernetes"])

    resp = await client.post(
        f"/interviews/{interview['id']}/job-description",
        files={"file": ("jd.pdf", raw, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["jobProfile"]["requiredSkills"] == ["Go", "Kubernetes"]


async def test_upload_job_description_requires_text_or_file(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    resp = await client.post(f"/interviews/{interview['id']}/job-description")
    assert resp.status_code == 400


async def test_upload_job_description_rejects_blank_text(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)
    resp = await client.post(
        f"/interviews/{interview['id']}/job-description", data={"text": "   "}
    )
    assert resp.status_code == 400


# ---- grounding: does the resume actually change question generation? -----


async def test_resume_context_is_included_in_question_generation(
    client, fake_ai_client, user_payload
):
    """This is the closest thing to testing the spec's own 'DONE' criterion
    ('uploading a resume materially changes the interview') without a real
    model: verifying the extracted resume content actually reaches the
    question-generation prompt, not just that it's stored."""
    interview = await _register_and_create(client, user_payload)

    raw = make_pdf_bytes(["Built a heat exchanger optimization project"])
    fake_ai_client.queue_candidate_profile(projects=["Heat exchanger optimization project"])
    await client.post(
        f"/interviews/{interview['id']}/resume",
        files={"file": ("resume.pdf", raw, "application/pdf")},
    )

    fake_ai_client.queue_question(question="Tell me about your heat exchanger project.")
    await client.post(f"/interviews/{interview['id']}/start")

    system_prompt = fake_ai_client.question_calls[0]["system"]
    assert "Heat exchanger optimization project" in system_prompt
    assert "CANDIDATE-PROVIDED BACKGROUND" in system_prompt


async def test_job_context_is_included_in_question_generation(client, fake_ai_client, user_payload):
    interview = await _register_and_create(client, user_payload)

    fake_ai_client.queue_job_profile(
        role="Backend Engineer", responsibilities=["Own the payments service"]
    )
    await client.post(
        f"/interviews/{interview['id']}/job-description",
        data={"text": "Backend Engineer role owning the payments service."},
    )

    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")

    system_prompt = fake_ai_client.question_calls[0]["system"]
    assert "Own the payments service" in system_prompt
    assert "JOB DESCRIPTION CONTEXT" in system_prompt


async def test_no_resume_means_no_candidate_context_in_prompt(client, fake_ai_client, user_payload):
    """Negative case: without an upload, the prompt should say there's no
    resume rather than silently omitting the instruction."""
    interview = await _register_and_create(client, user_payload)
    fake_ai_client.queue_question()
    await client.post(f"/interviews/{interview['id']}/start")

    system_prompt = fake_ai_client.question_calls[0]["system"]
    assert "no resume or job description has been provided" in system_prompt
    assert "CANDIDATE-PROVIDED BACKGROUND" not in system_prompt


async def test_resume_context_persists_into_later_turns(client, fake_ai_client, user_payload):
    """Resume grounding shouldn't only apply to the opening question."""
    interview = await _register_and_create(client, user_payload)
    raw = make_pdf_bytes(["Led a team of five engineers"])
    fake_ai_client.queue_candidate_profile(experience=["Led a team of five engineers"])
    await client.post(
        f"/interviews/{interview['id']}/resume",
        files={"file": ("resume.pdf", raw, "application/pdf")},
    )

    fake_ai_client.queue_question(question="Q1?")
    await client.post(f"/interviews/{interview['id']}/start")

    fake_ai_client.queue_analysis(quality=3, followUpNeeded=False)
    fake_ai_client.queue_question(question="Q2?")
    await client.post(f"/interviews/{interview['id']}/answer", json={"answer": "ok"})

    # question_calls[0] = opening, [1] = the second baseline question
    assert "Led a team of five engineers" in fake_ai_client.question_calls[1]["system"]
