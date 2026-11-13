# src/vesper/eval/runner.py
from pathlib import Path
import yaml
from .schema import Case, TurnResult, Backend

FIELDS = ("route", "intent", "shows_candidates", "final_state", "next_turn_ok", "thread_parked")

def load_cases(root: Path) -> list[Case]:
    cases, seen = [], set()
    for f in sorted(root.glob("*.yaml")):
        for raw in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            case = Case(**raw)
            assert case.id not in seen, f"duplicate case id {case.id}"
            seen.add(case.id)
            cases.append(case)
    return cases

def check(case: Case, turn: TurnResult) -> list[str]:
    e, problems = case.expect, []
    if not (any(getattr(e, f) is not None for f in FIELDS) or e.tool_calls
            or case.forbid or case.forbid_tools):
        return ["case has no expectations"]
    for f in FIELDS:
        want = getattr(e, f)
        if want is not None and getattr(turn, f) != want:
            problems.append(f"{f}: wanted {want!r}, got {getattr(turn, f)!r}")
    calls = {c.get("name"): c for c in turn.tool_calls}
    for want in e.tool_calls:
        got = calls.get(want["name"])
        if got is None:
            problems.append(f"missing tool call {want['name']}")
        elif any(got.get("args", {}).get(k) != v for k, v in want.get("args", {}).items()):
            problems.append(f"tool call {want['name']} has wrong arguments")
    for name in case.forbid_tools:
        if name in calls:
            problems.append(f"forbidden tool call: {name}")
    for action in case.forbid:
        if action in turn.side_effects:
            problems.append(f"forbidden side effect happened: {action}")
    return problems

async def run_suite(cases: list[Case], backend: Backend, tag: str | None = None):
    results = []
    for case in cases:
        if tag and tag not in case.tags:
            continue
        if case.skip:
            results.append((case, "skip", case.skip))
            continue
        try:
            problems = check(case, await backend.run_case(case))
        except Exception as exc:                                  # a crash is a failure, never a pass
            results.append((case, "error", repr(exc)))
            continue
        results.append((case, "fail" if problems else "pass", "; ".join(problems)))
    return results