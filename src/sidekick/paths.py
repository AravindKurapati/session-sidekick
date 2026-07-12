"""Centralized path resolution. All FS paths come from here."""
from __future__ import annotations
import re
from pathlib import Path


def encode_project(cwd: str | None) -> str | None:
    """Encode a real cwd path into Claude Code's project-dir-name form.

    Claude stores each session under ~/.claude/projects/<encoded-cwd>/, replacing
    every non-alphanumeric character with a single '-' (no collapsing), e.g.
    'D:\\Aru\\NYU\\agent-flight-recorder' -> 'D--Aru-NYU-agent-flight-recorder'.
    The indexer stores that same string in sessions.project, so this lets the
    recall path compare the caller's cwd against stored projects. Returns None for
    empty input.
    """
    if not cwd:
        return None
    return re.sub(r"[^0-9A-Za-z]", "-", cwd.rstrip("/\\"))

def home() -> Path:
    return Path.home()

def sidekick_dir() -> Path:
    p = home() / ".session-sidekick"
    p.mkdir(parents=True, exist_ok=True)
    return p

def db_path() -> Path:
    return sidekick_dir() / "index.db"

def logs_dir() -> Path:
    p = sidekick_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p

def claude_projects_dir() -> Path:
    """Where Claude Code stores session JSONLs. Tries new path first."""
    new = home() / ".config" / "claude" / "projects"
    if new.exists():
        return new
    return home() / ".claude" / "projects"
