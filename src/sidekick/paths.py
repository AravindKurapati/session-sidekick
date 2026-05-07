"""Centralized path resolution. All FS paths come from here."""
from __future__ import annotations
from pathlib import Path

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
