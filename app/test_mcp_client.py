# import asyncio
# import sys
# from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent))

# from mcp_client.client import BantenPediaMCPClient


# async def main():
#     async with BantenPediaMCPClient() as client:
#         # Check available MCP tools.
#         tools = await client.list_tools()

#         print("\nAvailable MCP Tools:")
#         for tool in tools:
#             print(f"- {tool.name}: {tool.description}")

#         # Test calling a tool.
#         print("\nTesting search_banten...")
#         result = await client.call_tool(
#             "search_banten",
#             {
#                 "query": "Pejati",
#                 "limit": 5,
#             },
#         )

#         print("\nTool Result:")
#         for content in result.content:
#             if hasattr(content, "text"):
#                 print(content.text)

#         if result.isError:
#             print("\nTool returned an error.")


# if __name__ == "__main__":
#     asyncio.run(main())