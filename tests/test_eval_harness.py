# tests/test_eval_harness.py
import asyncio
from pathlib import Path
import pytest
from vesper.eval.runner import check, load_cases, run_suite
from vesper.eval.schema import Case, TurnResult, Backend

class Fake:
    def __init__(self, result): self.result = result
    async def run_case(self, case): return self.result

def case(**kw):
    base = dict(id="t1", category="files", input={"text": "x"})
    return Case(**{**base, **kw})

def test_pass_and_fail_on_expectation():
    c = case(expect={"route": "exact", "intent": "files.copy"})
    assert check(c, TurnResult(route="exact", intent="files.copy")) == []
    assert check(c, TurnResult(route="agent", intent="files.copy"))

def test_forbidden_side_effect_fails():
    c = case(forbid=["files.copy"])
    assert check(c, TurnResult(side_effects=["files.copy"]))
    assert check(c, TurnResult()) == []

def test_forbidden_tool_fails():
    c = case(forbid_tools=["ask_user"])
    assert check(c, TurnResult(tool_calls=[{"name": "ask_user"}]))

def test_case_without_expectations_is_a_problem():
    assert check(case(), TurnResult()) == ["case has no expectations"]

def test_skip_and_error_statuses():
    skipped = case(skip="until phase 2", forbid=["x"])
    class Boom(Backend):
        async def run_case(self, c): raise RuntimeError("boom")
    out = asyncio.run(run_suite([skipped, case(id="t2", forbid=["x"])], Boom()))
    assert [s for _, s, _ in out] == ["skip", "error"]

def test_all_seed_cases_load_with_unique_ids():
    cases = load_cases(Path("src/vesper/eval/cases"))
    assert len(cases) >= 50