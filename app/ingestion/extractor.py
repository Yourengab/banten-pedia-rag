"""
Text extractor for the BantenPedia ingestion pipeline.

Supports:
  - Plain text (.txt)
  - Markdown (.md)
  - PDF (.pdf) via pypdf
  - DOCX (.docx) via python-docx

OCR is intentionally out of scope (as per PRD §9).
"""

import io
import os
from pathlib import Path


def extract_text(source: str | Path | bytes, filename: str = "") -> str:
    """
    Extract plain text from a file path, URL, or raw bytes.

    Args:
        source:   A filesystem path, a URL string, or raw file bytes.
        filename: Original filename (used to detect format when source is bytes).

    Returns:
        Extracted text as a single string.

    Raises:
        ValueError: If the file format is unsupported.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        ext = path.suffix.lower()
        raw = path.read_bytes()
    else:
        # bytes were passed directly
        raw = source
        ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md", ".markdown"):
        return raw.decode("utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf(raw)

    if ext in (".docx",):
        return _extract_docx(raw)

    raise ValueError(
        f"Unsupported file type: '{ext}'. "
        "Supported formats: .txt, .md, .pdf, .docx"
    )


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(raw: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "pypdf is required for PDF extraction. "
            "Install it with: pip install pypdf"
        ) from exc

    reader = PdfReader(io.BytesIO(raw))
    pages: list[str] = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            # Prepend page marker so chunker can preserve page_number
            pages.append(f"[PAGE:{page_num}]\n{text}")

    return "\n\n".join(pages)


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _extract_docx(raw: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import docx
    except ImportError as exc:
        raise ImportError(
            "python-docx is required for DOCX extraction. "
            "Install it with: pip install python-docx"
        ) from exc

    document = docx.Document(io.BytesIO(raw))
    paragraphs = [para.text for para in document.paragraphs if para.text.strip()]
    return "\n\n".join(paragraphs)
