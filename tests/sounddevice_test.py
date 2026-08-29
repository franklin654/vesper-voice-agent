import sounddevice as sd
import queue
import numpy as np
import whisper
import soxr

DEVICE_SAMPLE_RATE = 48000
WHISPER_SAMPLE_RATE = 16000
CHUNK_DURATION = 3

# sd.default.samplerate = DEVICE_SAMPLE_RATE
sd.default.device = 7

audio_queue = queue.Queue()

print("Loading Whisper Model")

model = whisper.load_model("turbo")

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(indata.copy().flatten())

print("Starting microphone stream... (Pres Ctrl+C to stop)")
try:
    with sd.InputStream(samplerate=DEVICE_SAMPLE_RATE, channels=1, dtype="float32", callback=audio_callback):
        while True:
            audio_buffer = []
            frames_collected = 0
            required_frames = DEVICE_SAMPLE_RATE * CHUNK_DURATION

            while frames_collected < required_frames:
                chunk = audio_queue.get()
                audio_buffer.append(chunk)
                frames_collected += len(chunk)

            native_audio = np.concatenate(audio_buffer)

            whisper_audio = soxr.resample(
                native_audio,
                in_rate=DEVICE_SAMPLE_RATE,
                out_rate=WHISPER_SAMPLE_RATE
            )

            result = model.transcribe(whisper_audio)

            text = result["text"].strip()
            if text:
                print(f"Transcribed: {text}")

except KeyboardInterrupt:
    print("\nTranscription stopped.")