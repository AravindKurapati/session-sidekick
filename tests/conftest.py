import pytest
from pathlib import Path

@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Redirect ~/.session-sidekick and ~/.claude to a tmp dir for tests."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows
    (home / ".claude" / "projects").mkdir(parents=True)
    return home
