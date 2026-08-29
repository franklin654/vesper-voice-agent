# Capture Voice Loop Dependencies
import openwakeword
from openwakeword.model import Model
from pvrecorder import PvRecorder
from sarvamai import AsyncSarvamAI, RealtimeAudioInput, RealtimePing, RealtimeEnd
import numpy as np
import torch
import base64

# Ai Agent Dependencies
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents.middleware import SummarizationMiddleware, ToolCallRequest, HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

import dotenv
import os
import asyncio
dotenv.load_dotenv()

# Wake-Word Capture Loop
FRAME_LENGTH = 1280
PING_INTERVAL = 25
MAX_UTTERANCE_SECONDS = 90.0

# Setting up Wake_Word Model & Recorder
openwake_model = Model()
recorder = PvRecorder(frame_length=FRAME_LENGTH, device_index=1)

def wait_for_wake_word(recorder: PvRecorder):
    """keeps recording the frames and wait's for the wake word to heard"""
    recorder.start()
    print("Please say 'Hey Jarvis' to get started")
    while True:
        frame = recorder.read()
        prediction = openwake_model.predict(frame)
        if prediction['hey_jarvis'] >= 0.3:
            recorder.stop()
            break

async def capture_utterance(recorder: PvRecorder, timeout: float | None = None) -> str | None:
    """Reads audio frames from Mic and sends it to SarvamAI API for translation and transcription

    Args:
        recorder (PvRecorder): the PvRecorder Object to read frames from.
        timeout (float | None, optional): The Maximum Utterance to listen for. Defaults to None.

    Returns:
        str | None: _description_
    """
    recorder.start()
    print("Please say/ask whatever you want: ")
    client = AsyncSarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))
    async with client.speech_to_text_realtime_streaming.connect(
        language_code="auto", 
        mode="translate",
        encoding="linear16",
    ) as ws:
        async def sender():
            while True:
                frame = await asyncio.to_thread(recorder.read)
                audio_base64 = base64.b64encode(np.array(frame).astype(np.int16).tobytes()).decode("utf-8")
                await ws.send_realtime_audio_input(RealtimeAudioInput(audio=audio_base64))


        async def pinger():
            while True:
                await asyncio.sleep(PING_INTERVAL)
                await ws.send_realtime_ping(RealtimePing())

        async def receiver():
            async for message in ws:
                if message.event == "transcript.final": # type: ignore
                    return message.text  # type: ignore
                if message.event == "error": # type: ignore
                    return None
            return None

        send_task = asyncio.create_task(sender())
        ping_task = asyncio.create_task(pinger())

        effective_timeout = min(timeout, MAX_UTTERANCE_SECONDS) if timeout else MAX_UTTERANCE_SECONDS
        try:
            return await asyncio.wait_for(receiver(), timeout=effective_timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            send_task.cancel()
            ping_task.cancel()
            recorder.stop()


# Setup Agent for action

qwen_llm = ChatOpenAI(
    name="qwen2.4-14b-q4",
    base_url="http://127.0.0.1:12001",
    api_key="dsafadsfdsafasd"
)

# Defining tools for the agent
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
def ask_user(question: str) -> str:
    """Ask the user one short, specific question, but only when a required
    detail is missing and cannot be reasonably inferred or defaulted.
    Do not use this to confirm things you can reasonably assume, and do not
    use it as a first response before attempting the request."""
    # This body never actually runs. HumanInTheLoopMiddleware intercepts
    # the call before this executes and substitues the human's reply
    # instead - it's here only so the tool has a valid signature.
    raise NotImplementedError("handled by HumanInTheLoopMiddleware's 'respond' descision")


tools = asyncio.run(client.get_tools())
tavily_search = TavilySearch(max_results=10,
                             topic="general")
tools.extend([
    tavily_search,
    ask_user
])

config: RunnableConfig = {"configurable": {"thread_id": 1}}

agent = create_agent(model=qwen_llm, tools=tools, 
                     checkpointer=InMemorySaver(), 
                     middleware=[
                         SummarizationMiddleware(model=qwen_llm, 
                                                 trigger=("fraction", 0.6), 
                                                 keep=("fraction", 0.25)),
                        HumanInTheLoopMiddleware(
                            interrupt_on={
                                "ask_user": {"allowed_decisions": ["respond"]}
                            }
                        )
                        ]
                    )


if __name__=="__main__":
    loop = asyncio.new_event_loop()
    try:
        while True:
            wait_for_wake_word(recorder)
            text = loop.run_until_complete(capture_utterance(recorder=recorder))
            if text is None:
                continue
            result = loop.run_until_complete(agent.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": text
                        }
                    ]
                },
                config=config,
                version="v2"
            ))
            while result.interrupts:
                question = result.interrupts[0].value["action_requests"][0]["arguments"]["question"]
                print("Agent is asking:", question)
                answer = loop.run_until_complete(capture_utterance(recorder=recorder))
                if answer is None:
                    decision = {
                        "type": "reject",
                        "message": "The user did not respond in time. Do not ask again — "
                                "either proceed with your best judgment or tell the user "
                                "you couldn't help without that information.",
                    }
                else:
                    decision = {"type": "respond", "message": answer}
                result = loop.run_until_complete(agent.ainvoke(
                    Command(
                        resume={
                            "decisions": [decision]
                        }
                    ),
                    config=config,
                    version="v2"
                ))
            else:
                result.value["messages"][-1].pretty_print()
    finally:
        recorder.stop()
        recorder.delete()
        print("Bye")
