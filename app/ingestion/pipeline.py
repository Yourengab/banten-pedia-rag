"""
Document ingestion pipeline for BantenPedia.

Orchestrates the full pipeline (PRD §8):
  Document → Extract → Clean → Chunk → Embed → Upload

Usage:
    from ingestion.pipeline import ingest_file, ingest_bytes

    result = ingest_file(
        path="path/to/buku_banten.pdf",
        title="Buku Banten Bali",
        source_type="book",
        description="Dokumentasi lengkap banten Bali.",
    )
    print(f"Ingested {result.chunks_inserted} chunks (doc: {result.document_id})")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from config import CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS
from ingestion.extractor import extract_text
from ingestion.cleaner import clean_text
from ingestion.chunker import chunk_text
from ingestion.embedder import embed_texts
from ingestion.uploader import upload_document, UploadResult

logger = logging.getLogger(__name__)


def ingest_file(
    path: str | Path,
    title: str,
    source_type: str,
    description: str | None = None,
    file_url: str | None = None,
    chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> UploadResult:
    """
    Ingest a document from a local file path.

    Args:
        path:              Path to the source file.
        title:             Document title for Supabase.
        source_type:       'book', 'article', 'transcript', 'docx', etc.
        description:       Optional document description.
        file_url:          Optional URL to original file.
        chunk_size_tokens: Max tokens per chunk (default from config).
        overlap_tokens:    Token overlap between consecutive chunks.

    Returns:
        UploadResult with document_id, chunks_inserted, version.
    """
    path = Path(path)
    logger.info(f"[Pipeline] Extracting: {path.name}")
    raw_text = extract_text(path)
    return _run_pipeline(
        raw_text=raw_text,
        filename=path.name,
        title=title,
        source_type=source_type,
        description=description,
        file_url=file_url,
        chunk_size_tokens=chunk_size_tokens,
        overlap_tokens=overlap_tokens,
    )


def ingest_bytes(
    data: bytes,
    filename: str,
    title: str,
    source_type: str,
    description: str | None = None,
    file_url: str | None = None,
    chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> UploadResult:
    """
    Ingest a document from raw bytes (e.g., uploaded via FastAPI).

    Args:
        data:      Raw file bytes.
        filename:  Original filename (used for format detection).
        title:     Document title.
        source_type: 'book', 'article', etc.
        ...        Same as ingest_file.

    Returns:
        UploadResult with document_id, chunks_inserted, version.
    """
    logger.info(f"[Pipeline] Extracting bytes: {filename}")
    raw_text = extract_text(data, filename=filename)
    return _run_pipeline(
        raw_text=raw_text,
        filename=filename,
        title=title,
        source_type=source_type,
        description=description,
        file_url=file_url,
        chunk_size_tokens=chunk_size_tokens,
        overlap_tokens=overlap_tokens,
    )


def _run_pipeline(
    raw_text: str,
    filename: str,
    title: str,
    source_type: str,
    description: str | None,
    file_url: str | None,
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> UploadResult:
    """Internal pipeline runner."""

    # 1. Clean
    logger.info("[Pipeline] Cleaning text…")
    cleaned = clean_text(raw_text)

    if not cleaned:
        raise ValueError(f"No usable text extracted from '{filename}'.")

    # 2. Chunk
    logger.info("[Pipeline] Chunking…")
    chunks = chunk_text(
        text=cleaned,
        chunk_size_tokens=chunk_size_tokens,
        overlap_tokens=overlap_tokens,
    )

    if not chunks:
        raise ValueError(f"No chunks produced for '{filename}'.")

    logger.info(f"[Pipeline] {len(chunks)} chunks created.")

    # 3. Embed
    logger.info("[Pipeline] Generating embeddings…")
    texts = [chunk.content for chunk in chunks]
    embeddings = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    logger.info(f"[Pipeline] {len(embeddings)} embeddings generated.")

    # 4. Upload
    logger.info("[Pipeline] Uploading to Supabase…")
    result = upload_document(
        title=title,
        source_type=source_type,
        chunks=chunks,
        embeddings=embeddings,
        file_url=file_url,
        description=description,
    )

    logger.info(
        f"[Pipeline] Done. document_id={result.document_id}, "
        f"chunks={result.chunks_inserted}, version={result.version}"
    )
    return result
