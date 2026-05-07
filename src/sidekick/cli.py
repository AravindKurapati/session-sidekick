"""Click CLI: composition root."""
from __future__ import annotations
import click
from sidekick import db, indexer
from sidekick.paths import db_path

@click.group()
def main() -> None:
    """session-sidekick: search & recall your Claude Code sessions."""

@main.command()
def reindex() -> None:
    """Incrementally index ~/.claude/projects/*.jsonl."""
    n = indexer.run()
    click.echo(f"indexed {n} new turn(s)")

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
