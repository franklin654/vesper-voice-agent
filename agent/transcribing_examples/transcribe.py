import os
import soxr
import torch
import base64
import asyncio
import getpass
import numpy as np
import sounddevice as sd
from collections import deque
from dotenv import load_dotenv
from sarvamai import AsyncSarvamAI, RealtimeAudioInput, RealtimeEnd, RealtimePing
from sarvamai.speech_to_text_realtime_streaming.socket_client import AsyncSpeechToTextRealtimeStreamingSocketClient

load_dotenv()
if os.environ.get("SARVAM_API_KEY") is None:
    API_KEY = getpass.getpass("Enter Sarvam API Key: ")
else:
    API_KEY = os.environ.get("SARVAM_API_KEY")


sarvam_client = AsyncSarvamAI(api_subscription_key=API_KEY)

DEVICE_SAMPLE_RATE = 48000
TARGET_SAMPLE_RATE = 16000
SILENCE_DURATION = 2.0
PRE_ROLL_DURATION = 1.0

VAD_CHUNK_SIZE = 512
NATIVE_CHUNK_SIZE = int(VAD_CHUNK_SIZE * (DEVICE_SAMPLE_RATE / TARGET_SAMPLE_RATE))

SILENCE_CHUNKS = int(SILENCE_DURATION / 0.032)
PRE_ROLL_CHUNKS = int(PRE_ROLL_DURATION / 0.032)

print("Loading Silero VAD...")
vad_model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True)

audio_queue = asyncio.Queue()

def audio_callback(indata: np.ndarray, frames: int, time, status):
    audio_queue.put_nowait(indata.copy().flatten())

async def send_to_sarvam(ws: AsyncSpeechToTextRealtimeStreamingSocketClient, float32_chunk: np.ndarray):
    """Helper to convert float32 array to int16 Base64 and send over WebSocket."""
    pcm_audio = (float32_chunk * 32767).astype(np.int16)
    base64_chunk = base64.b64encode(pcm_audio.tobytes()).decode("utf-8")
    await ws.send_realtime_audio_input(RealtimeAudioInput(audio=base64_chunk))

async def process_audio():
    async with sarvam_client.speech_to_text_realtime_streaming.connect(
        language_code="auto",
        stream_type="fast",
        mode="translate"
    ) as ws:
        print("Listening with 1s pre-speech buffer active...")

        # 1. Task for receving transcripts

        async def receive_events():
            async for message in ws:
                # if message.event == "transcript.partial":
                #     print(f"\rPartial: {message.text}", end="")
                if message.event == "transcript.final":
                    print(f"\nFinal: {message.text}\n")
                # print(message)

        # 2. Send Periodic Keep-Alive Pings
        async def send_pings():
            while True:

                await asyncio.sleep(5)
                try:
                    await ws.send_realtime_ping(RealtimePing())
                except Exception as e:
                    print(f"Ping failed: {e}")

        # 3. Task to stream audio with Pre-Roll logic
        async def stream_audio():
            is_speaking = False
            silence_counter = 0

            pre_buffer = deque(maxlen=PRE_ROLL_CHUNKS)

            while True:
                native_chunk = await audio_queue.get()

                # print("chunk_recivied", native_chunk[0:10])

                target_chunk = soxr.resample(native_chunk, in_rate=DEVICE_SAMPLE_RATE, out_rate=TARGET_SAMPLE_RATE)

                # Check VAD
                tensor_chunk = torch.from_numpy(target_chunk)
                speech_prob = vad_model(tensor_chunk, TARGET_SAMPLE_RATE).item()

                if speech_prob > 0.5:
                    if not is_speaking:
                        is_speaking = True
                        silence_counter = 0

                        while pre_buffer:
                            old_chunk = pre_buffer.popleft()
                            await send_to_sarvam(ws, old_chunk)

                    await send_to_sarvam(ws, target_chunk)
                else:
                    if is_speaking:
                        silence_counter += 1
                        await send_to_sarvam(ws, target_chunk)

                        if silence_counter > SILENCE_CHUNKS:
                            is_speaking = False
                            silence_counter = 0
                    else:
                        pre_buffer.append(target_chunk)

        await asyncio.gather(receive_events(), stream_audio(), send_pings())

if __name__=="__main__":
    with sd.InputStream(samplerate=DEVICE_SAMPLE_RATE, channels=1, dtype='float32', 
                        device=7, blocksize=NATIVE_CHUNK_SIZE, callback=audio_callback):
        try:
            asyncio.run(process_audio())
        except KeyboardInterrupt:
            print("\nStopped.")
                    

