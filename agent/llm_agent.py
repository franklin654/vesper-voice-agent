from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig
import os
import dotenv
import asyncio
import pathlib
dotenv.load_dotenv()

qwen_llm = ChatOpenAI(
    name="qwen2.4-14b-q4",
    base_url="http://127.0.0.1:12001",
    api_key="dsafadsfdsafasd"
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
        }
    }
)

@tool
def read_text_file(path: str):
    """
    This is a tool for reading a text file only
    args:
        path: the path to the text file
    returns:
        the content of the file if it presents else it will return File Not found
    """
    if not pathlib.Path(path).exists():
        return "File not found"
    else:
        return pathlib.Path(path).read_text()

def connect_to_drive_api():
    pass

tools = asyncio.run(client.get_tools())

tavily_search = TavilySearch(max_results=10,
                             topic="general")

tools.append(tavily_search)
tools.append(read_text_file)

agent = create_agent(model=qwen_llm, 
                     tools=tools, 
                     checkpointer=InMemorySaver(),
                     middleware=[
                         SummarizationMiddleware(
                             model=qwen_llm,
                             trigger=("fraction", 0.75),
                             keep=("fraction", 0.25))
                    ]
            )

config: RunnableConfig = {"configurable": {"thread_id": "1"}}


async def parse_agent_output(input: str|HumanMessage|dict[str, str]):
    async for message in agent.astream({"messages": input}, 
                                       config=config, 
                                       stream_mode="values", 
                                       version="v2"): # type: ignore
        message["data"]["messages"][-1].pretty_print()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

if __name__=="__main__":
    try:
        while True:
            human_input = input("Human: ")
            if human_input in ["q", 'quit', 'bye', 'exit']:
                break
            loop.run_until_complete(parse_agent_output(HumanMessage(human_input)))
    finally:
        loop.close()