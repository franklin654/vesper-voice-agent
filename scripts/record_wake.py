# scripts/record_wake.py
import argparse, time
from pathlib import Path
from audio_io import record, save

ap = argparse.ArgumentParser()
ap.add_argument("kind", choices=["positive", "negative", "ambient"])
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--distance", type=int, default=50)
ap.add_argument("--tag", default="normal", help="voice or noise note, e.g. quiet, tired, tv, fan")
ap.add_argument("--seconds", type=float, default=3.0)
ap.add_argument("--device", type=int, default=-1)
args = ap.parse_args()

NEAR_MISS = ["hey whisper", "hey Jasper", "hey Vespa", "vesper", "hey there", "hey Siri",
             "hey Vasu", "they vesper", "hey Vamsi", "hey Hesper"]

out = Path("fixtures/wake")
if args.kind == "ambient":
    input(f"Start the TV, fan or conversation, then press Enter to record {args.seconds:.0f} s ")
    save(out / "negatives" / f"ambient-{args.tag}-{int(time.time())}.wav",
         record(args.seconds, args.device))
else:
    for i in range(args.n):
        phrase = "hey vesper" if args.kind == "positive" else NEAR_MISS[i % len(NEAR_MISS)]
        input(f"[{i + 1}/{args.n}] say '{phrase}' ({args.tag}, {args.distance} cm); Enter to record ")
        time.sleep(0.4)
        name = f"{args.kind}-{args.tag}-{args.distance}cm-{int(time.time())}-{i}.wav"
        folder = "positives" if args.kind == "positive" else "negatives"
        save(out / folder / name, record(args.seconds, args.device))