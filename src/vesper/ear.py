import sounddevice as sd
import soxr
import numpy as np

import dotenv
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
