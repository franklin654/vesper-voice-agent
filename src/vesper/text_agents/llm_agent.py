"""Text-mode harness for exercising the agent and its tools (MCP-backed and
custom) from the terminal, without needing a microphone. Useful for trying
out a new tool before wiring it into the voice loop in assisstant.py."""

from contextlib import AsyncExitStack

from langchain.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel
from langgraph.types import Command

from ..agent_factory import get_agent
from ..tools import load_all_tools

import asyncio
import dotenv
dotenv.load_dotenv()

config: RunnableConfig = {"configurable": {"thread_id": "text-mode"}}

async def run_and_stream(agent: Pregel, input_data, config: RunnableConfig):
    """
    Helper function to stream updates to the console 
    and return the final state snapshot.
    """
    async for chunk in agent.astream(
        input_data,
        config=config,
        stream_mode="values",
        version="v2"
    ):
        if chunk["type"] == "values":
            print("\n🔄 [Live State Value]:")
            # chunk["data"] contains the full state dictionary at this step
            state = chunk["data"]
            messages = state.get("messages", [])

            if messages:
                messages[-1].pretty_print()

    return await agent.aget_state(config)


async def main() -> None:
    async with AsyncExitStack() as stack:
        tools = await load_all_tools(stack)
        agent = get_agent(model_name="GLM-4.5-Flash", tools=tools)

        SystemMessage("Text-mode agent ready. Type 'quit' to exit.").pretty_print()
        while True:
            human_input = input("You: ")
            if human_input.strip().lower() in {"q", "quit", "exit", "bye"}:
                return

            initial_input = {"messages": [{"role": "user", "content": human_input}]}
            result = await run_and_stream(agent, initial_input, config)
    
            while result.interrupts:
                question = result.interrupts[0].value["action_requests"][0]["args"]["question"]
                AIMessage(question).pretty_print()
                reply = input("Your reply (blank to skip): ")
                if reply:
                    decision = {"type": "respond", "message": reply}
                else:
                    decision = {
                        "type": "reject",
                        "message": "The user did not respond. Do not ask again — either "
                            "proceed with your best judgment or tell the user you couldn't "
                            "help without that information.",
                    }
                resume_input = Command(resume={"decisions": [decision]})
                result = await run_and_stream(agent, resume_input, config)
            # result.values["messages"][-1].pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
