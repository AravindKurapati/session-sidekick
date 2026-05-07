"""Search functions. FTS5 first; semantic added in Task 8."""
from __future__ import annotations
from sidekick import db

def fts(query: str, limit: int = 20, project: str | None = None) -> list[dict]:
    """FTS5 keyword search. Returns ranked hits with snippet."""
    conn = db.connect()
    sql = """
        SELECT t.session_id, t.turn_idx, t.role, s.project,
               snippet(turns_fts, 0, '[[', ']]', '...', 12) AS snippet,
               s.title
        FROM turns_fts JOIN turns t ON t.rowid = turns_fts.rowid
        JOIN sessions s ON s.id = t.session_id
        WHERE turns_fts MATCH ?
    """
    args: list = [query]
    if project:
        sql += " AND s.project LIKE ?"
        args.append(f"%{project}%")
    sql += " ORDER BY rank LIMIT ?"
    args.append(limit)
    return [
        {"session_id": r[0], "turn_idx": r[1], "role": r[2],
         "project": r[3], "snippet": r[4], "title": r[5]}
        for r in conn.execute(sql, args).fetchall()
    ]

def semantic(query: str, limit: int = 20, project: str | None = None) -> list[dict]:
    """Cosine similarity over stored embeddings. Implemented in Task 8."""
    return []

def combined(query: str, limit: int = 20, project: str | None = None) -> list[dict]:
    """RRF fusion of FTS and semantic. Falls back to FTS only until Task 8."""
    fts_hits = fts(query, limit=limit, project=project)
    for h in fts_hits:
        h.setdefault("score", 0.0)
        h.setdefault("mode", "fts")
    return fts_hits
