import shutil
from pathlib import Path
from click.testing import CliRunner
from sidekick.cli import main
from sidekick.paths import claude_projects_dir

FIXTURES = Path(__file__).parent / "fixtures"

def _seed(name="completed"):
    target_dir = claude_projects_dir() / "test-project"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / f"{name}.jsonl", target_dir / f"{name}.jsonl")

def test_reindex_then_stats(tmp_home):
    _seed()
    runner = CliRunner()
    r1 = runner.invoke(main, ["reindex"])
    assert r1.exit_code == 0, r1.output
    assert "3 new" in r1.output or "indexed 3" in r1.output.lower()
    r2 = runner.invoke(main, ["stats"])
    assert r2.exit_code == 0
    assert "sessions: 1" in r2.output.lower() or "1 session" in r2.output.lower()
    assert "turns: 3" in r2.output.lower() or "3 turn" in r2.output.lower()

def test_list_shows_session(tmp_home):
    _seed()
    runner = CliRunner()
    runner.invoke(main, ["reindex"])
    r = runner.invoke(main, ["list"])
    assert r.exit_code == 0
    assert "sess-completed" in r.output
    assert "test-project" in r.output

def test_list_filter_by_project(tmp_home):
    _seed("completed")
    _seed("abandoned")
    runner = CliRunner()
    runner.invoke(main, ["reindex"])
    r = runner.invoke(main, ["list", "--project", "test-project"])
    assert r.exit_code == 0
    assert "sess-completed" in r.output
    assert "sess-abandoned" in r.output
