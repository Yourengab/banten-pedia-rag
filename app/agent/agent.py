"""
BantenPedia AI Agent.

Implements the full query flow (PRD §25):
  User → Agent → MCP Client → search_knowledge() / search_banten() / get_components()
               → Gemini (grounded generation) → Final Answer

The agent uses the Gemini SDK with tool calling, routing through the
MCP server for all knowledge and banten data access.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from .prompts import (
    SYSTEM_PROMPT,
    NO_DB_CONTEXT_NOTE,
    build_context_block,
    detect_source_conflict,
)
from mcp_client.client import BantenPediaMCPClient

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# INTENT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def _detect_intent(query: str) -> str:
    """
    Detect query intent to route to appropriate agent.
    Returns one of: 'casual', 'banten', 'general', 'fallback'.
    """
    lowered = query.lower().strip()
    
    # Casual greetings
    casual_keywords = [
        "halo", "hai", "selamat", "apa kabar", "pagi", "siang", "sore", "malam",
        "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    ]
    if any(k in lowered for k in casual_keywords):
        return "casual"
    
    # Banten cultural keywords
    banten_keywords = [
        "penjor", "banten", "galungan", "kuningan", "ngaben", "odalan", "upacara",
        "taksu", "bali", "hindu", "offering", "bantenpedia",
    ]
    if any(k in lowered for k in banten_keywords):
        return "banten"
    
    # General knowledge – common question patterns
    general_keywords = ["where", "what", "who", "when", "how", "population", "capital", "country", "city"]
    if any(k in lowered for k in general_keywords):
        return "general"
    
    return "fallback"



@dataclass
class AgentResponse:
    answer: str
    sources: list[dict] = field(default_factory=list)
    search_performed: bool = False
    conflict_detected: bool = False
    options: list[dict] = field(default_factory=list)  # For disambiguation UI


# ══════════════════════════════════════════════════════════════════════════════
# AGENT
# ══════════════════════════════════════════════════════════════════════════════

# ── Constants ──────────────────────────────────────────────────────────────────
STOPWORDS = {
    "apa", "itu", "apa itu", "jelaskan", "tentang", "banten", "upakara",
    "bahan", "komponen", "sarana", "adalah", "maksud", "arti", "makna",
    "dari", "yang", "untuk", "bagaimana", "cara", "siapa", "dimana"
}

# ── Query Normalization ──────────────────────────────────────────────────────

def normalize_query(text: str) -> str:
    """Lowercase, trim, remove punctuation and common stopwords."""
    # Lowercase & strip
    text = text.lower().strip()
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Tokenize
    tokens = text.split()
    # Filter stopwords
    filtered = [t for t in tokens if t not in STOPWORDS]
    
    result = " ".join(filtered)
    return result if result else text

def _extract_search_keywords(user_query: str) -> dict:
    """
    Extract structured entity keywords using Gemini.
    Returns: {"core": str, "variants": list, "is_bali_topic": bool}
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = (
        "Kamu adalah pakar ekstraksi informasi untuk sistem pencarian BantenPedia.\n"
        "Tugas: Ekstrak subjek utama dari pertanyaan pengguna tentang budaya/banten Bali.\n\n"
        "ATURAN:\n"
        "1. 'core': Kata kunci murni (noun) tanpa imbuhan generik.\n"
        "2. 'variants': Maksimal 3 variasi ejaan/nama yang masuk akal.\n"
        "3. 'is_bali_topic': Boolean, apakah berkaitan dengan budaya/agama/upacara Bali.\n"
        "4. Istilah ambigu (misal 'kojong') harus dipahami dalam konteks Banten Bali.\n\n"
        "OUTPUT HARUS JSON FORMAT:\n"
        "{\n"
        "  \"core\": \"...\",\n"
        "  \"variants\": [\"...\"],\n"
        "  \"is_bali_topic\": true\n"
        "}\n\n"
        f"Pertanyaan: {user_query}"
    )
    
    # Fallback structure
    normalized = normalize_query(user_query)
    fallback = {"core": normalized, "variants": [normalized], "is_bali_topic": True}
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text or ""
        # Handle potential code fences
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(text)
        # Validate required keys
        if not all(k in data for k in ["core", "variants", "is_bali_topic"]):
            return fallback
            
        logger.info(f"[Agent] Structured keywords: {data}")
        return data
    except Exception as exc:
        logger.warning(f"[Agent] Keyword extraction failed, using fallback: {exc}")
        return fallback


