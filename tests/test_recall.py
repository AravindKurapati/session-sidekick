import json
import shutil
import socket
import threading
import time
from pathlib import Path
from sidekick import daemon, indexer, recall
from sidekick.paths import claude_projects_dir, sidekick_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _seed():
    proj = claude_projects_dir() / "test-project"
    proj.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "completed.jsonl", proj / "completed.jsonl")


class _SlowDaemon:
    """Fake daemon that responds with a hit after `delay` seconds. Lets us test
    the recall client's socket budget deterministically without the real embedder."""

    def __init__(self, delay: float):
        self.delay = delay
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self._sock.settimeout(2.0)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        sidekick_dir().mkdir(parents=True, exist_ok=True)
        (sidekick_dir() / "daemon.port").write_text(str(self.port))
        self._thread.start()

    def _serve(self):
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        try:
            conn.makefile("rb").readline()
            time.sleep(self.delay)
            hit = {"ok": True, "hit": {"session_id": "abcdef12-0000",
                    "score": 0.9, "title": "prior work", "summary": "s",
                    "tags": "t", "ended_at": "2026-05-09"}}
            conn.sendall(json.dumps(hit).encode() + b"\n")
        finally:
            conn.close()

    def stop(self):
        try:
            self._sock.close()
        except OSError:
            pass


def test_recall_default_budget_survives_realistic_embed_latency(tmp_home, capsys):
    # Real warm embed round-trip is ~310-380ms; a 300ms budget silently drops it.
    # The default budget must clear a ~400ms response.
    srv = _SlowDaemon(delay=0.4)
    srv.start()
    try:
        rc = recall.run("anything")  # uses the default timeout_ms
        assert rc == 0
        assert "claude --resume abcdef12-0000" in capsys.readouterr().out
    finally:
        srv.stop()


def test_recall_old_300ms_budget_would_miss_slow_daemon(tmp_home, capsys):
    # Guards the regression: at the old 300ms budget the 400ms response is dropped.
    srv = _SlowDaemon(delay=0.4)
    srv.start()
    try:
        rc = recall.run("anything", timeout_ms=300)
        assert rc == 0
        assert capsys.readouterr().out == ""
    finally:
        srv.stop()

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
