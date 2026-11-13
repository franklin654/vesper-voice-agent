# tests/test_lessons.py
from pathlib import Path

def test_no_sync_invoke_in_agent_package():
    """v1 mixed .ainvoke for first calls with .invoke for resumes. Async only."""
    for p in Path("src/vesper/agent").rglob("*.py"):
        assert ".invoke(" not in p.read_text(encoding="utf-8"), f"sync invoke in {p}"