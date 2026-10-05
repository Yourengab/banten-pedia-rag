"""
Text chunker for the BantenPedia ingestion pipeline.

Strategy (PRD §11):
  - Paragraph-based chunking.
  - Target: 500–1000 tokens per chunk.
  - Small overlap to preserve cross-paragraph context.
  - Never splits: title + first paragraph, component names + descriptions.
  - Preserves [PAGE:N] markers from PDF extractor for page-level citation.

Token estimation:
  ~4 characters per token (heuristic, avoids tiktoken dependency for MVP).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    content: str
    chunk_index: int
    page_number: int | None = None  # Phase 2: page-level citation


# Regex to detect [PAGE:N] markers injected by extractor.py
_PAGE_MARKER = re.compile(r"\[PAGE:(\d+)\]")

# Average chars per token (heuristic)
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def chunk_text(
    text: str,
    chunk_size_tokens: int = 750,
    overlap_tokens: int = 100,
) -> list[Chunk]:
    """
    Split cleaned text into overlapping paragraph-based chunks.

    Args:
        text:              Cleaned source text (may contain [PAGE:N] markers).
        chunk_size_tokens: Target maximum tokens per chunk.
        overlap_tokens:    Overlap with the previous chunk (in tokens).

    Returns:
        List of Chunk objects ordered by chunk_index.
    """
    if not text or not text.strip():
        return []

    # ── 1. Parse paragraphs and track page numbers ────────────────────────────
    paragraphs = _parse_paragraphs(text)

    if not paragraphs:
        return []

    # ── 2. Assemble chunks with overlap ───────────────────────────────────────
    chunks: list[Chunk] = []
    current_paras: list[tuple[str, int | None]] = []  # (text, page_number)
    current_tokens = 0
    chunk_size_chars = chunk_size_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    for para_text, page_num in paragraphs:
        para_tokens = _estimate_tokens(para_text)

        # If adding this paragraph would exceed the chunk size, flush.
        if current_tokens + para_tokens > chunk_size_tokens and current_paras:
            chunk = _build_chunk(current_paras, len(chunks))
            chunks.append(chunk)

            # Carry-over: keep the last N chars worth of paragraphs as overlap.
            current_paras = _trim_to_overlap(current_paras, overlap_chars)
            current_tokens = sum(
                _estimate_tokens(p) for p, _ in current_paras
            )

        current_paras.append((para_text, page_num))
        current_tokens += para_tokens

    # Flush remaining paragraphs.
    if current_paras:
        chunks.append(_build_chunk(current_paras, len(chunks)))

    return chunks


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_paragraphs(text: str) -> list[tuple[str, int | None]]:
    """
    Split text into (paragraph_text, page_number | None) tuples.
    [PAGE:N] markers from extractor.py are consumed to track the current page.
    """
    current_page: int | None = None
    paragraphs: list[tuple[str, int | None]] = []

    for block in re.split(r"\n{2,}", text):
        block = block.strip()
        if not block:
            continue

        # Check for page marker
        marker = _PAGE_MARKER.match(block)
        if marker:
            current_page = int(marker.group(1))
            # Strip the marker and use the rest as paragraph text
            block = block[marker.end():].strip()
            if not block:
                continue

        paragraphs.append((block, current_page))

    return paragraphs


def _build_chunk(
    paras: list[tuple[str, int | None]],
    index: int,
) -> Chunk:
    """Merge paragraphs into a single Chunk."""
    content = "\n\n".join(p for p, _ in paras)
    # Use the page number of the first paragraph in the chunk
    page_number = next((pg for _, pg in paras if pg is not None), None)
    return Chunk(content=content, chunk_index=index, page_number=page_number)


def _trim_to_overlap(
    paras: list[tuple[str, int | None]],
    overlap_chars: int,
) -> list[tuple[str, int | None]]:
    """
    Return the tail of `paras` whose total character count is ≤ overlap_chars.
    Always keeps at least the last paragraph to avoid empty overlap.
    """
    result: list[tuple[str, int | None]] = []
    total = 0

    for para in reversed(paras):
        para_len = len(para[0])
        if total + para_len > overlap_chars and result:
            break
        result.insert(0, para)
        total += para_len

    return result or [paras[-1]]
