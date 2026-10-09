"""
Knowledge retrieval tool for BantenPedia RAG.

Implements:
  - Semantic vector search via pgvector (PRD §14–16)
  - Similarity threshold filtering (PRD §17)
  - Source attribution and metadata (PRD §20)
  - Hybrid search: vector + keyword (PRD §31 / Future Dev)
  - Metadata filtering: source_type (PRD §31)
  - Score-based reranking stub (PRD §31)
  - Multi-query expansion (PRD §31)
  - Graceful no-result handling (PRD §21)
"""

from __future__ import annotations

import logging
import re
from typing import Any, cast

from database.supabase import supabase
from config import (
    GEMINI_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    DEFAULT_TOP_K,
    SIMILARITY_THRESHOLD,
)

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def search_knowledge(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    source_type: str | None = None,
    use_hybrid: bool = False,
    expand_query: bool = False,
) -> list[dict]:
    """
    Retrieve relevant knowledge chunks for a user query.

    Args:
        query:               The user's natural language question.
        top_k:               Maximum number of results (1–20).
        similarity_threshold: Minimum cosine similarity to include (0–1).
        source_type:         Optional filter — only return chunks from this
                             document source type (e.g. 'book').
        use_hybrid:          If True, merge vector results with keyword search.
        expand_query:        If True, generate additional sub-queries to
                             improve recall (multi-query expansion).

    Returns:
        List of result dicts, each with:
          content, chunk_index, page_number, similarity, document_id, source.
        Returns [] if no relevant results found above threshold.
    """
    if not query or not query.strip():
        return []

    top_k = max(1, min(top_k, 20))
    query = query.strip()

    # ── Multi-query expansion ─────────────────────────────────────────────────
    queries = [query]
    if expand_query:
        queries = _expand_queries(query)
        logger.info(f"[Knowledge] Expanded to {len(queries)} queries.")

    # ── Retrieve candidates per query, then merge ─────────────────────────────
    candidate_map: dict[str, dict] = {}  # chunk_id → result_dict

    for q in queries:
        embedding = _embed_query(q)

        vector_results = _vector_search(
            embedding=embedding,
            top_k=top_k * 2,  # Over-fetch for reranking headroom
            similarity_threshold=similarity_threshold,
            source_type=source_type,
        )

        if use_hybrid:
            keyword_results = _keyword_search(q, top_k=top_k)
            merged = _merge_hybrid(vector_results, keyword_results)
        else:
            merged = vector_results

        for r in merged:
            cid = str(r.get("id") or r.get("document_id", "")) + "_" + str(r.get("chunk_index", ""))
            if cid not in candidate_map or r["similarity"] > candidate_map[cid]["similarity"]:
                candidate_map[cid] = r

    candidates = list(candidate_map.values())

    if not candidates:
        logger.info(f"[Knowledge] No results above threshold {similarity_threshold}.")
        return []

    # ── Reranking (score-based; extendable to a reranker model) ──────────────
    ranked = _rerank(candidates, top_k=top_k)

    # ── Enrich with document metadata ────────────────────────────────────────
    enriched = _attach_document_metadata(ranked)

    return enriched


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING
# ══════════════════════════════════════════════════════════════════════════════

def _embed_query(query: str) -> list[float]:
    """Embed the query with RETRIEVAL_QUERY task type."""
    response = _gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIMENSION,
        ),
    )
    if not response.embeddings:
        raise ValueError("Gemini did not return embeddings for the query.")
    values = response.embeddings[0].values
    if values is None:
        raise ValueError("Gemini returned an embedding with no values.")
    return list(values)


# ══════════════════════════════════════════════════════════════════════════════
# VECTOR SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def _vector_search(
    embedding: list[float],
    top_k: int,
    similarity_threshold: float,
    source_type: str | None,
) -> list[dict]:
    """Call the appropriate Supabase RPC for vector similarity search."""

    if source_type:
        response = supabase.rpc(
            "match_document_chunks_filtered",
            {
                "query_embedding":      embedding,
                "match_count":          top_k,
                "similarity_threshold": similarity_threshold,
                "filter_source_type":   source_type,
            },
        ).execute()
    else:
        response = supabase.rpc(
            "match_document_chunks",
            {
                "query_embedding":      embedding,
                "match_count":          top_k,
                "similarity_threshold": similarity_threshold,
            },
        ).execute()

    return cast(list[dict[str, Any]], response.data) if response.data else []


# ══════════════════════════════════════════════════════════════════════════════
# KEYWORD SEARCH (Hybrid)
# ══════════════════════════════════════════════════════════════════════════════

