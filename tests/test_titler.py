import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from sidekick import db, indexer, titler
from sidekick.paths import claude_projects_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _seed(name: str):
    proj = claude_projects_dir() / "test-project"
    proj.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / f"{name}.jsonl", proj / f"{name}.jsonl")

def test_detect_status_completed(tmp_home):
    _seed("completed")
    indexer.run()
    assert titler.detect_status("sess-completed") == "completed"

def test_detect_status_abandoned(tmp_home):
    _seed("abandoned")
    indexer.run()
    assert titler.detect_status("sess-abandoned") == "abandoned"

def test_detect_status_context_limit(tmp_home):
    _seed("context_limit")
    indexer.run()
    assert titler.detect_status("sess-ctx") == "context_limit"

def test_title_persists_to_db(tmp_home):
    _seed("completed")
    indexer.run()
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text='{"title":"add fibonacci function","tags":["fibonacci","python","math"],"summary":"Added a fib helper"}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    with patch("sidekick.titler._client", return_value=fake_client):
        titler.title_session("sess-completed")
    conn = db.connect()
    row = conn.execute(
        "SELECT title, tags, summary, status, titled_at FROM sessions WHERE id='sess-completed'"
    ).fetchone()
    assert row[0] == "add fibonacci function"
    assert "fibonacci" in row[1]
    assert row[2] == "Added a fib helper"
    assert row[3] == "completed"
    assert row[4] is not None
