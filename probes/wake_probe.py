# probes/wake_probe.py
import argparse, json, statistics, time
from collections import deque
from pathlib import Path
import numpy as np, soundfile as sf
from livekit.wakeword import WakeWordModel          # verify the import path and constructor

WINDOW, FRAME, KEY = 25, 1280, "hey_vesper"         # verify the result key

def scores_for(model, audio):
    audio = np.pad(audio, (2 * 16000, 16000))       # silence either side so the window fills and drains
    window, scores, times = deque(maxlen=WINDOW), [], []
    for i in range(0, len(audio) - FRAME + 1, FRAME):
        window.append(audio[i:i + FRAME])
        if len(window) < WINDOW:
            continue
        t0 = time.perf_counter()
        out = model.predict(np.concatenate(window))
        times.append((time.perf_counter() - t0) * 1000)
        scores.append(float(out[KEY]))
    return scores, times

def load(path):
    audio, sr = sf.read(path, dtype="int16")
    assert sr == 16000
    return audio if audio.ndim == 1 else audio[:, 0]

def triggers(scores, thr, debounce_frames=25):
    count, last = 0, -debounce_frames
    for i, s in enumerate(scores):
        if s >= thr and i - last >= debounce_frames:
            count, last = count + 1, i
    return count

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--label", default="quiet", help="quiet, stress or llama")
args = ap.parse_args()

model = WakeWordModel(args.model)                   # verify constructor arguments
pos = sorted(Path("fixtures/wake/positives").glob("*.wav"))
neg = sorted(Path("fixtures/wake/negatives").glob("*.wav"))
all_times, pos_peaks, neg_rows = [], [], []
for p in pos:
    s, t = scores_for(model, load(p)); all_times += t; pos_peaks.append(max(s))
for p in neg:
    s, t = scores_for(model, load(p)); all_times += t
    neg_rows.append({"file": p.name, "peak": round(max(s), 3), "minutes": round(len(s) * 0.08 / 60, 2),
                     **{f"triggers_at_{thr}": triggers(s, thr) for thr in (0.5, 0.6, 0.7)}})

all_times.sort()
result = {
    "label": args.label,
    "recall": {str(thr): round(sum(p >= thr for p in pos_peaks) / max(1, len(pos_peaks)), 3)
               for thr in (0.4, 0.5, 0.6, 0.7)},
    "negative_triggers": {str(thr): sum(r[f"triggers_at_{thr}"] for r in neg_rows) for thr in (0.5, 0.6, 0.7)},
    "negative_minutes": round(sum(r["minutes"] for r in neg_rows), 1),
    "predict_ms": {"p50": round(statistics.median(all_times), 1),
                   "p95": round(all_times[int(0.95 * (len(all_times) - 1))], 1),
                   "max": round(all_times[-1], 1)},
    "worst_negatives": sorted(neg_rows, key=lambda r: -r["peak"])[:5],
}
Path("probes/results").mkdir(parents=True, exist_ok=True)
Path(f"probes/results/wake_{args.label}.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))