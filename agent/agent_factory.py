from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import tool, BaseTool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents.middleware import SummarizationMiddleware, HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig, Runnable
import os
import dotenv
import asyncio
from typing import List
dotenv.load_dotenv()

def get_agent(model_name: str = 'GLM-5.3-Flash',
              base_url: str|None = "https://api.z.ai/api/paas/v4",
              api_key_var: str = "ZAI_API_KEY",
              max_tokens: int = 8000,
              tools: List[BaseTool]|None = None) -> Runnable:
    API_KEY = os.environ.get(api_key_var)
    if API_KEY is None:
        raise RuntimeError(f"{api_key_var} is not set. Please add it to your .env file.")
    
    model = ChatOpenAI(
        model=model_name,
        base_url=base_url,
        api_key=lambda: API_KEY,
        max_completion_tokens=max_tokens)
    
    return create_agent(model=model, 
                     tools=tools, 
                     checkpointer=InMemorySaver(),
                     middleware=[
                            SummarizationMiddleware(
                             model=model,
                             trigger=("tokens", 50000),
                             keep=("tokens", 20000)),
                            HumanInTheLoopMiddleware(
                                interrupt_on={"ask_user": {"allowed_decisions": ["respond", "reject"]}}
                            )
                        ]
                    )

async def parse_agent_output(input: str|HumanMessage|dict[str, str], agent: Runnable, config: RunnableConfig):
    async with await agent.astream_events(
        {"messages": [input]}, 
        config=config,
        version="v3"
    ) as run:
        async for msg in run.messages:
            async for token in msg.text:
                print(token, end="", flush=True)