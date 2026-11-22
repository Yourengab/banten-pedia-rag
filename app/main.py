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
from typing import Annotated, Any, cast

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from postgrest import CountMethod
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_messages = []
    for error in exc.errors():
        # Field path (e.g., ['body', 'query'])
        loc = error.get("loc", [])
        field_name = loc[-1] if len(loc) > 1 else "root"
        msg = error.get("msg", "invalid input")
        error_messages.append(f"Field '{field_name}': {msg}")

    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": " | ".join(error_messages),
            "details": exc.errors(),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user's question.")
    session_id: str | None = Field(None, description="Optional chat session ID for context continuity.")
    session_name: str | None = Field(None, description="Optional name for new session if creating.")
    top_k: int = Field(DEFAULT_TOP_K, ge=1, le=20)
    similarity_threshold: float = Field(SIMILARITY_THRESHOLD, ge=0.0, le=1.0)
    source_type: str | None = Field(None, description="Filter by document type.")
    use_hybrid: bool = Field(False, description="Enable hybrid search.")
    expand_query: bool = Field(False, description="Enable multi-query expansion.")


class UpdateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, description="New session title/name.")


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    search_performed: bool
    conflict_detected: bool
    session_id: str
    options: list[dict] = []  # For disambiguation UI
    relations: list[dict] = []  # Structured relation data (komponen/bahan) for frontend


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


@app.get("/v1/models", tags=["Compat"])
def list_models():
    """OpenAI-compatible model discovery endpoint.
    
    Prevents 404s from OpenAI SDK wrappers (OpenWebUI, LiteLLM, Continue, etc.)
    that poll this endpoint to list available models.
    """
    from config import GEMINI_MODEL
    return {
        "object": "list",
        "data": [
            {
                "id": GEMINI_MODEL.strip(),
                "object": "model",
                "owned_by": "google",
            }
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(request: ChatRequest):
    """
    Send a question to the BantenPedia AI agent.

    The agent retrieves relevant knowledge from the repository and
    generates a grounded answer using Gemini. Supports chat sessions
    for context continuity.

    - If session_id is provided, chat history is used for context.
    - If session_id is not provided, a new session is created.
    """
    try:
        from chat.manager import create_session, add_message

        # Use provided session_id or create new one
        session_id = request.session_id
        if not session_id:
            from chat.manager import create_session
            # Auto-name from first query if not specified
            name = request.session_name or (request.query[:30] + "..." if len(request.query) > 30 else request.query)
            session_id = create_session(name=name)

        # Store user message before processing
        add_message(session_id, "user", request.query)

        result = await run_agent(
            user_query=request.query,
            session_id=session_id,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            source_type=request.source_type,
            use_hybrid=request.use_hybrid,
            expand_query=request.expand_query,
        )

        # Store assistant response
        add_message(session_id, "assistant", result.answer)

        return ChatResponse(
            answer=result.answer,
            sources=result.sources,
            search_performed=result.search_performed,
            conflict_detected=result.conflict_detected,
            session_id=session_id,
            options=result.options,
            relations=result.relations,
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
            .select("id", count=CountMethod.exact)
            .eq("document_id", document_id)
            .execute()
        )

        doc_dict = cast(dict[str, Any], doc)
        doc_dict["chunk_count"] = chunk_response.count or 0
        return doc_dict

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

        doc_dict = cast(dict[str, Any], doc_response.data[0])

        if not doc_dict["is_active"]:
            return {"message": "Document is already inactive.", "document_id": document_id}

        supabase.table("documents").update(
            {"is_active": False}
        ).eq("id", document_id).execute()

        return {
            "message": f"Document '{doc_dict['title']}' deactivated successfully.",
            "document_id": document_id,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[Documents] Deactivate error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# ENTITIES (Banten, Komponen, Bahan)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/banten/{banten_id}", tags=["Entities"])
def get_banten_detail(banten_id: str):
    """Get full detail of a banten entity, with its components."""
    try:
        from tools.banten import get_banten, get_components
        banten = get_banten(banten_id)
        if not banten: raise HTTPException(status_code=404, detail="Banten not found.")
        banten["components"] = get_components(banten_id)
        return {**banten, "type": "banten"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/komponen/{komponen_id}", tags=["Entities"])
def get_komponen_detail(komponen_id: str):
    """Get full detail of a component."""
    try:
        from tools.banten import get_komponen_detail
        data = get_komponen_detail(komponen_id)
        if not data: raise HTTPException(status_code=404, detail="Komponen not found.")
        return {**data, "type": "komponen"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/bahan/{bahan_id}", tags=["Entities"])
def get_bahan_detail(bahan_id: str):
    """Get full detail of a bahan."""
    try:
        from tools.banten import get_bahan_detail
        data = get_bahan_detail(bahan_id)
        if not data: raise HTTPException(status_code=404, detail="Bahan not found.")
        return {**data, "type": "bahan"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# CHAT SESSIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/chat/{session_id}/history", tags=["Chat"])
def get_chat_history(session_id: str):
    """Retrieve chat history for a given session."""
    try:
        from chat.manager import get_session_history
        history = get_session_history(session_id)
        return {"session_id": session_id, "messages": history}
    except Exception as exc:
        logger.error(f"[Chat] History error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/chat/sessions", tags=["Chat"])
def list_chat_sessions():
    """List all chat sessions."""
    try:
        from chat.manager import list_sessions
        sessions = list_sessions()
        return {"sessions": sessions}
    except Exception as exc:
        logger.error(f"[Chat] List sessions error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/chat/{session_id}", tags=["Chat"])
def update_chat_session(session_id: str, request: UpdateSessionRequest):
    """Update chat session name/title."""
    try:
        from chat.manager import update_session_name
        update_session_name(session_id, request.name)
        return {"message": "Session updated successfully.", "session_id": session_id, "name": request.name}
    except Exception as exc:
        logger.error(f"[Chat] Update session error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/chat/{session_id}", tags=["Chat"])
def delete_chat_session(session_id: str):
    """Delete a chat session and all its messages."""
    try:
        from chat.manager import delete_session
        delete_session(session_id)
        return {"message": "Session deleted successfully.", "session_id": session_id}
    except Exception as exc:
        logger.error(f"[Chat] Delete session error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

