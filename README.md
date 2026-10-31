# Vesper

A wake-word-activated voice assistant for your PC. Say a wake word, speak a
request, and Vesper transcribes it, hands it to an LLM agent equipped with
real tools (filesystem access, web search, browser control), and prints the
agent's reply back to you — asking you follow-up questions out loud when it
genuinely needs more information.

## How it works

```
mic  →  wake-word detection  →  speech-to-text  →  LangGraph agent  →  reply
(Ear)      (openWakeWord)        (SarvamAI)        (LLM + MCP tools)
```

1. **`Ear`** (`src/vesper/ear.py`) continuously captures audio from your
   microphone and resamples it to 16kHz.
2. **`WakeWordGate`** (`src/vesper/wake_word.py`) listens for the wake word
   using [openWakeWord](https://github.com/dscripka/openWakeWord) and only
   lets audio through once it's triggered.
3. **`Transcriber`** (`src/vesper/transcribe.py`) streams the following
   utterance to [SarvamAI](https://www.sarvam.ai/)'s realtime speech-to-text
   API and returns the transcribed text.
4. **The agent** (`src/vesper/agent_factory.py`) is a
   [LangGraph](https://www.langchain.com/langgraph) agent built with
   `langchain.agents.create_agent`, equipped with:
   - **MCP-backed tools**, configured declaratively in
     `src/vesper/tools/mcp_servers.json` (filesystem access, DuckDuckGo
     search, and Playwright browser control out of the box)
   - **Custom tools** (`src/vesper/tools/custom_tools.py`), including
     `ask_user` — a tool the agent calls when it needs to ask *you* a
     clarifying question instead of guessing
   - **`HumanInTheLoopMiddleware`**, which pauses the agent's execution on
     an `ask_user` call so the assistant can speak the question, listen for
     your reply, and resume the agent with your answer (or a timeout
     rejection if you don't respond)
   - **`SummarizationMiddleware`**, which condenses conversation history
     once it grows past a token threshold, so long sessions don't blow the
     context window
5. The agent's reply streams to the console token-by-token as it's
   generated.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Node.js (provides `npx`, used to launch the filesystem and Playwright MCP
  servers)
- A working microphone
- API keys for [SarvamAI](https://www.sarvam.ai/) (speech-to-text) and an
  OpenAI-compatible chat completions endpoint (defaults to
  [z.ai](https://z.ai/)'s GLM models)

## Setup

```bash
git clone git@github.com:franklin654/vesper-voice-agent.git
cd vesper-voice-agent
uv sync
```

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `SARVAM_API_KEY` | Yes | SarvamAI API key, used for speech-to-text |
| `ZAI_API_KEY` | Yes | API key for the LLM backend (z.ai by default) |
| `PLAYWRIGHT_MCP_EXTENSION_TOKEN` | Only if using the Playwright MCP server's browser extension mode | Token for the Playwright browser extension |
| `MIC_DEVICE_NAME` | No | Substring of your microphone's device name, so Vesper picks the right input device automatically. If unset, you'll be prompted to choose one interactively at startup. |
| `WAKE_WORD_MODEL_PATH` | No | Custom ONNX model. Defaults to `openwake_models/hey_vesper.onnx`; relative paths resolve against the `vesper` package directory, independently of the working directory. Absolute paths and `~` are also supported. |
| `WAKE_WORD_PHRASE` | No | Wake phrase shown in the console. Defaults to the model filename converted to words, e.g. `Hey Vesper`. This does not change the phrase the model was trained to detect. |

The MCP servers are launched on demand via `npx`/`uvx` the first time they're
used, so the first run of each will need network access to fetch them.

## Usage

**Voice mode** — the full wake-word → speech → agent loop:

```bash
uv run vesper
```

**Text mode** — a terminal chat harness for exercising the agent and its
tools without a microphone, handy for testing a new tool before wiring it
into the voice loop:

```bash
uv run python -m vesper.text_agents.llm_agent
```

## Configuring tools

MCP servers are declared in `src/vesper/tools/mcp_servers.json`. Add a new
server by adding an entry there — `${VAR}` placeholders are expanded against
your environment (loaded from `.env`), so secrets never need to be
hardcoded into the config file. Custom Python tools live in
`src/vesper/tools/custom_tools.py`; add a function decorated with
`@tool` and list it in `CUSTOM_TOOLS` in `src/vesper/tools/__init__.py`.

## Project layout

```
src/
├── main.py                       # entry point wiring
└── vesper/
    ├── assisstant.py             # main voice loop
    ├── agent_factory.py          # builds the LangGraph agent + middleware
    ├── ear.py                    # microphone capture + resampling
    ├── wake_word.py              # openWakeWord-based wake detection
    ├── transcribe.py             # SarvamAI realtime speech-to-text
    ├── tools/                    # MCP server config + custom tools
    ├── text_agents/              # text-mode harness for tool testing
    └── transcribing_examples/    # reference/exploration scripts
```

## Status

This is an active work in progress. Notably:
- Replies are currently printed to the console, not spoken aloud.
- The `execute_shell_command` tool is not yet gated by
  `HumanInTheLoopMiddleware`, so the agent can run shell commands
  autonomously without a confirmation step — treat this as unfinished
  before relying on it.

## License

[GPL-3.0](LICENSE)
