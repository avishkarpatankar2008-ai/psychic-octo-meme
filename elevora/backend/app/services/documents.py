"""
Resume/JD text extraction.

Unlike ai_client.py, this module was genuinely tested against real files:
PyMuPDF and python-docx run entirely locally, so the sandbox this was built
in could generate a real PDF and a real DOCX, round-trip them through these
exact functions, and check the extracted text matches. See
tests/test_documents.py. This is the one part of Phase 5 with the same
confidence level as the Phase 1-2 database/auth logic — not an AI call, not
a browser API, just local file parsing.
"""

import io

import docx
import pymupdf

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024  # 8MB — resumes/JDs are text, not media
MAX_EXTRACTED_CHARS = 15_000  # keep extraction-call context (and cost) bounded

ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}

PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"  # docx is a zip archive


class DocumentParseError(Exception):
    """Raised for any file-validation or extraction failure — always safe
    to show the message to the user, it never contains extracted content."""


def _looks_like_pdf(raw: bytes) -> bool:
    return raw.startswith(PDF_MAGIC)


def _looks_like_docx(raw: bytes) -> bool:
    return raw.startswith(DOCX_MAGIC)


def extract_text_from_pdf(raw: bytes) -> str:
    if not _looks_like_pdf(raw):
        raise DocumentParseError(
            "This doesn't look like a real PDF file (wrong file signature) — "
            "it may be corrupted or renamed from another format."
        )
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as pdf:
            return "\n".join(page.get_text() for page in pdf)
    except Exception as exc:  # pymupdf raises its own exception types for malformed PDFs
        raise DocumentParseError(f"Couldn't read that PDF: {exc}") from exc


def extract_text_from_docx(raw: bytes) -> str:
    if not _looks_like_docx(raw):
        raise DocumentParseError(
            "This doesn't look like a real .docx file (wrong file signature) — "
            "it may be corrupted, an old .doc file, or renamed from another format."
        )
    try:
        document = docx.Document(io.BytesIO(raw))
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as exc:  # python-docx raises various errors for malformed zips/XML
        raise DocumentParseError(f"Couldn't read that Word document: {exc}") from exc


def extract_text(*, filename: str, content_type: str | None, raw: bytes) -> str:
    """Dispatches to the right parser based on declared content type, then
    validates that the bytes actually match (magic-byte check) rather than
    trusting the client-supplied header — a renamed .exe claiming to be a
    PDF fails here, not silently inside pymupdf."""
    if len(raw) == 0:
        raise DocumentParseError("The uploaded file is empty.")
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise DocumentParseError("That file is too large — resumes and JDs should be under 8MB.")

    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        text = extract_text_from_pdf(raw)
    elif (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or filename.lower().endswith(".docx")
    ):
        text = extract_text_from_docx(raw)
    else:
        raise DocumentParseError(
            f"Unsupported file type: {content_type or 'unknown'}. Upload a PDF or .docx file."
        )

    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        raise DocumentParseError(
            "Couldn't find any readable text in that file — it may be a scanned "
            "image with no text layer. OCR isn't supported in this phase."
        )

    truncated = cleaned[:MAX_EXTRACTED_CHARS]
    return truncated