async def run_agent(
    user_query: str,
    session_id: str | None = None,
    top_k: int = 5,
    similarity_threshold: float = 0.70,
    source_type: str | None = None,
    use_hybrid: bool = True,
    expand_query: bool = True,
) -> AgentResponse:
    """
    Run the BantenPedia AI agent for a user query.

    The agent:
    1. Detects query intent (casual, banten, general, fallback).
    2. Retrieves chat history if session_id provided.
    3. Calls search_knowledge() for document-based answers.
    4. Calls search_banten() + get_components() for structured data.
    5. Constructs grounded context and generates a final answer via Gemini.

    Args:
        user_query:          The user's question.
        session_id:          Optional chat session ID for context continuity.
        top_k:               Max retrieval results.
        similarity_threshold: Minimum similarity for inclusion.
        source_type:         Filter knowledge by document type.
        use_hybrid:          Enable hybrid search (vector + keyword).
        expand_query:        Enable multi-query expansion.

    Returns:
        AgentResponse with answer, sources, and metadata flags.
    """
    # ── 0. Detect intent ──────────────────────────────────────────────────────
    intent = _detect_intent(user_query)
    logger.info(f"[Agent] Detected intent: {intent}")
    
    # For casual/fallback intents, handle directly without RAG search
    if intent == "casual":
        from agent.agent_prompts import CASUAL_AGENT_PROMPT
        answer = _generate_answer(
            user_query=user_query,
            context_block="",
            system_prompt=CASUAL_AGENT_PROMPT,
            chat_history="",
            conflict=False,
        )
        return AgentResponse(
            answer=answer,
            sources=[],
            search_performed=False,
            conflict_detected=False,
        )
    
    # For fallback intent, explain limitation
    if intent == "fallback":
        from agent.agent_prompts import FALLBACK_AGENT_PROMPT
        answer = _generate_answer(
            user_query=user_query,
            context_block="",
            system_prompt=FALLBACK_AGENT_PROMPT,
            chat_history="",
            conflict=False,
        )
        return AgentResponse(
            answer=answer,
            sources=[],
            search_performed=False,
            conflict_detected=False,
        )
    
    # For banten/general: perform RAG search
    async with BantenPediaMCPClient() as mcp:
        # ── 0. Retrieve chat history if session exists ────────────────────────
        chat_history_context = ""
        if session_id:
            from chat.manager import get_session_context
            chat_history_context = get_session_context(session_id, limit=10)
            if chat_history_context:
                logger.info(f"[Agent] Loaded chat history for session: {session_id}")

        # ── 1. Retrieve knowledge via MCP ─────────────────────────────────────
        chat_history_context = ""
        if session_id:
            from chat.manager import get_session_context
            chat_history_context = get_session_context(session_id, limit=10)
            if chat_history_context:
                logger.info(f"[Agent] Loaded chat history for session: {session_id}")

        # ── 1. Extract Keywords & Search Structured DB ────────────────────────
        query_data = _extract_search_keywords(user_query)
        
        # Check domain guardrail
        if not query_data.get("is_bali_topic", True):
            logger.info(f"[Agent] Non-Bali topic detected: {user_query!r}")
            return AgentResponse(
                answer="Maaf, saya hanya dapat membantu menjawab pertanyaan seputar budaya, upacara, dan banten Bali. Silakan ajukan pertanyaan yang berkaitan dengan topik tersebut.",
                sources=[],
                search_performed=False,
                conflict_detected=False,
            )

        logger.info(f"[Agent] Calling search_entities for: {query_data['core']!r}")
        
        banten_result = await mcp.call_tool(
            "search_entities",
            {
                "query_data": query_data,
                "limit": 5,
            },
        )
        
        banten_data_wrapper = _parse_mcp_result(banten_result)
        
        # Check if structured DB returned results
        if isinstance(banten_data_wrapper, dict):
            banten_data = banten_data_wrapper.get("data", [])
            is_ambiguous = banten_data_wrapper.get("ambiguous", False)
            top_score = banten_data_wrapper.get("top_score", 0.0)
            options = banten_data_wrapper.get("options", [])
        else:
            banten_data = banten_data_wrapper if isinstance(banten_data_wrapper, list) else []
            is_ambiguous = False
            top_score = 0.0
            options = []

        knowledge_chunks = []
        # Logic: If high score match, we can still complement with RAG
        # If low/no match, we do RAG.
        # If both fail, we refuse.
        
        if top_score < 0.8: # If not a perfect DB match, look into documents
            logger.info(f"[Agent] Calling search_knowledge to complement or find data.")
            knowledge_result = await mcp.call_tool(
                "search_knowledge",
                {
                    "query":                query_data['core'],
                    "top_k":                top_k,
                    "similarity_threshold": similarity_threshold,
                    "source_type":          source_type,
                    "use_hybrid":           use_hybrid,
                    "expand_query":         expand_query,
                },
            )
            knowledge_chunks = _parse_mcp_to_list(knowledge_result)

        # ── 3. Log result status & Logging ───────────────────────────────────
        path_taken = "db_high"
        if is_ambiguous: path_taken = "db_ambiguous"
        elif knowledge_chunks: path_taken = "rag"
        elif not banten_data and not knowledge_chunks: path_taken = "refused"
        
        # Log to search_misses (async implementation would be better, but doing it here for now)
        try:
            supabase.table("search_misses").insert({
                "query_original": user_query,
                "query_normalized": query_data.get("core"),
                "core_keyword": query_data.get("core"),
                "path_taken": path_taken,
                "top_score": top_score
            }).execute()
        except:
            pass

        if path_taken == "refused":
            return AgentResponse(
                answer=f"Maaf, informasi tentang '{user_query}' belum tersedia di BantenPedia. Untuk menghindari informasi yang keliru tentang adat Bali, saya tidak menjawab dari sumber yang belum terverifikasi.",
                sources=[],
                search_performed=True,
                conflict_detected=False,
            )
        
        # ── 4. Detect source conflicts (only meaningful when DB has results) ──
        conflict = detect_source_conflict(knowledge_chunks) if knowledge_chunks else False
        if conflict:
            logger.info("[Agent] Multiple document sources detected — surfacing differences.")

        # ── 5. Build context block ────────────────────────────────────────────
        context_block = build_context_block(knowledge_chunks, banten_data)

        # ── 6. Generate grounded answer with Gemini ───────────────────────────
        from agent.agent_prompts import BANTEN_AGENT_PROMPT, GENERAL_AGENT_PROMPT
        system_prompt = BANTEN_AGENT_PROMPT if intent == "banten" else GENERAL_AGENT_PROMPT
        
        # Add ambiguity hint to prompt if needed
        if is_ambiguous:
            system_prompt += "\n\n⚠️ PENTING: Hasil pencarian ambigu. Berikan daftar opsi yang tersedia kepada pengguna agar mereka memilih."

        answer = _generate_answer(
            user_query=user_query,
            context_block=context_block,
            system_prompt=system_prompt,
            chat_history=chat_history_context,
            conflict=conflict,
        )

        # ── 7. Collect unique sources for response ────────────────────────────
        sources = _collect_sources(knowledge_chunks)

        return AgentResponse(
            answer=answer,
            sources=sources,
            search_performed=True,
            conflict_detected=conflict,
            options=options,
        )


