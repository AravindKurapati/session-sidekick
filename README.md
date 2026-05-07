# session-sidekick

Auto-title your Claude Code sessions and inject per-prompt semantic matches against past sessions.

## Install

```bash
uv pip install -e .
```

## Quick start

```bash
sidekick reindex                       # index ~/.claude/projects/*.jsonl
sidekick embed                         # build embeddings (one-time, ~1 min for 1500 turns)
sidekick search "modal vllm"           # combined keyword + semantic
sidekick list --project foo            # browse
sidekick show <id>                     # session detail

# Hook installation
sidekick install-hooks                 # prints snippet for review
sidekick install-hooks --apply         # patches ~/.claude/settings.json

# Daemon (runs in background; recall hook needs it)
sidekick-daemon &
```

## How it works

See `FEATURE_session_sidekick.md`. Two mechanisms: Haiku-titled sessions on Stop, and a UserPromptSubmit hook that does precision semantic search against past sessions and only injects context on a confident hit.

## Requirements

- Python 3.11+
- `ANTHROPIC_API_KEY` env var (for the titler only)
- macOS / Linux / Windows

## License

MIT
