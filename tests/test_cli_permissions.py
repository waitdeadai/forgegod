from __future__ import annotations

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig

runner = CliRunner()


def test_permissions_command_shows_read_only_mode(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)

    result = runner.invoke(
        app,
        ["permissions", "--permission-mode", "read-only", "--approval-mode", "prompt"],
    )

    assert result.exit_code == 0
    assert "ForgeGod Permissions" in result.stdout
    assert "read-only" in result.stdout
    assert "prompt" in result.stdout
    assert "Blocked Tools" in result.stdout


def test_permissions_command_shows_allowlist_override(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)

    result = runner.invoke(
        app,
        ["permissions", "--allowed-tool", "read_file", "--allowed-tool", "grep"],
    )

    assert result.exit_code == 0
    assert "read_file, grep" in result.stdout or "grep, read_file" in result.stdout
