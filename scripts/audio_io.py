import numpy as np, soundfile as sf
from pvrecorder import PvRecorder
from pathlib import Path

SAMPLE_RATE, FRAME = 16000, 1280

def record(seconds: float, device: int = -1) -> np.ndarray:
    rec = PvRecorder(frame_length=FRAME, device_index=device)
    rec.start()
    try:
        frames = [np.array(rec.read(), dtype=np.int16) 
                  for _ in range(int(seconds * SAMPLE_RATE / FRAME))]
    finally:
        rec.stop()
        rec.delete()
    return np.concatenate(frames)

def save(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, SAMPLE_RATE, subtype="PCM_16")
