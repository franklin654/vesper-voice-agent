from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig, Runnable
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from contextlib import AsyncExitStack
import os
import getpass
import dotenv
import asyncio
import pathlib
dotenv.load_dotenv()


API_KEY = os.environ.get("ZAI_API_KEY")
if API_KEY is None:
    API_KEY=getpass.getpass("ZAI_API_KEY")

llm = ChatOpenAI(
    model="GLM-4.5-Flash",
    base_url="https://api.z.ai/api/paas/v4",
    api_key=lambda: API_KEY,
    max_completion_tokens=8000
)

client = MultiServerMCPClient(
    {
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(os.environ.get("HOME"))
            ],
            "transport": "stdio"
        },
        "ddg-search": {
            "command": "uvx",
            "args": [
                "--with",
                'duckduckgo-mcp-server[browser]',
                'duckduckgo-mcp-server',
                '--fetch-backend',
                'auto'
            ],
            "transport": "stdio"
        },
        "playwright": {
            "url": "http://localhost:7070/sse",
            "transport": "sse"
        }
    }
)

agent = create_agent(model=llm, 
                     tools=tools, 
                     checkpointer=InMemorySaver(),
                     middleware=[
                         SummarizationMiddleware(
                             model=llm,
                             trigger=("tokens", 50000),
                             keep=("tokens", 20000)),
                    ],
                    system_prompt="For all Playwright actions, do not create a new page or session. " \
                    "First, use the tool to list active pages/tabs, find the ID of the URL we are working " \
                    "on, and pass that specific page ID into all subsequent tool calls. " \
                    "If a welcome tab opens, switch focus back to the ta  + Exception Group Traceback (most recent call last):"
            )

config: RunnableConfig = {"configurable": {"thread_id": "1"}}


async def parse_agent_output(input: str|HumanMessage|dict[str, str], agent: Runnable):
    async with await agent.astream_events(
        {"messages": [input]},
        config=config,
        version="v3"
    ) as run: # type: ignore
        async for msg in run.messages:
            async for token in msg.text:
                print(token, end="", flush=True)
    print()

    if type(input) == str:
        input = HumanMessage(input)
    
    async for chunk in agent.astream({"messages": [input]}, config=config,
                                              version="v2", stream_mode="messages"): # type: ignore
        message = chunk["data"]["messages"][-1]
        if getattr(message, "type", "") == 'ai':
            message.pretty_print()
        else:
            print(message.text)
    result = await agent.ainvoke({"messages": [input]}, config=config)
    result["messages"][-1].pretty_print()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def main():
    all_tools = []
    async with AsyncExitStack() as stack:
        for server_name in ["playwright", "filesystem", "ddg-search"]:
            session = await stack.enter_async_context(client.session(server_name=server_name))

            server_tools = await load_mcp_tools(session)
            all_tools.extend(server_tools)

        agent = create_agent(model=llm, 
                        tools=all_tools, 
                        checkpointer=InMemorySaver(),
                        middleware=[
                            SummarizationMiddleware(
                                model=llm,
                                trigger=("tokens", 50000),
                                keep=("tokens", 20000)),
                        ],
                        system_prompt="You are an helpful interactive Computer Assisstant named Jarvis " \
                        "and you have a sister named cortana"
                )
        while True:
            human_input = input("Human: ")
            if human_input in ["q", 'quit', 'bye', 'exit']:
                return
            await parse_agent_output(human_input, agent)

if __name__=="__main__":
    try:
        loop.run_until_complete(main())            
    finally:
        loop.close()