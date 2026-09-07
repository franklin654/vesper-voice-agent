from openwakeword.model import Model
from .ear import Ear

WAKE_WORD_THRESHOLD = 0.4


class WakeWordGate:
    def __init__(self, model_path: str = "hey_jarvis"):
        self._model = Model(wakeword_models=[model_path], inference_framework="onnx")

    def triggered(self, frame) -> bool:
        scores = self._model.predict(frame)
        return scores['hey_jarvis'] >= WAKE_WORD_THRESHOLD

    async def wait_for_trigger(self, ear: Ear) -> None:
        while True:
            frame = await ear.read()
            if self.triggered(frame):
                return
