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
