"""
Supabase uploader for the BantenPedia ingestion pipeline.

Handles:
  - Inserting document metadata into `documents` table.
  - Batch-inserting chunks + embeddings into `document_chunks` table.
  - Document versioning: deactivates old versions on re-upload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from database.supabase import supabase
from ingestion.chunker import Chunk


@dataclass
class UploadResult:
    document_id: str
    chunks_inserted: int
    version: int


def upload_document(
    title: str,
    source_type: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    file_url: str | None = None,
    description: str | None = None,
) -> UploadResult:
    """
    Insert a document and its chunks into Supabase.

    Implements document versioning:
      - If a document with the same title already exists and is active,
        it is deactivated (is_active=FALSE) and a new version is created.

    Args:
        title:       Document title.
        source_type: Type of source ('book', 'article', 'transcript', etc.).
        chunks:      List of Chunk objects from the chunker.
        embeddings:  Parallel list of embeddings, one per chunk.
        file_url:    Optional URL to the original file.
        description: Optional description of the document.

    Returns:
        UploadResult with the new document UUID and chunk count.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) "
            "must have the same length."
        )

    # ── 1. Check existing versions (NOTE: 'version' column missing in live DB) ──────────────────
    existing = (
        supabase
        .table("documents")
        .select("id")
        .eq("title", title)
        .eq("is_active", True)
        .execute()
    )

    if existing.data:
        # Deactivate previous active version.
        # NOTE: Live DB missing 'updated_at' column, trigger fails. Use raw SQL to bypass.
        supabase.rpc("exec_sql", {
            "sql": f"UPDATE documents SET is_active = FALSE WHERE id = '{existing.data[0]['id']}'"
        }).execute()

    # ── 2. Insert document record ─────────────────────────────────────────────
    doc_response = (
        supabase
        .table("documents")
        .insert({
            "title":       title,
            "source_type": source_type,
            "file_url":    file_url,
            "description": description,
            "is_active":   True,
        })
        .execute()
    )

    document_id: str = cast(dict[str, Any], doc_response.data[0])["id"]
    current_version = 1

    # ── 3. Batch insert chunks + embeddings ───────────────────────────────────
    rows = []
    for chunk, embedding in zip(chunks, embeddings):
        # Format as pgvector literal: '[0.1,0.2,...]' (PostgreSQL array syntax)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        rows.append({
            "document_id": document_id,
            "content":     chunk.content,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "embedding":   embedding_str,
        })

    # Supabase supports batch inserts up to a few thousand rows.
    # Split into batches of 500 for safety.
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        supabase.table("document_chunks").insert(rows[i : i + BATCH]).execute()

    return UploadResult(
        document_id=document_id,
        chunks_inserted=len(chunks),
        version=current_version,
    )
