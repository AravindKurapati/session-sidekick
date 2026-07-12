# session-sidekick

> **Stop re-explaining context you've already worked through.**

A local CLI + Claude Code hook that indexes all your past sessions and surfaces relevant ones as you type - before you accidentally redo work you've already done.

---

## The problem this solves

Claude Code sessions are ephemeral. Every time you start a new one, Claude has no memory of the three hours you spent debugging the same Modal deployment last week, or the exact vLLM flag you figured out, or how you structured that RAG pipeline.

You either:
- Re-explain everything from scratch every session (slow)
- Search through raw JSONL files manually (painful)
- Forget you solved it and solve it again (expensive)

Session-sidekick fixes this with two pieces:

1. **A recall hook** - fires on every prompt via `UserPromptSubmit`. Runs semantic search against all your past sessions. If it finds a confident match, it prints a one-line hint before Claude sees your message: ` You did this before - session abc12345: add modal vllm endpoint`

2. **A search CLI** - keyword + semantic + combined search across every session you've ever had. `sidekick search "modal deployment"` ranks results by relevance, not just recency.

Everything is local. No API keys. No data leaves your machine.

---

## Install

```bash
pip install session-sidekick
```

Or from source:
```bash
git clone https://github.com/AravindKurapati/session-sidekick
cd session-sidekick
pip install -e .
```

**Requirements:** Python 3.11+ - no API keys needed.

---

## Quick start

```bash
# Index your Claude Code sessions (reads ~/.claude/projects/)
sidekick reindex

# Build semantic embeddings (one-time, ~1-2 min)
sidekick embed

# Check what got indexed
sidekick stats

# Search
sidekick search "modal vllm"
sidekick search "react state management" --mode fts
sidekick list --project my-project
sidekick show abc12345 --full
```

---

## Demo

**Browse recent sessions across all your projects**
![sidekick list --limit 8](<Screenshot 2026-05-12 092108.png>)

**Semantic search — finds relevant past work by meaning, not just keywords**
![sidekick search "bulk insert timeout"](<Screenshot 2026-05-12 092130.png>)

**Drill into any session for full context; `stats` shows your indexed corpus**
![sidekick show + sidekick stats](<Screenshot 2026-05-12 092147.png>)

---

## Live recall hook (the main feature)

The recall hook injects a past-session hint into your terminal at the moment you submit a prompt to Claude Code - giving you context before Claude even sees your message.

**Setup:**

```bash
# 1. Install the hooks into ~/.claude/settings.json
sidekick install-hooks --apply

# 2. Start the daemon (keeps the embedding model warm for fast recall)
sidekick-daemon
```

The daemon needs to be running for recall to work. Add it to your shell startup to keep it always-on:

```bash
# ~/.zshrc or ~/.bashrc
sidekick-daemon &>/dev/null &
```

**How it looks:**

```
You: fix the vllm timeout on modal

 You may have done this before - session a3f2b1c8 (2026-04-28): debug modal vllm timeout
   Set request_timeout=120 in the Modal endpoint config, not in the vLLM args.
   Tags: modal,vllm,timeout
   Resume with: claude --resume a3f2b1c8

Claude: ...
```

The hint only appears when the confidence score exceeds the threshold (default 0.78). Silent otherwise - it never interrupts you.

---

## All commands

| Command | What it does |
|---------|-------------|
| `reindex` | Incrementally scan `~/.claude/projects/*.jsonl` |
| `embed` | Build/update semantic embeddings for unembedded turns |
| `stats` | Sessions, turns, embeddings count + DB path |
| `list` | Browse sessions (`--project`, `--status`, `--limit`) |
| `search` | Keyword + semantic search (`--mode fts\|semantic\|combined`) |
| `show` | Full session detail by id (`--full` for all turns) |
| `install-hooks` | Print or apply hook config (`--apply` to patch settings.json) |
| `stop-hook` | Run by Claude Code Stop event - reindex + embed |

---

## How it works

```
~/.claude/projects/**/*.jsonl
        ↓  sidekick reindex
   SQLite (WAL) + FTS5
        ↓  sidekick embed
   MiniLM embeddings (384d, ONNX, local)
        ↓  sidekick-daemon
   TCP socket server (Windows) / Unix socket (macOS/Linux)
        ↓  UserPromptSubmit hook → sidekick-recall
   Cosine similarity → hint printed if score > 0.78
```

- **Index:** `~/.session-sidekick/index.db` - SQLite with FTS5 full-text and raw float32 embeddings
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` via fastembed (ONNX, ~80MB, downloads once)
- **Search:** FTS5 keyword, cosine similarity semantic, or RRF-fused combined
- **Recall budget:** 800ms timeout (ceiling, not a fixed delay) - silent if daemon is slow or down, never blocks Claude Code

---

## Data & privacy

- All data stays local at `~/.session-sidekick/`
- Only reads `~/.claude/projects/` - never writes to it
- No network calls (the optional titler uses Anthropic's API but is disabled by default)
- The daemon runs on localhost only

---

## Optional: session titler

If you want auto-generated titles for sessions (requires `ANTHROPIC_API_KEY`):

```bash
pip install "session-sidekick[titler]"
ANTHROPIC_API_KEY=... sidekick-titler
```

Calls Claude Haiku (~$0.0005 per session). Titles are stored locally and shown in `sidekick list`.

---

## License

MIT
