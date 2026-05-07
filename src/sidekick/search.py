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

import numpy as np
from sidekick.embeddings import Embedder, from_blob

_embedder: Embedder | None = None

def _embedder_singleton() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder

def semantic(query: str, limit: int = 20, project: str | None = None) -> list[dict]:
    """Cosine similarity over stored embeddings."""
    conn = db.connect()
    sql = """
        SELECT e.session_id, e.turn_idx, e.vec, t.text, t.role, s.project, s.title
        FROM embeddings e
        JOIN turns t ON t.session_id=e.session_id AND t.turn_idx=e.turn_idx
        JOIN sessions s ON s.id=e.session_id
    """
    args: list = []
    if project:
        sql += " WHERE s.project LIKE ?"
        args.append(f"%{project}%")
    rows = conn.execute(sql, args).fetchall()
    if not rows:
        return []
    qv = _embedder_singleton().embed_one(query)
    scored = []
    for sid, tidx, blob, text, role, proj, title in rows:
        v = from_blob(blob)
        score = float(np.dot(qv, v))
        scored.append({
            "session_id": sid, "turn_idx": tidx, "role": role,
            "project": proj, "title": title,
            "snippet": text[:200], "score": score,
        })
    scored.sort(key=lambda h: h["score"], reverse=True)
    return scored[:limit]

def combined(query: str, limit: int = 20, project: str | None = None) -> list[dict]:
    """RRF fusion of FTS and semantic."""
    fts_hits = fts(query, limit=limit * 2, project=project)
    sem_hits = semantic(query, limit=limit * 2, project=project)
    k = 60.0
    rrf: dict[tuple[str, int], dict] = {}
    for rank, h in enumerate(fts_hits, start=1):
        key = (h["session_id"], h["turn_idx"])
        rrf.setdefault(key, {**h, "score": 0.0, "mode": "fts"})
        rrf[key]["score"] += 1.0 / (k + rank)
    for rank, h in enumerate(sem_hits, start=1):
        key = (h["session_id"], h["turn_idx"])
        rrf.setdefault(key, {**h, "score": 0.0, "mode": "semantic"})
        rrf[key]["score"] += 1.0 / (k + rank)
        if rrf[key].get("mode") != "semantic":
            rrf[key]["mode"] = "hybrid"
    out = sorted(rrf.values(), key=lambda h: h["score"], reverse=True)
    return out[:limit]
