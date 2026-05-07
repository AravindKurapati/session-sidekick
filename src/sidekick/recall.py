"""Recall client. Invoked by the UserPromptSubmit hook. Always returns 0."""
from __future__ import annotations
import json
import socket
import sys
from sidekick.paths import sidekick_dir

def _daemon_address():
    if sys.platform == "win32":
        port_file = sidekick_dir() / "daemon.port"
        if not port_file.exists():
            return None
        try:
            return ("127.0.0.1", int(port_file.read_text().strip()))
        except ValueError:
            return None
    sock = sidekick_dir() / "daemon.sock"
    return str(sock) if sock.exists() else None

def _connect(addr, timeout: float) -> socket.socket | None:
    try:
        if isinstance(addr, tuple):
            return socket.create_connection(addr, timeout=timeout)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(addr)
        return s
    except OSError:
        return None

def _format_hit(hit: dict, prompt: str) -> str:
    title = hit.get("title") or "(untitled session)"
    summary = hit.get("summary") or ""
    tags = hit.get("tags") or ""
    sid = hit["session_id"]
    ended = hit.get("ended_at", "")
    return (
        f"\U0001f4a1 You may have done this before — session `{sid[:8]}` ({ended[:10]}): {title}\n"
        f"   {summary}\n"
        f"   Tags: {tags}\n"
        f"   Resume with: claude --resume {sid}\n"
    )

def run(prompt: str, project: str | None = None, timeout_ms: int = 300) -> int:
    """Print hint to stdout if confident match; otherwise silent. Always exits 0."""
    addr = _daemon_address()
    if not addr:
        return 0
    timeout = timeout_ms / 1000.0
    sock = _connect(addr, timeout)
    if not sock:
        return 0
    try:
        sock.sendall(json.dumps({"op": "recall", "prompt": prompt, "project": project}).encode() + b"\n")
        f = sock.makefile("rb")
        line = f.readline()
        resp = json.loads(line)
        if resp.get("ok") and resp.get("hit"):
            print(_format_hit(resp["hit"], prompt))
    except (OSError, json.JSONDecodeError):
        pass
    finally:
        sock.close()
    return 0

def main() -> None:
    """Entry: `sidekick-recall`. Reads the prompt from stdin."""
    prompt = sys.stdin.read()
    sys.exit(run(prompt))
