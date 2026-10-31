from langchain.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel
from langgraph.types import Command

from .agent_factory import get_agent
from .ear import Ear
from .transcribe import Transcriber
from .wake_word import WakeWordGate
from .tools import load_all_tools

from contextlib import AsyncExitStack, suppress
import os
import dotenv
import asyncio
dotenv.load_dotenv()

REPLY_TIMEOUT_SECONDS = 15.0
CANCEL_PHRASES = ("stop", "cancel", "never mind", "nevermind", "forget it", "that's enough", "quiet")

config: RunnableConfig = {"configurable": {"thread_id": "1"}}

class BargeInCancelled(Exception):
    """Raised when the user barges in on a running turn with cancel intent."""

def _is_cancel_intent(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in CANCEL_PHRASES)

async def run_and_stream(agent: Pregel, input_data, config: RunnableConfig):
    """
    Helper function to stream updates to the console 
    and return the final state snapshot.
    """
    async with await agent.astream_events(
        input_data,
        config=config,
        version="v3"
    ) as run:
        async def consume_messages():
            async for message in run.messages:
                async for token in message.text:
                    print(token, end="", flush=True)
                    await asyncio.sleep(0.010)
            print()
        
        await asyncio.gather(consume_messages())
    return await agent.aget_state(config)

async def run_with_barge_in(agent, input_data, config: RunnableConfig, ear: Ear,
                             wake_word_gate: WakeWordGate, transcriber: Transcriber):
    """Runs a turn while concurrently listening for the wake word again, so a
    long-running turn (search, browsing, shell commands) can be interrupted.
    Returns (result, pending_followup) - pending_followup is the next
    utterance to process immediately, if the barge-in wasn't a cancellation.
    Raises BargeInCancelled if the user barged in with a stop-type phrase."""
    agent_task = asyncio.create_task(run_and_stream(agent, input_data, config))
    listen_task = asyncio.create_task(wake_word_gate.wait_for_trigger(ear))
    try:
        while True:
            done, _ = await asyncio.wait({agent_task, listen_task}, return_when=asyncio.FIRST_COMPLETED)
            if agent_task in done:
                return agent_task.result(), None

            SystemMessage("Yes? (say 'stop' to cancel)").pretty_print()
            new_text = await transcriber.capture_utterance(ear, timeout=REPLY_TIMEOUT_SECONDS)
            if new_text is None:
                # False trigger - keep listening for another barge-in attempt.
                listen_task = asyncio.create_task(wake_word_gate.wait_for_trigger(ear))
                continue

            if _is_cancel_intent(new_text):
                agent_task.cancel()
                with suppress(asyncio.CancelledError):
                    await agent_task
                raise BargeInCancelled(new_text)

            return await agent_task, new_text
    finally:
        if not listen_task.done():
            listen_task.cancel()

async def run_assistant():
    sarvam_api_key = os.environ.get("SARVAM_API_KEY")
    if sarvam_api_key is None:
        raise RuntimeError("SARVAM_API_KEY is not set. Please add it to your .env file.")

    wake_word_gate = WakeWordGate()
    ear = Ear(device_name=os.environ.get("MIC_DEVICE_NAME"))
    ear.start()
    transcriber = Transcriber(sarvam_api_key)
    async with AsyncExitStack() as stack:
        tools = await load_all_tools(stack)
        agent = get_agent(tools=tools)

        try:
            pending_text = None
            while True:
                if pending_text is None:
                    SystemMessage(f"Please say {wake_word_gate.phrase} to wake the model").pretty_print()
                    await wake_word_gate.wait_for_trigger(ear)
                    SystemMessage("Please speak what you want to say").pretty_print()
                    text = await transcriber.capture_utterance(ear)
                    HumanMessage(text).pretty_print()
                    if text is None:
                        continue
                else:
                    text = pending_text
                    pending_text = None
                    HumanMessage(text).pretty_print()

                initial_input = {"messages": [{"role": "user", "content": text}]}
                try:
                    result, pending_text = await run_with_barge_in(
                        agent, initial_input, config, ear, wake_word_gate, transcriber
                    )
                except BargeInCancelled:
                    AIMessage("Cancelled.").pretty_print()
                    ear.drain()
                    continue

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
                    resume_input = Command(resume={"decisions": [decision]})
                    result = await run_and_stream(agent, resume_input, config)
                ear.drain()
        finally:
            ear.close()

if __name__=="__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_assistant())
