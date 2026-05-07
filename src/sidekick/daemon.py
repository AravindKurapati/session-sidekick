"""Local socket daemon. Unix domain socket on POSIX, TCP localhost on Windows."""
from __future__ import annotations
import json
import os
import socket
import sys
import threading
from sidekick import db, search
from sidekick.embeddings import Embedder
from sidekick.paths import sidekick_dir

CONFIDENCE_THRESHOLD = 0.78

def _socket_address():
    if sys.platform == "win32":
        return ("127.0.0.1", 0)
    return str(sidekick_dir() / "daemon.sock")

class Server:
    def __init__(self) -> None:
        self._address = None
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._embedder: Embedder | None = None

    @property
    def address(self):
        return self._address

    def start(self) -> None:
        if sys.platform == "win32":
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.bind(("127.0.0.1", 0))
            self._address = self._sock.getsockname()
            (sidekick_dir() / "daemon.port").write_text(str(self._address[1]))
        else:
            path = _socket_address()
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.bind(path)
            self._address = path
        self._sock.listen(8)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            self._sock.close()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            f = conn.makefile("rb")
            line = f.readline()
            req = json.loads(line)
            resp = self._dispatch(req)
            conn.sendall(json.dumps(resp).encode() + b"\n")
        except Exception as e:
            try:
                conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode() + b"\n")
            except OSError:
                pass
        finally:
            conn.close()

    def _dispatch(self, req: dict) -> dict:
        op = req.get("op")
        if op == "ping":
            return {"ok": True, "pong": True}
        if op == "recall":
            return self._recall(req.get("prompt", ""), req.get("project"))
        return {"ok": False, "error": f"unknown op: {op}"}

    def _recall(self, prompt: str, project: str | None) -> dict:
        if not prompt.strip():
            return {"ok": True, "hit": None}
        if self._embedder is None:
            self._embedder = Embedder()
        hits = search.semantic(prompt, limit=5, project=project)
        if not hits:
            return {"ok": True, "hit": None}
        top = hits[0]
        if top["score"] < CONFIDENCE_THRESHOLD:
            return {"ok": True, "hit": None}
        conn = db.connect()
        row = conn.execute(
            "SELECT title, summary, tags, ended_at FROM sessions WHERE id=?",
            (top["session_id"],),
        ).fetchone()
        conn.close()
        title, summary, tags, ended = row if row else (None, None, None, None)
        return {
            "ok": True,
            "hit": {
                "session_id": top["session_id"],
                "score": top["score"],
                "title": title,
                "summary": summary,
                "tags": tags,
                "ended_at": ended,
            },
        }

def main() -> None:
    """Entry point: `sidekick-daemon`. Runs forever."""
    srv = Server()
    srv.start()
    addr = srv.address
    print(f"sidekick-daemon listening on {addr}", flush=True)
    try:
        srv._thread.join()
    except KeyboardInterrupt:
        srv.stop()
