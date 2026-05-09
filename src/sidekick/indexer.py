"""Incremental indexer. Walks ~/.claude/projects, parses new JSONL bytes, inserts."""
from __future__ import annotations
import datetime as dt
from pathlib import Path

from sidekick import db
from sidekick.parser import parse_session_file, Turn
from sidekick.paths import claude_projects_dir


def _project_name(path: Path) -> str:
    """Return the top-level project dir name, even for subagent paths."""
    root = claude_projects_dir()
    try:
        return path.relative_to(root).parts[0]
    except (ValueError, IndexError):
        return path.parent.name

def _upsert_session(conn, turn: Turn, project: str) -> None:
    conn.execute(
        """
        INSERT INTO sessions (id, project, cwd, started_at, ended_at, status)
        VALUES (?, ?, ?, ?, ?, 'unknown')
        ON CONFLICT(id) DO UPDATE SET
            cwd=COALESCE(sessions.cwd, excluded.cwd),
            ended_at=excluded.ended_at,
            project=COALESCE(sessions.project, excluded.project)
        """,
        (turn.session_id, project, turn.cwd, turn.timestamp, turn.timestamp),
    )

def _insert_turn(conn, turn: Turn) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO turns
            (session_id, turn_idx, role, text, timestamp, input_tokens, output_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (turn.session_id, turn.turn_idx, turn.role, turn.text,
         turn.timestamp, turn.input_tokens, turn.output_tokens),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO turns_fts (rowid, text, session_id, turn_idx, role)
        SELECT rowid, text, session_id, turn_idx, role FROM turns
        WHERE session_id=? AND turn_idx=?
        """,
        (turn.session_id, turn.turn_idx),
    )

def _last_offset(conn, file_path: Path) -> tuple[float, int]:
    row = conn.execute(
        "SELECT mtime, byte_offset FROM file_offsets WHERE file_path=?",
        (str(file_path),),
    ).fetchone()
    return (row[0], row[1]) if row else (0.0, 0)

def _save_offset(conn, file_path: Path, mtime: float, offset: int) -> None:
    conn.execute(
        """
        INSERT INTO file_offsets (file_path, mtime, byte_offset, indexed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            mtime=excluded.mtime,
            byte_offset=excluded.byte_offset,
            indexed_at=excluded.indexed_at
        """,
        (str(file_path), mtime, offset, dt.datetime.utcnow().isoformat()),
    )

def embed_pending(batch_size: int = 64) -> int:
    """Embed turns that have no embedding yet. Returns count embedded."""
    from sidekick.embeddings import Embedder, to_blob
    conn = db.connect()
    rows = conn.execute(
        """
        SELECT t.session_id, t.turn_idx, t.text
        FROM turns t
        LEFT JOIN embeddings e
          ON e.session_id=t.session_id AND e.turn_idx=t.turn_idx
        WHERE e.session_id IS NULL AND t.text != ''
        """
    ).fetchall()
    if not rows:
        return 0
    embedder = Embedder()
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        vecs = embedder.embed_many([r[2] for r in batch])
        conn.executemany(
            "INSERT OR REPLACE INTO embeddings (session_id, turn_idx, vec) VALUES (?, ?, ?)",
            [(r[0], r[1], to_blob(v)) for r, v in zip(batch, vecs)],
        )
        total += len(batch)
    conn.close()
    return total

def run(only_session: str | None = None) -> int:
    """Index all new bytes; return number of new turns inserted."""
    root = claude_projects_dir()
    if not root.exists():
        return 0
    conn = db.connect()
    new_turns = 0
    files = sorted(root.rglob("*.jsonl"))
    for f in files:
        if only_session and only_session not in f.name:
            continue
        mtime = f.stat().st_mtime
        last_mtime, last_offset = _last_offset(conn, f)
        size = f.stat().st_size
        if mtime <= last_mtime and size <= last_offset:
            continue
        project = _project_name(f)
        max_offset = last_offset
        for turn in parse_session_file(f):
            if turn.byte_offset < last_offset:
                continue
            _upsert_session(conn, turn, project)
            _insert_turn(conn, turn)
            new_turns += 1
            max_offset = max(max_offset, turn.byte_offset + 1)
        _save_offset(conn, f, mtime, size)
    conn.close()
    return new_turns
