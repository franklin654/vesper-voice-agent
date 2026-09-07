from contextlib import AsyncExitStack

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools

from .mcp_servers import get_mcp_client
from .custom_tools import ask_user

CUSTOM_TOOLS = [ask_user]


async def load_all_tools(stack: AsyncExitStack) -> list[BaseTool]:
    """Connects to every configured MCP server (using the caller's
    AsyncExitStack, so session lifetime stays tied to the caller's scope)
    and returns the combined list of MCP tools plus the hand-written
    custom tools."""
    tools: list[BaseTool] = list(CUSTOM_TOOLS)
    client = get_mcp_client()
    for server_name in client.connections.keys():
        session = await stack.enter_async_context(client.session(server_name=server_name))
        server_tools = await load_mcp_tools(session=session)
        tools.extend(server_tools)
    return tools
