import sqlite3
from sidekick import db

def test_connect_creates_schema(tmp_home):
    conn = db.connect()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {row[0] for row in cur.fetchall()}
    assert "sessions" in names
    assert "turns" in names
    assert "file_offsets" in names

def test_connect_creates_fts(tmp_home):
    conn = db.connect()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='turns_fts'"
    )
    assert cur.fetchone() is not None

def test_connect_is_idempotent(tmp_home):
    db.connect().close()
    db.connect().close()

def test_wal_mode_enabled(tmp_home):
    conn = db.connect()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
