import json, logging
from vesper.trace import Trace, summarize
from vesper.logging import setup_logging, new_turn_id

def test_trace_marks_increase_and_summarize(tmp_path):
    p = tmp_path / "t.jsonl"
    for i in range(5):
        t = Trace(f"t{i}")
        t.mark("a"); t.mark("b")
        assert t.marks["b"] >= t.marks["a"]
        t.dump(str(p))
    s = summarize(str(p))
    assert s["a"]["n"] == 5 and "p95" in s["b"]

def test_log_lines_carry_turn_id(tmp_path):
    p = tmp_path / "l.jsonl"
    setup_logging(str(p))
    tid = new_turn_id()
    logging.getLogger("x").info("hello", extra={"data": {"k": 1}})
    for h in logging.getLogger().handlers: h.flush()
    row = json.loads(p.read_text().splitlines()[-1])
    assert row["turn_id"] == tid and row["k"] == 1