def run_agent_sync(user_query: str, **kwargs) -> AgentResponse:
    """Synchronous wrapper around run_agent for use in non-async contexts."""
    return asyncio.run(run_agent(user_query, **kwargs))


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _generate_answer(
    user_query: str,
    context_block: str,
    system_prompt: str,
    chat_history: str = "",
    conflict: bool = False,
) -> str:
    """Generate a grounded answer using Gemini with retrieved context."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    conflict_note = (
        "\n\nCATATAN: Ditemukan perbedaan antar sumber. "
        "Tolong tampilkan informasi dari setiap sumber secara terpisah."
        if conflict else ""
    )

    # Prepend chat history if available
    history_prefix = f"{chat_history}\n\n" if chat_history else ""

    user_message = (
        f"{history_prefix}"
        f"{context_block}"
        f"{conflict_note}\n\n"
        f"Pertanyaan pengguna: {user_query}"
    )

    # Retry logic for transient API failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,  # Low temperature for factual grounding
                ),
            )
            return (response.text or "").strip()
        except Exception as exc:
            if attempt < max_retries - 1:
                logger.warning(f"[Agent] Gemini API error (attempt {attempt + 1}/{max_retries}): {exc}")
                import time
                time.sleep(1 * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"[Agent] Gemini API failed after {max_retries} attempts: {exc}")
                raise
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_mcp_result(result) -> Any:
    """Extract list of dicts OR dict (if structured) from an MCP tool call result."""
    if result is None:
        return []

    # MCP results come back as a CallToolResult with .content list
    if hasattr(result, "content"):
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    parsed = json.loads(item.text)
                    return parsed # Return directly as dict/list
                except (json.JSONDecodeError, TypeError):
                    pass
    return []


def _parse_mcp_to_list(result) -> list[dict]:
    """Helper to specifically ensure result is a list of dicts for RAG/Knowledge."""
    data = _parse_mcp_result(result)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _collect_sources(chunks: list[dict]) -> list[dict]:
    """Collect unique sources from retrieval results."""
    seen: set[str] = set()
    sources: list[dict] = []

    for chunk in chunks:
        source = chunk.get("source", {})
        key = str(source.get("title", "")) + str(source.get("source_type", ""))
        if key not in seen:
            seen.add(key)
            sources.append({
                "title":       source.get("title"),
                "source_type": source.get("source_type"),
                "file_url":    source.get("file_url"),
            })

    return sources
