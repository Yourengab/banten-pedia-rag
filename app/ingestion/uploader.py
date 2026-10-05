"""
Supabase uploader for the BantenPedia ingestion pipeline.

Handles:
  - Inserting document metadata into `documents` table.
  - Batch-inserting chunks + embeddings into `document_chunks` table.
  - Document versioning: deactivates old versions on re-upload.
"""

from __future__ import annotations

from dataclasses import dataclass

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

    # ── 1. Check existing versions ────────────────────────────────────────────
    existing = (
        supabase
        .table("documents")
        .select("id, version")
        .eq("title", title)
        .eq("is_active", True)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )

    current_version = 1
    if existing.data:
        prev = existing.data[0]
        current_version = prev["version"] + 1

        # Deactivate the previous active version.
        supabase.table("documents").update(
            {"is_active": False}
        ).eq("id", prev["id"]).execute()

    # ── 2. Insert document record ─────────────────────────────────────────────
    doc_response = (
        supabase
        .table("documents")
        .insert({
            "title":       title,
            "source_type": source_type,
            "file_url":    file_url,
            "description": description,
            "version":     current_version,
            "is_active":   True,
        })
        .execute()
    )

    document_id: str = doc_response.data[0]["id"]

    # ── 3. Batch insert chunks + embeddings ───────────────────────────────────
    rows = []
    for chunk, embedding in zip(chunks, embeddings):
        rows.append({
            "document_id": document_id,
            "content":     chunk.content,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "embedding":   embedding,
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
