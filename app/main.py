"""
BantenPedia FastAPI Application.

Routes:
  GET  /health          — liveness check
  POST /chat            — send a question, get an agent-generated answer
  POST /ingest          — upload and ingest a document into the RAG pipeline
  GET  /documents       — list all ingested documents
  GET  /documents/{id}  — get a specific document with its chunk count
  DELETE /documents/{id} — deactivate a document (soft delete / versioning)
  POST /search          — direct RAG search (bypass agent, for debugging)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import (
    DEFAULT_TOP_K,
    SIMILARITY_THRESHOLD,
    validate_config,
)
from agent.agent import run_agent
from ingestion.pipeline import ingest_bytes
from database.supabase import supabase

# Validate environment on startup
validate_config()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BantenPedia RAG API",
    description=(
        "Backend API for BantenPedia — a RAG-powered AI assistant "
        "for knowledge about Balinese banten (offerings)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user's question.")
    top_k: int = Field(DEFAULT_TOP_K, ge=1, le=20)
    similarity_threshold: float = Field(SIMILARITY_THRESHOLD, ge=0.0, le=1.0)
    source_type: str | None = Field(None, description="Filter by document type.")
    use_hybrid: bool = Field(False, description="Enable hybrid search.")
    expand_query: bool = Field(False, description="Enable multi-query expansion.")


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    search_performed: bool
    conflict_detected: bool


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(DEFAULT_TOP_K, ge=1, le=20)
    similarity_threshold: float = Field(SIMILARITY_THRESHOLD, ge=0.0, le=1.0)
    source_type: str | None = None
    use_hybrid: bool = False
    expand_query: bool = False


class IngestResponse(BaseModel):
    document_id: str
    chunks_inserted: int
    version: int
    message: str


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe."""
    return {"status": "ok", "service": "BantenPedia RAG API"}


# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(request: ChatRequest):
    """
    Send a question to the BantenPedia AI agent.

    The agent retrieves relevant knowledge from the repository and
    generates a grounded answer using Gemini.
    """
    try:
        result = await run_agent(
            user_query=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            source_type=request.source_type,
            use_hybrid=request.use_hybrid,
            expand_query=request.expand_query,
        )
        return ChatResponse(
            answer=result.answer,
            sources=result.sources,
            search_performed=result.search_performed,
            conflict_detected=result.conflict_detected,
        )
    except Exception as exc:
        logger.error(f"[Chat] Error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# DIRECT SEARCH (debug / evaluation)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/search", tags=["RAG"])
async def search_knowledge_endpoint(request: SearchRequest):
    """
    Direct RAG search — bypasses the LLM agent.
    Returns raw retrieval results for debugging or evaluation.
    """
    from tools.knowledge import search_knowledge

    try:
        results = search_knowledge(
            query=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            source_type=request.source_type,
            use_hybrid=request.use_hybrid,
            expand_query=request.expand_query,
        )
        return {"query": request.query, "results": results, "count": len(results)}
    except Exception as exc:
        logger.error(f"[Search] Error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# INGEST
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_document(
    file: UploadFile = File(..., description="Document file (.pdf, .txt, .md, .docx)"),
    title: Annotated[str, Form()] = "",
    source_type: Annotated[str, Form()] = "book",
    description: Annotated[str, Form()] = "",
    file_url: Annotated[str, Form()] = "",
):
    """
    Upload and ingest a document into the BantenPedia knowledge repository.

    Runs the full pipeline: Extract → Clean → Chunk → Embed → Upload.
    If a document with the same title already exists, a new version is created.
    """
    if not title.strip():
        title = file.filename or "Untitled Document"

    try:
        data = await file.read()
        result = ingest_bytes(
            data=data,
            filename=file.filename or "",
            title=title.strip(),
            source_type=source_type.strip() or "book",
            description=description.strip() or None,
            file_url=file_url.strip() or None,
        )
        return IngestResponse(
            document_id=result.document_id,
            chunks_inserted=result.chunks_inserted,
            version=result.version,
            message=(
                f"Document '{title}' ingested successfully. "
                f"{result.chunks_inserted} chunks created (version {result.version})."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"[Ingest] Error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/documents", tags=["Documents"])
def list_documents(
    active_only: bool = Query(True, description="If true, only return active documents."),
    source_type: str | None = Query(None, description="Filter by source type."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all documents in the knowledge repository.

    Supports filtering by source type and active/all versions.
    """
    try:
        query = (
            supabase
            .table("documents")
            .select("id, title, source_type, description, file_url, version, is_active, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )

        if active_only:
            query = query.eq("is_active", True)

        if source_type:
            query = query.eq("source_type", source_type)

        response = query.execute()
        return {"documents": response.data, "count": len(response.data)}

    except Exception as exc:
        logger.error(f"[Documents] List error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/documents/{document_id}", tags=["Documents"])
def get_document(document_id: str):
    """Get a single document with its chunk count."""
    try:
        doc_response = (
            supabase
            .table("documents")
            .select("*")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )

        if not doc_response.data:
            raise HTTPException(status_code=404, detail="Document not found.")

        doc = doc_response.data[0]

        # Count chunks
        chunk_response = (
            supabase
            .table("document_chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )

        doc["chunk_count"] = chunk_response.count or 0
        return doc

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[Documents] Get error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/documents/{document_id}", tags=["Documents"])
def deactivate_document(document_id: str):
    """
    Soft-delete a document by marking it as inactive.

    This is a versioning-aware operation: the document and its chunks
    remain in the database but will no longer appear in search results.
    Re-ingesting with the same title will create a new active version.
    """
    try:
        doc_response = (
            supabase
            .table("documents")
            .select("id, title, is_active")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )

        if not doc_response.data:
            raise HTTPException(status_code=404, detail="Document not found.")

        doc = doc_response.data[0]

        if not doc["is_active"]:
            return {"message": "Document is already inactive.", "document_id": document_id}

        supabase.table("documents").update(
            {"is_active": False}
        ).eq("id", document_id).execute()

        return {
            "message": f"Document '{doc['title']}' deactivated successfully.",
            "document_id": document_id,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[Documents] Deactivate error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))