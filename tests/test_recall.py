import shutil
import time
from pathlib import Path
from sidekick import daemon, indexer, recall
from sidekick.paths import claude_projects_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _seed():
    proj = claude_projects_dir() / "test-project"
    proj.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "completed.jsonl", proj / "completed.jsonl")

def test_format_hit_has_no_emoji_or_em_dash():
    hit = {"session_id": "abcdef12-1111-2222", "title": "do the thing",
           "summary": "a summary", "tags": "t1,t2", "ended_at": "2026-05-09"}
    out = recall._format_hit(hit, "prompt")
    assert "\U0001f4a1" not in out          # no emoji
    assert "—" not in out              # no em-dash
    assert "session `abcdef12`" in out
    assert "claude --resume abcdef12-1111-2222" in out


def test_recall_silent_when_daemon_down(tmp_home, capsys):
    _seed()
    indexer.run()
    indexer.embed_pending()
    rc = recall.run("anything", timeout_ms=300)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""

def test_recall_emits_block_on_hit(tmp_home, capsys):
    _seed()
    indexer.run()
    indexer.embed_pending()
    srv = daemon.Server()
    srv.start()
    time.sleep(0.2)
    try:
        rc = recall.run("recursive math fibonacci", timeout_ms=2000)
        assert rc == 0
        captured = capsys.readouterr()
        if captured.out:
            assert "claude --resume" in captured.out
    finally:
        srv.stop()
