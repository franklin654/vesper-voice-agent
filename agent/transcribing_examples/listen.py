import queue
import numpy as np
import sounddevice as sd
import soxr
import torch
import whisper

SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512
SILENCE_DURATION = 1.0
SILENCE_CHUNKS = int((SAMPLE_RATE / VAD_CHUNK_SIZE) * SILENCE_DURATION)

audio_queue = queue.Queue()

# Load Models
print("Loading Whisper...")
whisper_model = whisper.load_model("tiny")

print("Loading Silero VAD...")
vad_model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', 
                              model='silero_vad',
                              trust_repo=True # type: ignore
                            )

def audio_callback(indata, frames, time, status):
    audio_queue.put(indata.copy().flatten())

print("Listening... (Speak into the microphone)")

is_speaking = False
silence_counter = 0
phrase_buffer = []

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                    blocksize=VAD_CHUNK_SIZE, device=23, callback=audio_callback):
    while True:
        chunk = audio_queue.get()

        tensor_chunk = torch.from_numpy(chunk)

        speech_prob = vad_model(tensor_chunk, SAMPLE_RATE).item()

        if speech_prob > 0.5:
            is_speaking = True
            silence_counter = 0
            phrase_buffer.append(chunk)
        else:
            if is_speaking:
                phrase_buffer.append(chunk)
                silence_counter += 1

                if silence_counter > SILENCE_CHUNKS:
                    full_audio = np.concatenate(phrase_buffer)

                    result = whisper_model.transcribe(full_audio)
                    text = result["text"].strip() # type: ignore

                    if text:
                        print(f"You said: {text}")

                    is_speaking = False
                    silence_counter = 0
                    phrase_buffer = []