import os
from pathlib import Path

from openwakeword.model import Model
from .ear import Ear

WAKE_WORD_THRESHOLD = 0.25
PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = "openwake_models/hey_vesper.onnx"


class WakeWordGate:
    def __init__(self, model_path: str | Path | None = None):
        """Load a custom ONNX model; relative paths are based on this package."""
        path = Path(model_path or os.environ.get("WAKE_WORD_MODEL_PATH") or DEFAULT_MODEL_PATH).expanduser()
        if not path.is_absolute():
            path = PACKAGE_DIR / path
        self.model_path = path.resolve()
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Wake-word model not found: {self.model_path}")

        self.model_name = self.model_path.stem
        self.phrase = os.environ.get("WAKE_WORD_PHRASE") or self.model_name.replace("_", " ").title()
        self._model = Model(wakeword_models=[str(self.model_path)], inference_framework="onnx")

    def triggered(self, frame) -> bool:
        scores = self._model.predict(frame)
        return scores[self.model_name] >= WAKE_WORD_THRESHOLD

    async def wait_for_trigger(self, ear: Ear) -> None:
        self._model.reset()
        while True:
            frame = await ear.read()
            if self.triggered(frame):
                return
