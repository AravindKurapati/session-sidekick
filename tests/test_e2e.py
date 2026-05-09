"""End-to-end: index → embed → daemon → recall round-trip on the fixture corpus."""
import json
import shutil
import socket
import time
from pathlib import Path
from sidekick import daemon, indexer
from sidekick.paths import claude_projects_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _send(addr, payload):
    if isinstance(addr, tuple):
        s = socket.create_connection(addr, timeout=2.0)
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(addr)
    s.sendall(json.dumps(payload).encode() + b"\n")
    line = s.makefile("rb").readline()
    s.close()
    return json.loads(line)

def test_e2e_full_pipeline(tmp_home):
    proj = claude_projects_dir() / "myproj"
    proj.mkdir(parents=True, exist_ok=True)
    for name in ("completed", "abandoned"):
        shutil.copy(FIXTURES / f"{name}.jsonl", proj / f"{name}.jsonl")

    indexer.run()
    indexer.embed_pending()

    srv = daemon.Server()
    srv.start()
    time.sleep(0.2)
    try:
        assert _send(srv.address, {"op": "ping"}) == {"ok": True, "pong": True}
        resp = _send(srv.address, {"op": "recall", "prompt": "compute fibonacci sequence"})
        assert resp["ok"] is True
    finally:
        srv.stop()
