"""Build + install Claude Code hook config in ~/.claude/settings.json."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from sidekick import indexer
from sidekick.paths import home

def build_hook_config() -> dict:
    py = sys.executable
    return {
        "Stop": [
            {
                "matcher": "*",
                "hooks": [
                    {"type": "command", "command": f'"{py}" -m sidekick stop-hook', "timeout": 5}
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "matcher": "*",
                "hooks": [
                    {"type": "command", "command": f'"{py}" -m sidekick.recall', "timeout": 1}
                ],
            }
        ],
    }

def settings_path() -> Path:
    return home() / ".claude" / "settings.json"

def merge_into(existing: dict, new_hooks: dict) -> dict:
    out = dict(existing)
    out.setdefault("hooks", {})
    for event, entries in new_hooks.items():
        out["hooks"].setdefault(event, [])
        out["hooks"][event] = [
            e for e in out["hooks"][event]
            if not any(
                "sidekick" in (h.get("command", "") if isinstance(h, dict) else "")
                for h in (e.get("hooks", []) if isinstance(e, dict) else [])
            )
        ]
        out["hooks"][event].extend(entries)
    return out

def install(apply: bool = False) -> str:
    cfg = build_hook_config()
    snippet = json.dumps({"hooks": cfg}, indent=2)
    if not apply:
        return snippet
    sp = settings_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if sp.exists():
        try:
            existing = json.loads(sp.read_text())
        except json.JSONDecodeError:
            existing = {}
    merged = merge_into(existing, cfg)
    sp.write_text(json.dumps(merged, indent=2))
    return f"wrote {sp}"

def stop_hook() -> tuple[int, int, int]:
    """Run after Claude Code stops: index from AFR when available, then embed."""
    source_db = indexer.afr_db_path()
    if source_db.exists():
        new, skipped = indexer.reindex_from_afr(db_path=source_db)
    else:
        new = indexer.run()
        skipped = 0
    embedded = indexer.embed_pending()
    print(f"sidekick: {new} sessions indexed, {skipped} skipped")
    return new, skipped, embedded
