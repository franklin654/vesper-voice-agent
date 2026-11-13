import argparse, json, time
from pathlib import Path
import yaml
from audio_io import record, save

ap = argparse.ArgumentParser()
ap.add_argument("--speaker", required=True)
ap.add_argument("--distance", type=int, default=60, help="cm from the mic")
ap.add_argument("--noise", default="quiet")
ap.add_argument("--seconds", type=float, default=4.0)
ap.add_argument("--only", help="comma-seperated ids to record")
ap.add_argument("--device", type=int, default=-1)
args = ap.parse_args()

phrases = yaml.safe_load(Path("fixtures/phrases.yaml").read_text(encoding="utf-8"))

if args.only:
    wanted = set(args.only.split(","))
    phrases = [p for p in phrases if p["id"] in wanted]

manifest = Path("fixtures/manifest.jsonl")
for p in phrases:
    while True:
        input(f"\n[{p['id']}] say: {p['text']}\n  Enter to record ")
        time.sleep(0.4)
        audio = record(args.seconds, args.device)
        choice = input("  Enter = keep, r = redo, s = skip: ").strip().lower()
        if choice == "r":
            continue
        if choice != "s":
            rel = f"audio/{args.speaker}/{args.distance}cm-{args.noise}/{p['id']}.wav"
            save(Path("fixtures") / rel, audio)
            row = {**p, "file": rel, "speaker": args.speaker,
                   "distance_cm": args.distance, "noise": args.noise}
            with manifest.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        break