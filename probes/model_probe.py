from math import log
import argparse, asyncio, json, statistics, time
import logging
from pathlib import Path
from numpy import require
import httpx, jsonschema, yaml

SYSTEM = ("You are a voice assistant. Use tools when needed. If a required detail is "
          "missing and cannot be reasonably inferred, call ask_user instead of guessing.")

def fn(name, description, props, required):
    """Returns the function name, description, and properties of 
    the function along with whether if it's required
    """
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props, "required": required}}}

# Tools for model test run/probe
TOOLS = [
    fn("calc", "Evaluate an arithmetic expression.", {"expr": {"type": "string"}}, ["expr"]),
    fn("set_reminder", "Create a reminder.",
       {"text": {"type": "string"}, "when": {"type": "string", "description": "e.g. 'tomorrow 8 am'"}},
       ["text", "when"]),
    fn("search_files", "Search the user's files by name.", {"query": {"type": "string"}}, ["query"]),
    fn("ask_user", "Ask the user one short, specific question. Use only when a required detail "
       "is missing and cannot be reasonably inferred or defaulted.",
       {"question": {"type": "string"}}, ["question"]),
]

# Schema or property for all the tools defined in TOOLS list.
SCHEMAS = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}

def check_calls(calls):
    """Return (names, problem). problem is None when every call parses and validates."""
    names = []
    for c in calls:
        name = c["function"]["name"]        # Get the function call Name and append it to list.
        names.append(name)
        if name not in SCHEMAS:
            return names, "unknown_tool"    # check if the name is in the defind tools
        try:
            args = json.loads(c["function"]["arguments"])   # Load the argumets passed by model to the function
        except (json.JSONDecodeError, TypeError):
            return names, "parse_error"     # If the the json parsing failed return the func_name and the parse_error
        try:
            jsonschema.validate(args, SCHEMAS[name])    # Validate the arguments parsed by the call with expected schema of the function
        except jsonschema.ValidationError:
            return names, "schema_invalid"  # Return the func name if schema validation failed.
    return names, None                      # Return the func names that were called.

def judge(case, names, problem, text):# -> Any | Literal['pass', 'spurious_call', 'guessed_args', 'no_question', 'wrong_tool']:# -> Any | Literal['pass', 'spurious_call', 'guessed_args', 'no_question', 'wrong_tool']:# -> Any | Literal['pass', 'spurious_call', 'guessed_args', 'no_question', 'wrong_tool']:# -> Any | Literal['pass', 'spurious_call', 'guessed_args', 'no_question', 'wrong_tool']:# -> Any | Literal['pass', 'spurious_call', 'guessed_args', 'no_question', 'wrong_tool']:# -> Any | Literal['pass', 'spurious_call', 'guessed_args', 'no_question', 'wrong_tool']:
    exp = case["expect"]
    if exp.get("no_tool"):
        return "pass" if not names else "spurious_call"
    if problem:
        return problem
    if exp.get("asks"):
        if names == ["ask_user"] or (not names and text.strip().endswith("?")):
            return "pass"
        return "guessed_args" if names else "no_question"
    if "tool" in exp:
        return "pass" if names == [exp["tool"]] else "wrong_tool"
    if "tools" in exp:
        return "pass" if sorted(names) == sorted(exp["tools"]) else "wrong_tool"
    return "pass"

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="label for this model, e.g. qwen2.5-14b-q4")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()

    cases = yaml.safe_load(Path("probes/tool_prompts.yaml").read_text(encoding="utf-8"))
    rows = []
    async with httpx.AsyncClient(timeout=180) as client:
        for case in cases:
            for r in range(args.repeats):
                body = {"model": args.name, "temperature": args.temperature, "tools": TOOLS,
                        "messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": case["text"]}]}
                t0 = time.perf_counter()
                resp = await client.post(f"{args.base_url}/chat/completions", json=body)
                ms = (time.perf_counter() - t0) * 1000
                json_resp = resp.json()
                msg = json_resp["choices"][0]["message"]
                names, problem = check_calls(msg.get("tool_calls") or [])
                verdict = judge(case, names, problem, msg.get("content") or "")
                rows.append({"id": case["id"], "group": case["group"], "run": r, 
                             "verdict": verdict, "ms": round(ms)})

    summary = {}
    for g in sorted({r["group"] for r in rows}):
        grp = [r for r in rows if r["group"] == g]
        summary[g] = {"n": len(grp), "pass_rate": round(sum(r["verdict"] == "pass" for r in grp) / len(grp), 3)}
    lat = sorted(r["ms"] for r in rows)
    out = {"model": args.name, "temperature": args.temperature, "summary": summary,
           "latency_ms": {"p50": statistics.median(lat), "p95": lat[int(0.95 * (len(lat) - 1))]},
           "failures": [r for r in rows if r["verdict"] != "pass"]}
    Path("probes/results").mkdir(parents=True, exist_ok=True)
    Path(f"probes/results/model_{args.name.replace("/", "_")}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out["summary"], indent=2), out["latency_ms"])

asyncio.run(main())