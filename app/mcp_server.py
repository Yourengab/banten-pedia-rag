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
    top_k: int = 5
) -> list[dict]:
    """Search relevant knowledge from documents using RAG."""
    return search_knowledge_data(query, top_k)


if __name__ == "__main__":
    mcp.run(transport="stdio")