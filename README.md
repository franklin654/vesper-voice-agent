# vesper

A voice-first executive assistant that runs in the background on your own computer. Say "hey vesper", then control your machine, set reminders, and work with your mail and calendar, using a local model and explicit safety rules.

> **Status: pre-alpha, Phase 0 of 5.** v2 is a ground-up rebuild: nothing from v1 is carried over, only its lessons. Right now the repository holds the design, the plan, and the tooling to prove the risky pieces (local model, Sarvam, wake word). The assistant itself does not run yet. See the [roadmap](#roadmap).

## What it will do

- **Listen on demand.** A custom wake word ("hey vesper") or push-to-talk starts a turn. Wake detection runs locally; audio is sent to Sarvam only after a trigger, one utterance at a time.
- **Understand mixed Telugu-English.** Open-ended speech goes to Sarvam's realtime speech-to-text (translated to English). Simple commands use a local recognizer so they work offline.
- **Skip the LLM when it can.** A deterministic router matches commands by grammar, then by meaning, and only falls through to the language model for open-ended requests.
- **Control your computer.** Open apps and sites, play media, manage windows, search and copy files by voice, with numbered choices on screen and an undo for file operations.
- **Schedule and remind.** Reminders, scheduled messages, and recurring briefings. Unattended jobs run only content you approved when you scheduled them.
- **Work with Google Workspace.** Calendar, Gmail drafts, Drive and contacts through Google's hosted MCP servers. Every write is read back and confirmed.
- **Show what it is doing.** A Siri-style popup, tray icon, terminal UI, web UI and a `vesperctl` command, all driven by the same event stream.
- **Reach your phone and the cloud (later).** A cloud agent as the always-on scheduler and an Android client.

## How it works

```text
mic -> wake word / push-to-talk -> speech to text (local first, Sarvam on a miss)
    -> router: exact match -> semantic match -> agent (LLM)
    -> handlers: computer control | scheduler | Workspace
    -> events -> popup | tray | TUI | web UI
```

- One **daemon** owns all state. Every interface is a thin client that renders events and sends input.
- One **handler registry** is called by both the router and the agent, so no capability has two implementations.
- Every handler declares a **risk class** (safe, reversible, destructive, privileged). The model never chooses it.
- The agent sits behind an `AgentBackend` interface, so the framework can change without touching audio, clients or capabilities.

Details are in the [design document](docs/vesper_Voice_Assistant___Design_v2_0_3.md).

## Tech stack

| Part | Choice | Status |
| --- | --- | --- |
| Language and tooling | Python, `uv` (3.12 is the default to confirm in Phase 0) | Chosen |
| Local model | Qwen2.5 14B Instruct Q4 through llama.cpp's `llama-server` | Baseline; compared against newer models in Phase 0 (decision D5) |
| Agent | LangChain `create_agent` with middleware, SQLite checkpointer | Chosen; Google ADK evaluated in a spike in Phase 3 |
| Speech to text | Sarvam realtime (`saaras:v3-realtime`) plus a local recognizer for commands | Chosen; local recognizer built in Phase 2 |
| Wake word | `livekit-wakeword` model trained for "hey vesper", scored by our own ring buffer | Chosen |
| Audio capture | PvRecorder, 16 kHz mono | Chosen |
| Local API | FastAPI WebSocket on `127.0.0.1` | Planned |
| Clients | Textual (TUI), PySide6 (popup), static web UI | Planned |
| Storage | SQLite | Planned |
| Secrets | System keyring | Planned |

## Requirements

- Linux with KDE Plasma. Developed on an Arch-based machine and targeted at Kubuntu 26.04. The input and popup work assumes Wayland; confirm with `echo $XDG_SESSION_TYPE`.
- Python (see above), [`uv`](https://docs.astral.sh/uv/), `git`, `ffmpeg`, `sox`, `stress-ng`.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) with `llama-server`, and a GGUF model.
- A microphone.
- A Sarvam API subscription key.
- Your trained `hey_vesper` ONNX wake model.

Windows and macOS are not supported. A Windows backend is a possible later phase. Android is planned.

## Quick start (Phase 0)

```bash
git clone <your-repo-url> vesper
cd vesper
uv sync

make test     # unit tests
make lint     # ruff
make eval     # eval harness (most cases are skipped until their phase)
```

Store your Sarvam key in the system keyring once:

```bash
uv run python -c "import keyring; keyring.set_password('vesper', 'sarvam', input('Sarvam key: '))"
```

Start the local model for the probes:

```bash
llama-server -m /path/to/model.gguf --jinja -c 8192 --port 8080
```

Then follow the [Phase 0 guide](docs/vesper_Voice_Assistant___Phase_0_Guide_v2_0_3.md) to record audio fixtures and run the four probes (recorder, model, Sarvam, wake word).

## Repository layout

```text
vesper/
  intents/            shared YAML: intents, slots, risk classes
  probes/             Phase 0 standalone probes and their results
  fixtures/           recorded audio and phrase lists (audio is not in git)
  src/vesper/
    daemon/           main loop, state machine, supervisor, event bus, local API
    audio/            recorder thread, ring buffer, wake word
    stt/              Sarvam client, local recognizer, circuit breaker
    router/           exact and semantic tiers, handler registry
    agent/            AgentBackend interface and implementations
    handlers/         computer control, scheduler and Workspace handlers
    scheduler/        job store, dispatcher, outbox, time parsing
    clients/          popup, TUI, web UI, vesperctl
    eval/             eval harness and cases
  deploy/systemd/     user service units
  training/wakeword/  wake-word training container and configs
  docs/               design, plan, guides, decision records
```

Most packages are empty until their phase.

## Documentation

| Document | What it covers |
| --- | --- |
| [Design v2.0.3](docs/vesper_Voice_Assistant___Design_v2_0_3.md) | Architecture, event protocol, safety model, and the lessons carried over from v1 |
| [Implementation Plan v2.0.3](docs/vesper_Voice_Assistant___Implementation_Plan_v2_0_3.md) | The six phases with tasks, how-tos, end results and gates |
| [Phase 0 Guide](docs/vesper_Voice_Assistant___Phase_0_Guide_v2_0_3.md) | Step-by-step setup, fixtures, probes and the eval harness |
| `docs/adr/` | One short decision record per open decision |
| `docs/phase0-report.md` | Results of the Phase 0 probes (written during Phase 0) |

The v1 repository is archived read-only. Its architecture plan is kept for reference; read it for lessons only and never copy code from it.

## Roadmap

| Phase | Goal | Gate to move on |
| --- | --- | --- |
| 0. Foundations and probes | Empty working repo, risky pieces proven in isolation, fixtures, eval harness | Probe results recorded, at least 50 eval cases, model chosen |
| 1. Platform | Background daemon, event stream, supervisor, first clients | Every injected fault ends in IDLE; agent and human-in-the-loop evals pass |
| 2. Local assistant, no LLM | Files, media, web, windows and reminders by voice, offline | Offline demo passes with no wrong actions |
| 3. Smart assistant | Agent, Workspace, scheduled sends, web UI, ADK spike | Injection tests pass; a scheduled send happens exactly once |
| 4. Everywhere | Cloud scheduler, device registry, Android thin client | A reminder reaches laptop and phone |
| 5. Stretch | On-device Android tier, spoken replies, Windows, accessibility tree | Per item |

The wake-word model is tuned in parallel from real-use logs.

## Safety model

- **Approval happens at scheduling time against frozen content.** Unattended jobs never improvise.
- **Reads and writes are separate tools.** Writes are always read back and confirmed; any run that reads untrusted text (mail, web pages) has no write tools.
- **The model never writes raw paths, shell commands or addresses.** Handlers take IDs from search results and typed arguments checked against allowlists.
- **Deleting means moving to trash.** File operations are confined to configured roots and log an undo.
- **No raw shell tool, and privileged actions are not available by voice.**
- **Speaker verification** gates anything above the safe class, and a **kill switch** stops all jobs.

## Privacy

- Wake detection runs on the device. The microphone stays open locally so the wake word can be heard, and the operating system's microphone indicator stays on.
- Audio goes to Sarvam only after a wake or push-to-talk, one utterance at a time, and is billed by the second.
- Wake-word clips, including near-misses, are kept locally with rolling retention to tune the model. They never leave the machine.
- Secrets live in the system keyring. The local API binds to loopback only.

## Development

- `make test`, `make lint` and `make eval` must pass before a change is merged; behaviour changes also add or update an eval case.
- Every new capability sits behind a config flag that stays off until its phase's exit criteria pass.
- The agent package uses async calls only. Never mix sync `invoke` with async calls.
- Do not commit audio fixtures, model files or secrets. A pre-commit hook scans for secrets.
- Definition of done for a task: code merged, test written, eval case added if behaviour changed, config flag documented, one line in the changelog.

## License

To be decided. Add a `LICENSE` file before sharing the repository. Note that the wake-word training data (ACAV100M features) is non-commercial, so a model trained on it inherits that restriction.

## Acknowledgements

[llama.cpp](https://github.com/ggml-org/llama.cpp), [Qwen](https://github.com/QwenLM), [Sarvam AI](https://www.sarvam.ai/), [LangChain](https://www.langchain.com/), [livekit-wakeword](https://github.com/livekit), and [PvRecorder](https://github.com/Picovoice/pvrecorder).
