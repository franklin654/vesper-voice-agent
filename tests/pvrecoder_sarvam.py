from pvrecorder import PvRecorder
from sarvamai import AsyncSarvamAI, RealtimeAudioInput, RealtimePing, RealtimeEnd
import numpy as np
import dotenv
import torch
import os
dotenv.load_dotenv()
import asyncio
import base64

recorder = PvRecorder(frame_length=1280, device_index=1)

async def caputre_utterance(recorder: PvRecorder, timeout: float | None = None) -> str | None:
    recorder.start()
    client = AsyncSarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))
    async with client.speech_to_text_realtime_streaming.connect(
        language_code="auto", mode="translate",
        encoding="linear16"
    ) as ws:
        async def sender():
            while True:
                frame = await asyncio.to_thread(recorder.read)
                audio_base64 = base64.b64encode(np.array(frame).astype(np.int16).tobytes()).decode("utf-8")
                await ws.send_realtime_audio_input(RealtimeAudioInput(audio=audio_base64))


        async def pinger():
            while True:
                await asyncio.sleep(5)
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

        try:
            return await asyncio.wait_for(receiver(), timeout=timeout) if timeout else await receiver()
        except asyncio.TimeoutError:
            return None
        finally:
            send_task.cancel()
            ping_task.cancel()
            recorder.stop()

if __name__=="__main__":
    print(asyncio.run(caputre_utterance(recorder)))
    print(asyncio.run(caputre_utterance(recorder)))