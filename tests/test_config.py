"""Tests for ForgeGod configuration."""

import tempfile
from pathlib import Path

import toml

from forgegod.config import (
    ForgeGodConfig,
    _coerce,
    _deep_merge,
    _env_overrides,
    init_project,
    load_config,
)
from forgegod.models import BudgetMode


def test_default_config():
    config = ForgeGodConfig()
    assert config.models.coder == "ollama:qwen3-coder-next"
    assert config.budget.daily_limit_usd == 5.0
    assert config.budget.mode == BudgetMode.NORMAL
    assert config.loop.max_iterations == 100
    assert config.loop.auto_commit_success is False
    assert config.loop.auto_push_success is False
    assert config.security.sandbox_backend == "auto"
    assert config.security.sandbox_image == "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm"


def test_deep_merge():
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    override = {"a": 2, "nested": {"y": 3, "z": 4}}
    result = _deep_merge(base, override)
    assert result["a"] == 2
    assert result["nested"]["x"] == 1
    assert result["nested"]["y"] == 3
    assert result["nested"]["z"] == 4


def test_coerce():
    assert _coerce("true") is True
    assert _coerce("false") is False
    assert _coerce("42") == 42
    assert _coerce("3.14") == 3.14
    assert _coerce("hello") == "hello"


def test_init_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = init_project(Path(tmpdir))
        assert project_dir.exists()
        assert (project_dir / "config.toml").exists()
        assert (project_dir / "logs").exists()

        # Verify config is valid TOML
        config_text = (project_dir / "config.toml").read_text()
        data = toml.loads(config_text)
        assert "models" in data
        assert "budget" in data


def test_load_config_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(Path(tmpdir))
        assert config.models.planner == "openai:gpt-4o-mini"
        assert config.ollama.host == "http://localhost:11434"


def test_load_config_from_toml():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / ".forgegod"
        project_dir.mkdir()
        (project_dir / "config.toml").write_text(
            '[budget]\ndaily_limit_usd = 10.0\nmode = "throttle"\n'
        )
        config = load_config(Path(tmpdir))
        assert config.budget.daily_limit_usd == 10.0
        assert config.budget.mode == BudgetMode.THROTTLE


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("FORGEGOD_BUDGET_DAILY_LIMIT_USD", "20.0")
    overrides = _env_overrides()
    assert overrides.get("budget", {}).get("daily_limit_usd") == 20.0
