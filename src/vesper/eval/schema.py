# src/vesper/eval/schema.py
from typing import Any, Protocol
from pydantic import BaseModel, Field

class Expect(BaseModel):
    route: str | None = None                  # exact | semantic | agent
    intent: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)   # each: {name, args?}
    shows_candidates: bool | None = None
    final_state: str | None = None
    next_turn_ok: bool | None = None
    thread_parked: bool | None = None

class Case(BaseModel):
    id: str
    category: str
    tags: list[str] = Field(default_factory=list)
    skip: str | None = None                   # e.g. "until phase 2"
    input: dict[str, Any]                     # {text: ...} or {audio: path}
    context: dict[str, Any] = Field(default_factory=dict)
    script: list[dict[str, Any]] = Field(default_factory=list)   # steps the backend plays: waits, replies, events to expect
    expect: Expect = Field(default_factory=Expect)
    forbid: list[str] = Field(default_factory=list)              # action ids that must not happen
    forbid_tools: list[str] = Field(default_factory=list)        # tool names that must not be called

class TurnResult(BaseModel):
    route: str | None = None
    intent: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    shows_candidates: bool = False
    final_state: str | None = None
    next_turn_ok: bool | None = None
    thread_parked: bool | None = None
    side_effects: list[str] = Field(default_factory=list)        # action ids that really happened

class Backend(Protocol):
    async def run_case(self, case: Case) -> TurnResult: ...