from mcp.server.fastmcp import FastMCP

from tools.banten import (
    search_banten as search_banten_data,
    get_banten as get_banten_data,
    get_components as get_components_data,
)

from tools.knowledge import (
    search_knowledge as search_knowledge_data,
)

mcp = FastMCP("BantenPedia MCP Server")


@mcp.tool()
def search_banten(
    query: str,
    wilayah: str | None = None,
    limit: int = 5
) -> list[dict]:
    """Search banten by name and optionally by regency."""
    return search_banten_data(query, wilayah, limit)


@mcp.tool()
def get_banten(banten_id: str) -> dict | None:
    """Get detailed information about a banten using its UUID."""
    return get_banten_data(banten_id)


@mcp.tool()
def get_components(banten_id: str) -> list[dict]:
    """Get the components and quantities of a banten."""
    return get_components_data(banten_id)


@mcp.tool()
def search_knowledge(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.70,
    source_type: str | None = None,
    use_hybrid: bool = False,
    expand_query: bool = False,
) -> list[dict]:
    """
    Search relevant knowledge from documents using RAG.

    Args:
        query:                User's natural language question.
        top_k:                Maximum number of results to return (1–20).
        similarity_threshold: Minimum cosine similarity score (0.0–1.0).
        source_type:          Optional filter — only from this source type
                              (e.g. 'book', 'article', 'transcript').
        use_hybrid:           If True, merges vector search with keyword search
                              using Reciprocal Rank Fusion.
        expand_query:         If True, generates alternative query phrasings
                              to improve recall (multi-query expansion).

    Returns:
        List of matching chunks with content, similarity, page_number, and source.
    """
    return search_knowledge_data(
        query=query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        source_type=source_type,
        use_hybrid=use_hybrid,
        expand_query=expand_query,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")