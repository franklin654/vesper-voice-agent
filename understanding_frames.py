import sounddevice as sd
import numpy as np
import time

def callback(indata: np.ndarray, frames: int, time, status: sd.CallbackFlags):
    if status:
        print(status)
    print(indata, indata.shape)

with sd.InputStream(samplerate=48000.0, device=16, callback=callback) as stream:
    sd.sleep(int(1*1000))