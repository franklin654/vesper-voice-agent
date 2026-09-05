import numpy as np
import soxr
from sarvamai import AsyncSarvamAI, RealtimeAudioInput, RealtimePing
import asyncio
from ear import Ear
import base64

MAX_UTTERANCE_SECONDS = 90
PING_INTERVAL_SECONDS = 25


class Transcriber:
    def __init__(self, api_key: str):
        self._client = AsyncSarvamAI(api_subscription_key=api_key)


    async def capture_utterance(self, ear: Ear, timeout: float | None = None) -> str|None:
        async with self._client.speech_to_text_realtime_streaming.connect(
            language_code="auto",
            mode="translate",
            encoding="linear16",
        ) as ws:
            async def sender():
                while True:
                    frame = await ear.read()
                    base64_frame = base64.b64encode(frame.tobytes()).decode("utf-8")
                    await ws.send_realtime_audio_input(RealtimeAudioInput(audio=base64_frame))

            async def pinger():
                while True:
                    await asyncio.sleep(PING_INTERVAL_SECONDS)
                    await ws.send_realtime_ping(RealtimePing())

            async def receiver():
                async for message in ws:
                    if message.event == "transcript.final": # type: ignore
                        return message.text # type: ignore
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