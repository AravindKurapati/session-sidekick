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
    ]

def test_reindex_from_afr_is_idempotent(tmp_home, tmp_path):
    afr_db = tmp_path / "afr.db"
    make_afr_db(afr_db)

    indexer.reindex_from_afr(db_path=afr_db)
    new, skipped = indexer.reindex_from_afr(db_path=afr_db)

    assert new == 0
    assert skipped == 2
