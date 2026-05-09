"""JSONL → Turn dataclasses. Pure parsing; no DB, no network."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

@dataclass(frozen=True)
class Turn:
    session_id: str
    turn_idx: int
    role: str
    text: str
    timestamp: str
    cwd: str | None
    input_tokens: int
    output_tokens: int
    byte_offset: int
    raw_type: str
    raw_subtype: str | None

def _flatten_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "tool_use":
                parts.append(f"[tool_use:{item.get('name','?')}]")
            elif item.get("type") == "tool_result":
                tr = item.get("content", "")
                if isinstance(tr, list):
                    tr = " ".join(p.get("text", "") for p in tr if isinstance(p, dict))
                parts.append(f"[tool_result:{tr[:500]}]")
        return "\n".join(parts)
    return ""

_MESSAGE_ROLES = {"user", "assistant"}


def parse_session_file(path: Path) -> Iterator[Turn]:
    """Yield Turn for each well-formed message line. Skip metadata events silently."""
    if not path.exists():
        return
    turn_idx = 0
    offset = 0
    with open(path, "rb") as f:
        for raw in f:
            line_offset = offset
            offset += len(raw)
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            session_id = obj.get("sessionId") or obj.get("session_id")
            if not session_id:
                continue
            msg = obj.get("message") or {}
            role = msg.get("role", "")
            # Skip metadata events (last-prompt, permission-mode, attachment, etc.)
            if role not in _MESSAGE_ROLES:
                continue
            text = _flatten_content(msg.get("content", ""))
            usage = msg.get("usage") or {}
            yield Turn(
                session_id=session_id,
                turn_idx=turn_idx,
                role=role,
                text=text,
                timestamp=obj.get("timestamp", ""),
                cwd=obj.get("cwd"),
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
                byte_offset=line_offset,
                raw_type=obj.get("type", ""),
                raw_subtype=obj.get("subtype"),
            )
            turn_idx += 1
