"""SQLite connection + schema. Lives at ~/.session-sidekick/index.db."""
from __future__ import annotations
import sqlite3
from sidekick.paths import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project TEXT,
    cwd TEXT,
    started_at TEXT,
    ended_at TEXT,
    title TEXT,
    summary TEXT,
    tags TEXT,
    status TEXT,
    titled_at TEXT,
    last_seen_offset INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turns (
    session_id TEXT NOT NULL,
    turn_idx INTEGER NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    PRIMARY KEY (session_id, turn_idx)
);

CREATE TABLE IF NOT EXISTS file_offsets (
    file_path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    byte_offset INTEGER NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    session_id TEXT NOT NULL,
    turn_idx INTEGER NOT NULL,
    vec BLOB NOT NULL,
    PRIMARY KEY (session_id, turn_idx)
);

CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
    text,
    session_id UNINDEXED,
    turn_idx UNINDEXED,
    role UNINDEXED,
    content='turns',
    content_rowid='rowid'
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_titled ON sessions(titled_at) WHERE titled_at IS NULL;
"""

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