def _keyword_search(query: str, top_k: int) -> list[dict]:
    """
    Full-text / ILIKE keyword search on document_chunks.content.

    This provides BM25-like recall for exact term matching.
    Results are given a nominal similarity of 0.60 so they can be merged
    with vector results and ranked by score.
    """
    terms = [t for t in re.split(r"\s+", query.strip()) if len(t) > 2]
    if not terms:
        return []

    # Use the longest term as the primary search term to get the most specific results.
    primary_term = max(terms, key=len)

    try:
        response = (
            supabase
            .table("document_chunks")
            .select("id, document_id, content, chunk_index, page_number")
            .ilike("content", f"%{primary_term}%")
            .limit(top_k)
            .execute()
        )
    except Exception as exc:
        logger.warning(f"[Knowledge] Keyword search failed: {exc}")
        return []

    results = []
    for row in (response.data or []):
        row_dict = cast(dict[str, Any], row)
        results.append({
            "id":          row_dict.get("id"),
            "document_id": row_dict.get("document_id"),
            "content":     row_dict.get("content"),
            "chunk_index": row_dict.get("chunk_index"),
            "page_number": row_dict.get("page_number"),
            "similarity":  0.60,  # nominal score for keyword matches
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# HYBRID MERGE
# ══════════════════════════════════════════════════════════════════════════════

def _merge_hybrid(
    vector_results: list[dict],
    keyword_results: list[dict],
) -> list[dict]:
    """
    Merge vector and keyword results using Reciprocal Rank Fusion (RRF).

    RRF score = Σ 1 / (k + rank_i), k=60
    This produces a stable merged ranking without needing aligned scores.
    """
    K = 60
    scores: dict[str, float] = {}
    records: dict[str, dict] = {}

    def _key(r: dict) -> str:
        return str(r.get("id") or "") + "_" + str(r.get("chunk_index", ""))

    for rank, result in enumerate(vector_results, start=1):
        k = _key(result)
        scores[k] = scores.get(k, 0.0) + 1.0 / (K + rank)
        records[k] = result

    for rank, result in enumerate(keyword_results, start=1):
        k = _key(result)
        scores[k] = scores.get(k, 0.0) + 1.0 / (K + rank)
        if k not in records:
            records[k] = result

    # Overwrite similarity with RRF score (normalised to 0–1 range for display)
    max_score = max(scores.values()) if scores else 1.0
    merged = []
    for k, score in scores.items():
        record = records[k].copy()
        record["similarity"] = round(score / max_score, 4)
        merged.append(record)

    return sorted(merged, key=lambda r: r["similarity"], reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# RERANKING
# ══════════════════════════════════════════════════════════════════════════════

def _rerank(results: list[dict], top_k: int) -> list[dict]:
    """
    Score-based reranking.

    Currently: sort by similarity descending, take top_k.

    This function is a stub for a future reranker model integration.
    To upgrade to a cross-encoder reranker, replace the body of this function.
    The function signature and downstream callers remain unchanged.
    """
    ranked = sorted(results, key=lambda r: r.get("similarity", 0.0), reverse=True)
    return ranked[:top_k]


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-QUERY EXPANSION
# ══════════════════════════════════════════════════════════════════════════════

def _expand_queries(query: str) -> list[str]:
    """
    Generate 2–3 alternative phrasings of the query to improve recall.

    Uses Gemini to rewrite the query in different ways while preserving intent.
    Falls back to the original query if generation fails.
    """
    from google import genai as _genai

    prompt = (
        "You are a search query expansion assistant for a Balinese cultural knowledge base.\n"
        "Given the following user query, generate 2 alternative search queries in the same language "
        "(Indonesian or Balinese) that would retrieve relevant documents. "
        "Each alternative should use different vocabulary or framing.\n"
        "Output ONLY the alternative queries, one per line. No explanations.\n\n"
        f"Original query: {query}"
    )

    try:
        client = _genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()
        alternatives = [line.strip() for line in text.splitlines() if line.strip()]
        # Prepend the original query so it's always included.
        return [query] + alternatives[:2]
    except Exception as exc:
        logger.warning(f"[Knowledge] Query expansion failed, using original: {exc}")
        return [query]


# ══════════════════════════════════════════════════════════════════════════════
# METADATA ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

def _attach_document_metadata(chunks: list[dict]) -> list[dict]:
    """
    Fetch document metadata for each chunk and attach as `source` field.
    """
    document_ids = list({
        c["document_id"] for c in chunks if c.get("document_id")
    })

    documents_by_id: dict[str, dict[str, Any]] = {}

    if document_ids:
        docs_response = (
            supabase
            .table("documents")
            .select("id, title, source_type, file_url, description, version")
            .in_("id", document_ids)
            .execute()
        )
        documents_by_id = {
            cast(dict[str, Any], d)["id"]: cast(dict[str, Any], d)
            for d in (docs_response.data or [])
        }

    results = []
    for chunk in chunks:
        doc_id = chunk.get("document_id")
        doc: dict[str, Any] = documents_by_id.get(doc_id, {}) if doc_id is not None else {}  # type: ignore[arg-type]
        results.append({
            "content":     chunk.get("content"),
            "chunk_index": chunk.get("chunk_index"),
            "page_number": chunk.get("page_number"),   # Page-level citation
            "similarity":  chunk.get("similarity"),
            "document_id": chunk.get("document_id"),
            "source": {
                "title":       doc.get("title"),
                "source_type": doc.get("source_type"),
                "file_url":    doc.get("file_url"),
                "description": doc.get("description"),
                "version":     doc.get("version"),     # Document versioning
            },
        })

    return results