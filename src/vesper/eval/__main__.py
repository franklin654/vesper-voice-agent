# src/vesper/eval/__main__.py
import argparse, asyncio, sys
from collections import Counter
from pathlib import Path
from .runner import load_cases, run_suite
from .schema import Case, TurnResult

class NullBackend:
    async def run_case(self, case: Case) -> TurnResult:
        raise NotImplementedError("no backend yet: this case should be marked skip")

BACKENDS = {"none": NullBackend}          # register real backends here as phases land
CASES = Path(__file__).parent / "cases"

def main() -> int:
    ap = argparse.ArgumentParser(prog="vesper.eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--suite", default=None, help="tag to select, e.g. smoke")
    run.add_argument("--backend", default="none", choices=BACKENDS)
    args = ap.parse_args()

    results = asyncio.run(run_suite(load_cases(CASES), BACKENDS[args.backend](), args.suite))
    by_status = Counter(status for _, status, _ in results)
    for case, status, note in results:
        if status in ("fail", "error"):
            print(f"{status.upper():5} {case.id}: {note}")
    by_cat = Counter((case.category, status) for case, status, _ in results)
    print(f"\n{len(results)} cases: " + ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())))
    for (cat, status), n in sorted(by_cat.items()):
        print(f"  {cat:12} {status:6} {n}")
    return 1 if by_status["fail"] or by_status["error"] else 0

sys.exit(main())