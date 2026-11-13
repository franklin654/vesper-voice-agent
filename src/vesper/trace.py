import json, statistics, time

class Trace:
    """Millisecond marks since the turn started. One JSON line per turn"""
    def __init__(self, turn_id: str):
        self.turn_id, self.t0, self.marks = turn_id, time.monotonic(), {}

    def mark(self, name: str):
        self.marks[name] = round((time.monotonic() - self.t0) * 1000)

    def dump(self, path: str = "trace.jsonl") -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"turn_id": self.turn_id, **self.marks})+"\n")

def summarize(path: str) -> dict[str, dict[str, float]]:
    """p50 and p95 per mark over a trace file"""
    series: dict[str, list[int]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            for key, value in row.items():
                if key != "turn_id":
                    series.setdefault(key, []).append(value)
    out = {}
    for key, values in series.items():
        values.sort()
        p95 = values[min(len(values) - 1, int(0.95 * len(values)))]
        out[key] = {"n": len(values), "p50": statistics.median(values), "p95": p95}
    return out
