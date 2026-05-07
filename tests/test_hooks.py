import json
from pathlib import Path
from click.testing import CliRunner
from sidekick.cli import main
from sidekick import hooks

def test_build_hook_config_has_required_events():
    cfg = hooks.build_hook_config()
    assert "Stop" in cfg
    assert "UserPromptSubmit" in cfg

def test_install_hooks_dry_run_prints(tmp_home):
    runner = CliRunner()
    r = runner.invoke(main, ["install-hooks"])
    assert r.exit_code == 0
    assert "Stop" in r.output
    assert "UserPromptSubmit" in r.output
    settings_path = tmp_home / ".claude" / "settings.json"
    assert not settings_path.exists()

def test_install_hooks_apply_writes_settings(tmp_home):
    runner = CliRunner()
    r = runner.invoke(main, ["install-hooks", "--apply"])
    assert r.exit_code == 0
    settings_path = tmp_home / ".claude" / "settings.json"
    assert settings_path.exists()
    cfg = json.loads(settings_path.read_text())
    assert "hooks" in cfg
    assert "Stop" in cfg["hooks"]
    assert "UserPromptSubmit" in cfg["hooks"]

def test_install_hooks_apply_preserves_existing(tmp_home):
    settings_path = tmp_home / ".claude" / "settings.json"
    settings_path.write_text(json.dumps({"someOther": True, "hooks": {"OtherEvent": []}}))
    runner = CliRunner()
    r = runner.invoke(main, ["install-hooks", "--apply"])
    assert r.exit_code == 0
    cfg = json.loads(settings_path.read_text())
    assert cfg["someOther"] is True
    assert "OtherEvent" in cfg["hooks"]
    assert "Stop" in cfg["hooks"]
