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
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from agent.prompts import (
    SYSTEM_PROMPT,
    NO_RESULT_RESPONSE,
    build_context_block,
    detect_source_conflict,
)
from mcp_client.client import BantenPediaMCPClient

logger = logging.getLogger(__name__)


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
    top_k: int = 5,
    similarity_threshold: float = 0.70,
    source_type: str | None = None,
    use_hybrid: bool = False,
    expand_query: bool = False,
) -> AgentResponse:
    """
    Run the BantenPedia AI agent for a user query.

    The agent:
    1. Calls search_knowledge() for document-based answers.
    2. Optionally calls search_banten() / get_components() for structured data.
    3. Constructs grounded context and generates a final answer via Gemini.

    Args:
        user_query:          The user's question.
        top_k:               Max retrieval results.
        similarity_threshold: Minimum similarity for inclusion.
        source_type:         Filter knowledge by document type.
        use_hybrid:          Enable hybrid search (vector + keyword).
        expand_query:        Enable multi-query expansion.

    Returns:
        AgentResponse with answer, sources, and metadata flags.
    """
    async with BantenPediaMCPClient() as mcp:
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

        # ── 2. Check if we have usable knowledge ──────────────────────────────
        if not knowledge_chunks:
            logger.info("[Agent] No relevant knowledge found.")
            return AgentResponse(
                answer=NO_RESULT_RESPONSE,
                sources=[],
                search_performed=True,
                conflict_detected=False,
            )

        # ── 3. Detect source conflicts ────────────────────────────────────────
        conflict = detect_source_conflict(knowledge_chunks)
        if conflict:
            logger.info("[Agent] Multiple sources detected — surfacing differences.")

        # ── 4. Build context block ────────────────────────────────────────────
        context_block = build_context_block(knowledge_chunks)

        # ── 5. Generate grounded answer with Gemini ───────────────────────────
        answer = _generate_answer(
            user_query=user_query,
            context_block=context_block,
            conflict=conflict,
        )

        # ── 6. Collect unique sources for response ────────────────────────────
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
    conflict: bool,
) -> str:
    """Generate a grounded answer using Gemini with retrieved context."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    conflict_note = (
        "\n\nCATATAN: Ditemukan perbedaan antar sumber. "
        "Tolong tampilkan informasi dari setiap sumber secara terpisah."
        if conflict else ""
    )

    user_message = (
        f"{context_block}"
        f"{conflict_note}\n\n"
        f"Pertanyaan pengguna: {user_query}"
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,  # Low temperature for factual grounding
        ),
    )

    return response.text.strip()


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
                    if isinstance(parsed, list):
                        return parsed
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
                "version":     source.get("version"),
            })

    return sources
