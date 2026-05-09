import shutil
from pathlib import Path
from click.testing import CliRunner
from sidekick import indexer, search
from sidekick.cli import main
from sidekick.paths import claude_projects_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _seed_all():
    proj = claude_projects_dir() / "test-project"
    proj.mkdir(parents=True, exist_ok=True)
    for name in ("completed", "abandoned", "context_limit"):
        shutil.copy(FIXTURES / f"{name}.jsonl", proj / f"{name}.jsonl")

def test_fts_finds_keyword(tmp_home):
    _seed_all()
    indexer.run()
    hits = search.fts("fibonacci", limit=10)
    assert len(hits) == 1
    assert hits[0]["session_id"] == "sess-completed"

def test_fts_returns_snippet(tmp_home):
    _seed_all()
    indexer.run()
    hits = search.fts("fibonacci", limit=10)
    assert "fibonacci" in hits[0]["snippet"].lower()

def test_search_command_prints_session_id(tmp_home):
    _seed_all()
    indexer.run()
    runner = CliRunner()
    r = runner.invoke(main, ["search", "fibonacci"])
    assert r.exit_code == 0
    assert "sess-completed" in r.output

def test_semantic_finds_similar(tmp_home):
    _seed_all()
    indexer.run()
    indexer.embed_pending(batch_size=8)
    hits = search.semantic("recursive math function", limit=5)
    assert any(h["session_id"] == "sess-completed" for h in hits)

def test_combined_returns_both_modes(tmp_home):
    _seed_all()
    indexer.run()
    indexer.embed_pending()
    hits = search.combined("fibonacci recursive", limit=10)
    assert len(hits) >= 1
    assert all("score" in h and "mode" in h for h in hits)

def test_shipped_sessions_rank_higher():
    results = search._apply_outcome_boost([
        {"session_id": "blocked", "status": "blocked", "score": 0.9},
        {"session_id": "shipped", "status": "shipped", "score": 0.8},
    ])

    assert results[0]["session_id"] == "shipped"
    assert results[0]["score"] == 1.04
