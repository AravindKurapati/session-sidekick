import json
import shutil
import socket
import time
from pathlib import Path
from sidekick import daemon, indexer
from sidekick.paths import claude_projects_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _seed():
    proj = claude_projects_dir() / "test-project"
    proj.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "completed.jsonl", proj / "completed.jsonl")

def _send_request(addr, payload: dict) -> dict:
    if isinstance(addr, tuple):
        s = socket.create_connection(addr, timeout=2.0)
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(addr)
    s.sendall(json.dumps(payload).encode() + b"\n")
    f = s.makefile("rb")
    line = f.readline()
    s.close()
    return json.loads(line)

def test_daemon_recall_returns_hit(tmp_home):
    _seed()
    indexer.run()
    indexer.embed_pending()
    srv = daemon.Server()
    srv.start()
    try:
        time.sleep(0.2)
        resp = _send_request(srv.address, {"op": "recall", "prompt": "fibonacci recursion"})
        assert resp["ok"] is True
        assert "hit" in resp
        assert resp["hit"] is None or resp["hit"]["session_id"] == "sess-completed"
    finally:
        srv.stop()

def test_daemon_ping(tmp_home):
    _seed()
    srv = daemon.Server()
    srv.start()
    try:
        time.sleep(0.2)
        resp = _send_request(srv.address, {"op": "ping"})
        assert resp == {"ok": True, "pong": True}
    finally:
        srv.stop()
