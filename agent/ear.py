from langchain.messages import HumanMessage, SystemMessage

import openwakeword
from openwakeword.model import Model
from pvrecorder import PvRecorder
import sounddevice as sd
from sarvamai import AsyncSarvamAI, RealtimeAudioInput, RealtimePing
import soxr
import numpy as np
import base64

import dotenv
import os
import getpass
import asyncio
dotenv.load_dotenv()

class Ear:
    """Captures at the device's native rate (queried, never assumed) and
    resamples to 16kHz in software, since forcing samplerate=16000 on the
    InputStream isn't reliably supported across devices/backends. Every
    consumer downstream still only ever sees 16kHz PCM."""

    def __init__(self, device_index = None, device_name: str | None = None) -> None:
        # Setting Up Device
        # Device indices are assigned per-machine (and can shift between
        # reboots on the same machine), so prefer resolving by name - it's
        # the only thing that's actually stable to hardcode/configure.
        if device_index is None and device_name:
            for each_device in sd.query_devices():
                if device_name.lower() in each_device["name"].lower() and each_device["max_input_channels"] > 0:
                    device_index = each_device["index"]
                    break

        if device_index is None:
            device_list = sd.query_devices()
            for each_device in device_list:
                print(f"{each_device['index']}:\t{each_device['name']}")
            while True:
                device_index = input("Please enter the index of the microphone: ")
                if device_index.isdecimal() and int(device_index) < len(device_list):
                    self._DEVICE_INDEX = int(device_index)
                    break
                else:
                    print("Please pick and option from the above")
        self._DEVICE_INDEX = device_index
        self.DEVICE_SAMPLE_RATE = int(sd.query_devices(device_index)["default_samplerate"])  # Getting the default sample rate
        self.DEVICE_FRAME_SIZE = int(1280 * (self.DEVICE_SAMPLE_RATE / 16000.0))
        self._audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self._stream = sd.InputStream(samplerate=self.DEVICE_SAMPLE_RATE, 
                                                blocksize=self.DEVICE_FRAME_SIZE, 
                                                device=self._DEVICE_INDEX, 
                                                channels=1,
                                                dtype="int16",
                                                callback=self._callback_for_sd)
        self._loop = asyncio.get_event_loop()
        

    def _callback_for_sd(self, indata: np.ndarray, frames: int, time, status: sd.CallbackFlags) -> None:
        if status:
            pass
        self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, indata.copy().flatten())

    def start(self) -> None:
        self._stream.start()


    def close(self) -> None:
        self._stream.stop()
        self._stream.close()


    async def read(self) -> np.ndarray:
        frame = await self._audio_queue.get()
        resampled_frame = soxr.resample(frame, self.DEVICE_SAMPLE_RATE, 16000.0)
        return resampled_frame
    

    def drain(self) -> None:
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()
    
###########################################################################################


# WAKE-Word Capture Settings
FRAME_LENGTH = 1280
_PING_INTERVAL = 25
MAX_UTTERANCE_SECONDS = 90.0
DEVICE_INDEX = PvRecorder.get_available_devices().index("Logitech G PRO X Gaming Headset Mono")

# Setting up Wake Word Model & Recorder
_openwakeword_model = Model(inference_framework="onnx")
_recorder = PvRecorder(frame_length=FRAME_LENGTH, device_index=DEVICE_INDEX)

def wait_for_wake_word():
    """keeps recording the frames and wait's for the wake word to heard"""
    _openwakeword_model.reset()
    _recorder.start()

    # flush ~1s of buffered frames (12 frames x 80ms @ 16Khz)
    for _ in range(12):
        _recorder.read()

    SystemMessage("Please say 'Hey Jarvis' to get started").pretty_print()
    while True:
        frame = _recorder.read()
        prediction = _openwakeword_model.predict(np.array(frame).astype(np.int16))

        if prediction['hey_jarvis'] >= 0.3: # type: ignore
            _recorder.stop()
            _openwakeword_model.reset()      # don't let state leak into the next round
            break


async def capture_utterance_sarvam(timeout: float | None = None) -> str | None:
        
    """Reads audio frames from Mic and sends it to SarvamAI API for translation and transcription

    Args:
        recorder (PvRecorder): the PvRecorder Object to read frames from.
        timeout (float | None, optional): The Maximum Utterance to listen for. Defaults to None.

    Returns:
        str | None: None if error occurred or timed out else returns the transcribed text.
    """
    _recorder.start()
    SystemMessage("Please say/ask whatever you want").pretty_print()
    client = AsyncSarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))
    async with client.speech_to_text_realtime_streaming.connect(
        language_code="auto", 
        mode="translate",
        encoding="linear16",
    ) as ws:
        async def sender():
            while True:
                frame = await asyncio.to_thread(_recorder.read)
                audio_base64 = base64.b64encode(np.array(frame).astype(np.int16).tobytes()).decode("utf-8")
                await ws.send_realtime_audio_input(RealtimeAudioInput(audio=audio_base64))


        async def pinger():
            while True:
                await asyncio.sleep(_PING_INTERVAL)
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
            _recorder.stop()
    

def close_recorder():
    _recorder.stop()
    _recorder.delete()