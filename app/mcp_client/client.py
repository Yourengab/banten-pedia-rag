import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "app"
SERVER_FILE = APP_DIR / "mcp_server.py"

load_dotenv(ROOT_DIR / ".env")


class BantenPediaMCPClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

        server_env = os.environ.copy()
        existing_pythonpath = server_env.get("PYTHONPATH", "")
        server_env["PYTHONPATH"] = (
            f"{APP_DIR}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(APP_DIR)
        )

        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_FILE)],
            env=server_env,
        )

    async def __aenter__(self):
        # AsyncExitStack ensures all context managers are entered and exited
        # within the same task, avoiding anyio cancel scope boundary violations.
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        read_stream, write_stream = await self._stack.enter_async_context(
            stdio_client(self.server_params)
        )
        self.session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self.session.initialize()

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self._stack:
            await self._stack.__aexit__(exc_type, exc_value, traceback)
            self._stack = None
        self.session = None

    async def list_tools(self):
        """Get tools registered on the MCP Server."""
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, name: str, arguments: dict):
        """Call an MCP tool by name."""
        return await self.session.call_tool(
            name,
            arguments=arguments,
        )