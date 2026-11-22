"""
Google Search tool for BantenPedia.
Uses Serper API (serper.dev) as a reliable Google Search API wrapper.
"""

import httpx
import logging
from typing import Any
from config import SERPER_API_KEY

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


async def google_search(query: str, num_results: int = 5) -> list[dict[str, Any]]:
    """
    Search Google via Serper API and return structured results.
    
    Args:
        query: Search query
        num_results: Number of results to return (max 10)
    
    Returns:
        List of dicts with keys: title, link, snippet
    """
    if not SERPER_API_KEY:
        logger.warning("[Internet] SERPER_API_KEY not set, skipping Google Search")
        return []

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": min(num_results, 10),
        "gl": "id",  # Indonesia locale
        "hl": "id",  # Indonesian language
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(SERPER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        organic = data.get("organic", [])
        results = []
        for item in organic[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results

    except httpx.HTTPStatusError as exc:
        logger.error(f"[Internet] Serper API error: {exc.response.status_code} - {exc.response.text}")
        return []
    except Exception as exc:
        logger.error(f"[Internet] Google search failed: {exc}")
        return []


def google_search_sync(query: str, num_results: int = 5) -> list[dict[str, Any]]:
    """Synchronous wrapper for google_search."""
    import asyncio
    return asyncio.run(google_search(query, num_results))