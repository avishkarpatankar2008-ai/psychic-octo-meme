import io

import docx
import pymupdf
import pytest

from app.services.documents import (
    DocumentParseError,
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)


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


# ---- PDF --------------------------------------------------------------


def test_extract_text_from_real_pdf():
    raw = make_pdf_bytes(["John Doe", "Skills: Python, FastAPI, MongoDB"])
    text = extract_text_from_pdf(raw)
    assert "John Doe" in text
    assert "Python" in text


def test_pdf_extraction_rejects_wrong_magic_bytes():
    fake_pdf = b"MZ\x90\x00" + b"\x00" * 100  # a Windows executable header, renamed .pdf
    with pytest.raises(DocumentParseError, match="doesn't look like a real PDF"):
        extract_text_from_pdf(fake_pdf)


def test_pdf_extraction_rejects_corrupted_pdf():
    corrupted = b"%PDF-1.4\nthis is not valid pdf content after the header"
    with pytest.raises(DocumentParseError):
        extract_text_from_pdf(corrupted)


# ---- DOCX ---------------------------------------------------------------


def test_extract_text_from_real_docx():
    raw = make_docx_bytes(["Jane Smith", "Experience: Software Engineer at Acme Corp"])
    text = extract_text_from_docx(raw)
    assert "Jane Smith" in text
    assert "Acme Corp" in text


def test_docx_extraction_rejects_wrong_magic_bytes():
    fake_docx = b"not a zip file at all"
    with pytest.raises(DocumentParseError, match="doesn't look like a real .docx"):
        extract_text_from_docx(fake_docx)


def test_docx_extraction_rejects_corrupted_docx():
    corrupted = b"PK\x03\x04" + b"\x00" * 50  # right magic bytes, garbage zip contents
    with pytest.raises(DocumentParseError):
        extract_text_from_docx(corrupted)


# ---- extract_text() dispatcher -------------------------------------------


def test_dispatcher_routes_pdf_by_content_type():
    raw = make_pdf_bytes(["Resume content here"])
    text = extract_text(filename="resume", content_type="application/pdf", raw=raw)
    assert "Resume content here" in text


def test_dispatcher_routes_docx_by_content_type():
    raw = make_docx_bytes(["Resume content here"])
    text = extract_text(
        filename="resume",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        raw=raw,
    )
    assert "Resume content here" in text


def test_dispatcher_falls_back_to_filename_extension():
    raw = make_pdf_bytes(["Resume via extension"])
    text = extract_text(filename="resume.pdf", content_type=None, raw=raw)
    assert "Resume via extension" in text


def test_dispatcher_rejects_unsupported_type():
    with pytest.raises(DocumentParseError, match="Unsupported file type"):
        extract_text(filename="resume.txt", content_type="text/plain", raw=b"plain text resume")


def test_dispatcher_rejects_empty_file():
    with pytest.raises(DocumentParseError, match="empty"):
        extract_text(filename="resume.pdf", content_type="application/pdf", raw=b"")


def test_dispatcher_rejects_oversized_file():
    oversized = b"%PDF-" + b"0" * (8 * 1024 * 1024 + 1)
    with pytest.raises(DocumentParseError, match="too large"):
        extract_text(filename="resume.pdf", content_type="application/pdf", raw=oversized)


def test_dispatcher_rejects_image_only_pdf_with_no_text_layer():
    pdf = pymupdf.open()
    pdf.new_page()  # a blank page — no text inserted at all
    raw = pdf.tobytes()
    pdf.close()
    with pytest.raises(DocumentParseError, match="Couldn't find any readable text"):
        extract_text(filename="resume.pdf", content_type="application/pdf", raw=raw)


def test_dispatcher_truncates_very_long_documents():
    long_text = "Skill number {}. " * 5000
    raw = make_pdf_bytes([long_text])
    text = extract_text(filename="resume.pdf", content_type="application/pdf", raw=raw)
    assert len(text) <= 15_000
