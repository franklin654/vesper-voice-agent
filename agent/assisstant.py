from langchain.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agent_factory import get_agent
from ear import Ear
from transcribe import Transcriber
from wake_word import WakeWordGate
from tools import load_all_tools

from contextlib import AsyncExitStack
import os
import dotenv
import asyncio
dotenv.load_dotenv()

REPLY_TIMEOUT_SECONDS = 15.0

config: RunnableConfig = {"configurable": {"thread_id": "1"}}

async def run_assistant():
    sarvam_api_key = os.environ.get("SARVAM_API_KEY")
    if sarvam_api_key is None:
        raise RuntimeError("SARVAM_API_KEY is not set. Please add it to your .env file.")

    ear = Ear(device_name=os.environ.get("MIC_DEVICE_NAME"))
    ear.start()
    wake_word_gate = WakeWordGate()
    transcriber = Transcriber(sarvam_api_key)
    async with AsyncExitStack() as stack:
        tools = await load_all_tools(stack)
        agent = get_agent(tools=tools)

        try:
            while True:
                SystemMessage("Please Say Hey Jarvis To wake the model").pretty_print()
                await wake_word_gate.wait_for_trigger(ear)
                SystemMessage("Please speak what you want to say").pretty_print()
                text = await transcriber.capture_utterance(ear)
                HumanMessage(text).pretty_print()
                if text is None:
                    continue
                result = await agent.ainvoke({
                    "messages": [
                        {
                            "role": "user",
                            "content": text
                        }
                    ]
                }, 
                config=config,
                version="v2")
                while result.interrupts:
                    question = result.interrupts[0].value["action_requests"][0]["args"]["question"]
                    ear.drain()
                    AIMessage(question).pretty_print()
                    SystemMessage("Please reply to AI").pretty_print()
                    reply = await transcriber.capture_utterance(ear, timeout=REPLY_TIMEOUT_SECONDS)
                    if reply is None:
                        decision = {
                            "type": "reject",
                            "message": "The user did not respond in time. Do not ask again — "
                                "either proceed with your best judgment or tell the user "
                                "you couldn't help without that information.",
                        }
                    else:
                        decision = {"type": "respond", "message": reply}
                    result = await agent.ainvoke(
                        Command(
                            resume={
                                "decisions": [decision]
                            }
                        ),
                        config=config,
                        version="v2"
                    )
                result.value["messages"][-1].pretty_print()
                ear.drain()
        finally:
            ear.close()

if __name__=="__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_assistant())