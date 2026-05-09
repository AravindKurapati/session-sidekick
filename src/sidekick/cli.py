"""Click CLI: composition root."""
from __future__ import annotations
import io
import sys

import click

from sidekick import db, hooks as hooksmod, indexer
from sidekick import search as searchmod
from sidekick.paths import db_path

# Windows consoles default to cp1252; force UTF-8 so snippet output doesn't crash.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


@click.group()
def main() -> None:
    """session-sidekick: search & recall your Claude Code sessions."""


@main.command()
def reindex() -> None:
    """Incrementally index ~/.claude/projects/*.jsonl."""
    n = indexer.run()
    click.echo(f"indexed {n} new turn(s)")


@main.command(name="reindex-from-afr")
def reindex_from_afr() -> None:
    """Import sessions from AFR's ~/.afr/afr.db."""
    try:
        new, skipped = indexer.reindex_from_afr()
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Done. {new} new, {skipped} skipped.")


@main.command()
def stats() -> None:
    """Print database stats."""
    conn = db.connect()
    s = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    t = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    e = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    titled = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE titled_at IS NOT NULL"
    ).fetchone()[0]
    click.echo(f"db: {db_path()}")
    click.echo(f"sessions: {s} (titled: {titled})")
    click.echo(f"turns: {t}")
    click.echo(f"embeddings: {e}")


@main.command(name="list")
@click.option("--project", default=None, help="Filter by project name (substring).")
@click.option("--status", default=None, help="completed|abandoned|context_limit|unknown")
@click.option("--limit", default=20, type=int)
def list_sessions(project: str | None, status: str | None, limit: int) -> None:
    """List indexed sessions, most recent first."""
    conn = db.connect()
    sql = "SELECT id, project, title, status, ended_at FROM sessions WHERE 1=1"
    args: list = []
    if project:
        sql += " AND project LIKE ?"
        args.append(f"%{project}%")
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY ended_at DESC LIMIT ?"
    args.append(limit)
    for sid, proj, title, st, ended in conn.execute(sql, args):
        click.echo(f"{sid:<36}  {proj:<30}  {st or 'unknown':<12}  {title or '(untitled)'}")


@main.command()
def embed() -> None:
    """Embed any turns that don't yet have an embedding."""
    n = indexer.embed_pending()
    click.echo(f"embedded {n} turn(s)")


@main.command()
@click.argument("query")
@click.option("--project", default=None)
@click.option("--limit", default=10, type=int)
@click.option("--mode", type=click.Choice(["fts", "semantic", "combined"]), default="combined")
def search(query: str, project: str | None, limit: int, mode: str) -> None:
    """Search across all indexed sessions."""
    if mode == "fts":
        hits = searchmod.fts(query, limit=limit, project=project)
    elif mode == "semantic":
        hits = searchmod.semantic(query, limit=limit, project=project)
    else:
        hits = searchmod.combined(query, limit=limit, project=project)
    if not hits:
        click.echo("(no hits)")
        return
    for h in hits:
        score = h.get("score", 0.0)
        click.echo(f"{h['session_id']:<36}  turn {h['turn_idx']:>3}  score={score:.3f}  {h['project']:<25}  {h['snippet'][:120]}")


@main.command()
@click.argument("session_id")
@click.option("--full", is_flag=True, help="Print every turn's text.")
def show(session_id: str, full: bool) -> None:
    """Show a session by id (partial id supported)."""
    conn = db.connect()
    row = conn.execute(
        "SELECT id, project, title, summary, tags, status, ended_at FROM sessions WHERE id LIKE ?",
        (f"{session_id}%",),
    ).fetchone()
    if not row:
        click.echo(f"no session matching {session_id!r}")
        return
    click.echo(f"id:      {row[0]}")
    click.echo(f"project: {row[1]}")
    click.echo(f"title:   {row[2] or '(untitled)'}")
    click.echo(f"summary: {row[3] or '-'}")
    click.echo(f"tags:    {row[4] or '-'}")
    click.echo(f"status:  {row[5]}")
    click.echo(f"ended:   {row[6]}")
    if full:
        click.echo("---")
        for tidx, role, text in conn.execute(
            "SELECT turn_idx, role, text FROM turns WHERE session_id=? ORDER BY turn_idx", (row[0],)
        ):
            click.echo(f"[{tidx}] {role}: {text[:300]}")


@main.command(name="install-hooks")
@click.option("--apply", is_flag=True, help="Patch ~/.claude/settings.json. Otherwise prints snippet.")
def install_hooks(apply: bool) -> None:
    """Print or install the Claude Code hook config."""
    out = hooksmod.install(apply=apply)
    click.echo(out)


@main.command(name="stop-hook")
def stop_hook() -> None:
    """Run by Claude Code Stop event: index and embed new turns."""
    hooksmod.stop_hook()
