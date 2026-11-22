from mcp.server.mcpserver import MCPServer

from tools.banten import (
    search_banten as search_banten_data,
    search_entities as search_entities_data,
    get_banten as get_banten_data,
    get_components as get_components_data,
    get_full_relation_tree as get_full_relation_tree_data,
)

from tools.knowledge import (
    search_knowledge as search_knowledge_data,
)

mcp = MCPServer("BantenPedia MCP Server")


@mcp.tool()
def search_entities(
    query_data: dict,
    limit: int = 5
) -> dict:
    """
    Search banten, komponen, and bahan with fuzzy matching and disambiguation.
    query_data should be: {"core": str, "variants": list, "is_bali_topic": bool}
    """
    return search_entities_data(query_data, limit)


@mcp.tool()
def search_banten(
    query: str,
    wilayah: str | None = None,
    limit: int = 5
) -> dict:
    """Search banten by name and optionally by regency (legacy)."""
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
def get_full_relation_tree(banten_id: str, max_depth: int = 3) -> list[dict]:
    """
    Recursively fetch all components and their materials down the hierarchy.
    Returns a flat list of all related entities with hierarchy info.
    
    Args:
        banten_id: Root entity ID (banten or komponen)
        max_depth: Maximum recursion depth (default 3: banten -> komponen -> bahan)
    
    Returns:
        List of dicts with id, name, type, description, level, parent_name, notes
    """
    return get_full_relation_tree_data(banten_id, max_depth)


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