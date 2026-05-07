"""Haiku-powered titler + heuristic status detection."""
from __future__ import annotations
import datetime as dt
import json
import os
from sidekick import db

MODEL = "claude-haiku-4-5-20251001"

PROMPT_TEMPLATE = """You are summarizing a developer's coding session with an AI assistant.

Output STRICT JSON with this schema:
{{
  "title": "<5-word title in lowercase, no punctuation>",
  "tags": ["<tag1>", "<tag2>", "<tag3>"],
  "summary": "<one sentence describing what got done or what was attempted>"
}}

Only output JSON. No prose, no markdown fences.

First user prompts:
{first_user_prompts}

Last assistant turns:
{last_assistant_turns}
"""

def _client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def detect_status(session_id: str) -> str:
    conn = db.connect()
    rows = conn.execute(
        "SELECT role, text, input_tokens FROM turns WHERE session_id=? ORDER BY turn_idx",
        (session_id,),
    ).fetchall()
    if not rows:
        return "unknown"
    last_text = (rows[-1][1] or "").lower()
    if "compact" in last_text or "context auto-compact" in last_text:
        return "context_limit"
    max_input = max((r[2] or 0) for r in rows)
    if max_input > 180000:
        return "context_limit"
    last_user = [r for r in rows if r[0] == "user"][-3:]
    short_corrections = sum(
        1 for r in last_user
        if len((r[1] or "").strip()) <= 12
        and any(w in (r[1] or "").lower() for w in ("no", "stop", "forget", "nope", "cancel"))
    )
    if short_corrections >= 2:
        return "abandoned"
    return "completed"

def _build_prompt(session_id: str) -> str:
    conn = db.connect()
    user_rows = conn.execute(
        "SELECT text FROM turns WHERE session_id=? AND role='user' ORDER BY turn_idx LIMIT 5",
        (session_id,),
    ).fetchall()
    asst_rows = conn.execute(
        "SELECT text FROM turns WHERE session_id=? AND role='assistant' ORDER BY turn_idx DESC LIMIT 3",
        (session_id,),
    ).fetchall()
    first_user = "\n---\n".join(r[0][:800] for r in user_rows)
    last_asst = "\n---\n".join(r[0][:800] for r in reversed(asst_rows))
    return PROMPT_TEMPLATE.format(
        first_user_prompts=first_user or "(none)",
        last_assistant_turns=last_asst or "(none)",
    )

def title_session(session_id: str) -> dict | None:
    """Call Haiku, parse JSON, persist to sessions row. Returns the parsed dict or None."""
    status = detect_status(session_id)
    prompt = _build_prompt(session_id)
    client = _client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text if resp.content else ""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    title = (data.get("title") or "").strip().lower()[:80]
    tags = ",".join((data.get("tags") or [])[:3])
    summary = (data.get("summary") or "").strip()[:300]
    conn = db.connect()
    conn.execute(
        """
        UPDATE sessions
        SET title=?, tags=?, summary=?, status=?, titled_at=?
        WHERE id=?
        """,
        (title, tags, summary, status, dt.datetime.utcnow().isoformat(), session_id),
    )
    return {"title": title, "tags": tags, "summary": summary, "status": status}

def main() -> None:
    """Entry: `sidekick-titler <session_id>` — titles untitled sessions if no arg."""
    import sys
    if len(sys.argv) > 1:
        title_session(sys.argv[1])
        return
    conn = db.connect()
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM sessions WHERE titled_at IS NULL LIMIT 50"
    ).fetchall()]
    for sid in ids:
        try:
            title_session(sid)
        except Exception as e:
            print(f"titler error on {sid}: {e}", file=__import__("sys").stderr)
