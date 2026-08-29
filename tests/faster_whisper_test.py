from faster_whisper import WhisperModel

model_size = "small"

model = WhisperModel(model_size, device="cpu")

segments, info = model.transcribe('audio.mp3')

print("Detected language '%s' with probability %f" % (info.language, info.language_probability))

for segment in segments:
    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))