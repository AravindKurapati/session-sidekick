import shutil
import time
from pathlib import Path
from sidekick import db, indexer
from sidekick.paths import claude_projects_dir
from fixtures.make_afr_fixture import make_afr_db

FIXTURES = Path(__file__).parent / "fixtures"

def _seed(home, name="completed"):
    target_dir = claude_projects_dir() / "test-project"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.jsonl"
    shutil.copy(FIXTURES / f"{name}.jsonl", target)
    return target

def test_index_inserts_turns(tmp_home):
    _seed(tmp_home)
    n = indexer.run()
    assert n == 3
    conn = db.connect()
    rows = conn.execute("SELECT COUNT(*) FROM turns").fetchone()
    assert rows[0] == 3

def test_index_inserts_session_row(tmp_home):
    _seed(tmp_home)
    indexer.run()
    conn = db.connect()
    row = conn.execute(
        "SELECT id, project, cwd FROM sessions WHERE id='sess-completed'"
    ).fetchone()
    assert row is not None
    assert row[1] == "test-project"
    assert row[2] == "/proj/foo"

def test_index_is_incremental(tmp_home):
    f = _seed(tmp_home)
    assert indexer.run() == 3
    assert indexer.run() == 0
    with open(f, "a") as fh:
        fh.write('{"type":"user","message":{"role":"user","content":"more"},"sessionId":"sess-completed","timestamp":"2026-05-04T10:00:40Z"}\n')
    time.sleep(0.05)
    assert indexer.run() == 1

def test_index_populates_fts(tmp_home):
    _seed(tmp_home)
    indexer.run()
    conn = db.connect()
    rows = conn.execute(
        "SELECT session_id FROM turns_fts WHERE turns_fts MATCH 'fibonacci'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "sess-completed"

def test_reindex_from_afr_imports_goals(tmp_home, tmp_path):
    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)

    new, skipped = indexer.reindex_from_afr(db_path=afr_db)

    assert new == 2
    assert skipped == 0
    conn = db.connect()
    sessions = conn.execute(
        "SELECT id, project, title, status FROM sessions ORDER BY started_at"
    ).fetchall()
    assert len(sessions) == 2
    assert sessions[0] == (
        "abc12345-0000-0000-0000-000000000000",
        "/projects/foo",
        "fix the modal deployment error",
        "shipped",
    )

    turns = conn.execute(
        """
        SELECT session_id, turn_idx, role, text
        FROM turns
        WHERE session_id='abc12345-0000-0000-0000-000000000000'
        ORDER BY turn_idx
        """
    ).fetchall()
    assert turns == [
        (
            "abc12345-0000-0000-0000-000000000000",
            0,
            "user",
            "fix the modal deployment error",
        ),
        (
            "abc12345-0000-0000-0000-000000000000",
            1,
            "assistant",
            "Fixed by adding huggingface-secret",
        ),
        (
            "abc12345-0000-0000-0000-000000000000",
            2,
            "user",
            "merged as PR #42 after fixing the secret",
        ),
    ]

def test_reindex_from_afr_skips_empty_tag_note(tmp_home, tmp_path):
    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)

    indexer.reindex_from_afr(db_path=afr_db)
    conn = db.connect()
    # The "def67890" row has empty tag_note — should produce only turn 0 (no final_summary, no note).
    turns = conn.execute(
        "SELECT turn_idx FROM turns WHERE session_id='def67890-0000-0000-0000-000000000000' ORDER BY turn_idx"
    ).fetchall()
    assert [t[0] for t in turns] == [0]


def test_reindex_from_afr_tolerates_missing_tag_note_column(tmp_home, tmp_path):
    """Older AFR DBs (pre-migration) lack the tag_note column. Indexer must not crash."""
    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db, with_tag_note=False)

    new, skipped = indexer.reindex_from_afr(db_path=afr_db)
    assert new == 2
    assert skipped == 0


def test_reindex_from_afr_tag_note_is_searchable(tmp_home, tmp_path):
    """The whole point — tag_note text must land in turns_fts so recall can match it."""
    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)
    indexer.reindex_from_afr(db_path=afr_db)
    conn = db.connect()
    hits = conn.execute(
        "SELECT session_id FROM turns_fts WHERE turns_fts MATCH ?", ("merged",)
    ).fetchall()
    assert any(h[0] == "abc12345-0000-0000-0000-000000000000" for h in hits)


def test_reindex_from_afr_backfills_existing_titles(tmp_home, tmp_path):
    """Sessions already indexed from JSONL (empty title/status) get refreshed from AFR."""
    # Pre-seed sessions table as if JSONL-indexed: blank title/status/summary.
    conn = db.connect()
    conn.execute(
        "INSERT INTO sessions (id, project, cwd, started_at, ended_at, title, status, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("abc12345-0000-0000-0000-000000000000", "/projects/foo", "/projects/foo",
         "2026-05-01T10:00:00", "2026-05-01T10:30:00", "", "untagged", "")
    )
    conn.commit()
    conn.close()

    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)
    new, skipped = indexer.reindex_from_afr(db_path=afr_db)

    # Existing row was updated (counted as skipped), new row inserted.
    assert skipped == 1
    assert new == 1

    conn = db.connect()
    title, status, summary = conn.execute(
        "SELECT title, status, summary FROM sessions WHERE id = ?",
        ("abc12345-0000-0000-0000-000000000000",)
    ).fetchone()
    assert title == "fix the modal deployment error"
    assert status == "shipped"
    assert summary == "Fixed by adding huggingface-secret"


def test_reindex_from_afr_backfill_preserves_existing_when_afr_blank(tmp_home, tmp_path):
    """If AFR has empty fields, existing sidekick values are preserved."""
    conn = db.connect()
    conn.execute(
        "INSERT INTO sessions (id, project, cwd, started_at, ended_at, title, status, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("def67890-0000-0000-0000-000000000000", "/projects/foo", "/projects/foo",
         "2026-05-02T11:00:00", "2026-05-02T11:10:00",
         "manually titled", "blocked", "manual summary")
    )
    conn.commit()
    conn.close()

    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)
    indexer.reindex_from_afr(db_path=afr_db)

    conn = db.connect()
    title, status, summary = conn.execute(
        "SELECT title, status, summary FROM sessions WHERE id = ?",
        ("def67890-0000-0000-0000-000000000000",)
    ).fetchone()
    # AFR's def67890 has user_goal="debug auth...", outcome="blocked", final_summary="".
    # Title gets updated (AFR has it), status replaced (AFR's is also "blocked"), summary preserved (AFR empty).
    assert title == "debug authentication middleware"  # AFR overwrote
    assert status == "blocked"
    assert summary == "manual summary"  # preserved — AFR's final_summary was empty


def test_reindex_from_afr_is_idempotent(tmp_home, tmp_path):
    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)

    indexer.reindex_from_afr(db_path=afr_db)
    new, skipped = indexer.reindex_from_afr(db_path=afr_db)

    assert new == 0
    assert skipped == 2
