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


# ══════════════════════════════════════════════════════════════════════════════
# AGENT
# ══════════════════════════════════════════════════════════════════════════════

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

        # ── 1. Retrieve knowledge via MCP ─────────────────────────────────────
        logger.info(f"[Agent] Calling search_knowledge for: {user_query!r}")

        knowledge_result = await mcp.call_tool(
            "search_knowledge",
            {
                "query":                user_query,
                "top_k":                top_k,
                "similarity_threshold": similarity_threshold,
                "source_type":          source_type,
                "use_hybrid":           use_hybrid,
                "expand_query":         expand_query,
            },
        )

        knowledge_chunks = _parse_mcp_result(knowledge_result)

        # ── 2. Search structured banten data ──────────────────────────────────
        logger.info(f"[Agent] Calling search_banten for: {user_query!r}")
        
        banten_result = await mcp.call_tool(
            "search_banten",
            {
                "query": user_query,
                "limit": 3,
            },
        )
        
        banten_data = _parse_mcp_result(banten_result)
        
        # ── 3. Log DB result status ───────────────────────────────────────────
        if not knowledge_chunks:
            logger.info(
                "[Agent] No document results found."
            )
        else:
            logger.info(f"[Agent] Found {len(knowledge_chunks)} chunks from documents.")
        
        if not banten_data:
            logger.info(
                "[Agent] No structured banten results found."
            )
        else:
            logger.info(f"[Agent] Found {len(banten_data)} banten matches.")

        # ── 4. Detect source conflicts (only meaningful when DB has results) ──
        conflict = detect_source_conflict(knowledge_chunks) if knowledge_chunks else False
        if conflict:
            logger.info("[Agent] Multiple document sources detected — surfacing differences.")

        # ── 5. Build context block ────────────────────────────────────────────
        # Returns NO_DB_CONTEXT_NOTE when empty, instructing Gemini to fall back
        # to its own knowledge rather than refusing to answer.
        context_block = build_context_block(knowledge_chunks, banten_data)

        # ── 6. Generate grounded answer with Gemini ───────────────────────────
        # Select appropriate system prompt based on intent
        from agent.agent_prompts import BANTEN_AGENT_PROMPT, GENERAL_AGENT_PROMPT
        system_prompt = BANTEN_AGENT_PROMPT if intent == "banten" else GENERAL_AGENT_PROMPT
        
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

def _parse_mcp_result(result) -> list[dict]:
    """Extract list of dicts from an MCP tool call result."""
    if result is None:
        return []

    # MCP results come back as a CallToolResult with .content list
    if hasattr(result, "content"):
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    parsed = json.loads(item.text)
                    # If parsed as a list, return directly.
                    if isinstance(parsed, list):
                        return parsed
                    # If parsed as a dict (single item result), wrap in list.
                    if isinstance(parsed, dict):
                        return [parsed]
                except (json.JSONDecodeError, TypeError):
                    pass
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
