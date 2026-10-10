"""
Embedding generator for the BantenPedia ingestion pipeline.

Uses Gemini Embedding 2 (768 dimensions) via google-genai SDK.
Supports batched embedding to stay within API rate limits.
"""

from __future__ import annotations

import time

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    EMBEDDING_BATCH_SIZE,
)

_client = genai.Client(api_key=GEMINI_API_KEY)


def embed_texts(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """
    Generate embeddings for a list of text strings.

    Calls API once per text (Gemini embed_content processes one at a time).
    Adds delay between calls to respect rate limits.

    Args:
        texts:     List of text strings to embed.
        task_type: Gemini embedding task type.
                   Use "RETRIEVAL_DOCUMENT" for storage,
                   "RETRIEVAL_QUERY" for query-time search.

    Returns:
        List of 768-dimensional float vectors, one per input text.
    """
    if not texts:
        return []

    all_embeddings: list[list[float]] = []

    for i, text in enumerate(texts):
        response = _client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=[text],
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSION,
            ),
        )

        if not response.embeddings or response.embeddings[0].values is None:
            raise ValueError(
                f"Gemini returned no embedding for text index {i}"
            )

        all_embeddings.append(response.embeddings[0].values)

        # Brief pause to avoid rate limiting.
        if i + 1 < len(texts):
            time.sleep(0.1)

    return all_embeddings


def embed_query(query: str) -> list[float]:
    """
    Generate a single embedding for a search query.

    Uses RETRIEVAL_QUERY task type for best semantic search results.
    """
    results = embed_texts([query], task_type="RETRIEVAL_QUERY")
    return results[0]
