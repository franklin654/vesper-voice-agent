# scripts/phrases_to_cases.py
import yaml
from pathlib import Path

phrases = yaml.safe_load(Path("fixtures/phrases.yaml").read_text(encoding="utf-8"))
cases = [{
    "id": f"speech-{p['id']}", "category": "speech" if p["category"] == "mixed" else p["category"],
    "tags": ["needs-expect"], "skip": "until phase 2",
    "input": {"text": p.get("expected_en") or p["text"],
              "audio": f"fixtures/audio/thomas/50cm-quiet/{p['id']}.wav"},
    "expect": {},                                  # fill in route and intent by hand
} for p in phrases]
Path("src/vesper/eval/cases/generated.yaml").write_text(
    yaml.safe_dump(cases, sort_keys=False, allow_unicode=True), encoding="utf-8")