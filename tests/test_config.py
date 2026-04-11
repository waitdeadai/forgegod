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
    openai_surface_label,
    recommend_model_defaults,
    resolve_openai_surface,
)
from forgegod.models import BudgetMode


def test_default_config():
    config = ForgeGodConfig()
    assert config.models.coder == "ollama:qwen3-coder-next"
    assert config.harness.profile == "adversarial"
    assert config.harness.preferred_provider == "auto"
    assert config.harness.openai_surface == "auto"
    assert config.budget.daily_limit_usd == 5.0
    assert config.budget.mode == BudgetMode.NORMAL
    assert config.loop.max_iterations == 100
    assert config.loop.auto_commit_success is False
    assert config.loop.auto_push_success is False
    assert config.memory.enabled is True
    assert config.memory.extraction_enabled is True
    assert config.security.sandbox_backend == "auto"
    assert config.security.sandbox_image == "auto"
    assert config.openai_codex.command == "codex"
    assert config.openai_codex.sandbox == "read-only"
    assert config.openai.reasoning_effort == "medium"
    assert config.openai.verbosity == "medium"
    assert config.openai.parallel_tool_calls is True
    assert config.zai.use_coding_plan is True
    assert config.zai.coding_plan_base_url == "https://api.z.ai/api/coding/paas/v4"


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
        assert data["budget"]["mode"] == "normal"


def test_load_config_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(Path(tmpdir))
        assert config.models.planner == "openai:gpt-5.4"
        assert config.ollama.host == "http://localhost:11434"


def test_recommend_model_defaults_openai_codex_only():
    models = recommend_model_defaults(
        ["openai-codex"],
        ollama_available=False,
        codex_automation_supported=True,
    )
    assert models.planner == "openai-codex:gpt-5.4"
    assert models.reviewer == "openai-codex:gpt-5.4"
    assert models.sentinel == "openai-codex:gpt-5.4"


def test_recommend_model_defaults_prefers_zai_when_no_local():
    models = recommend_model_defaults(["zai"], ollama_available=False)
    assert models.coder == "zai:glm-5.1"
    assert models.planner == "zai:glm-5.1"


def test_recommend_model_defaults_prefers_zai_over_ollama_when_cloud_ready():
    models = recommend_model_defaults(["zai"], ollama_available=True)
    assert models.coder == "zai:glm-5.1"


def test_recommend_model_defaults_single_model_unifies_roles():
    models = recommend_model_defaults(
        ["zai", "openai-codex"],
        ollama_available=False,
        codex_automation_supported=True,
        profile="single-model",
    )
    assert models.planner == "zai:glm-5.1"
    assert models.coder == "zai:glm-5.1"
    assert models.reviewer == "zai:glm-5.1"
    assert models.sentinel == "zai:glm-5.1"
    assert models.escalation == "zai:glm-5.1"
    assert models.researcher == "zai:glm-5.1"


def test_recommend_model_defaults_openai_preference_biases_openai_surfaces():
    models = recommend_model_defaults(
        ["zai", "openai", "openai-codex"],
        ollama_available=False,
        codex_automation_supported=True,
        preferred_provider="openai",
    )
    assert models.planner == "openai:gpt-5.4"
    assert models.coder == "openai:gpt-5.4-mini"
    assert models.reviewer == "openai-codex:gpt-5.4"
    assert models.sentinel == "openai:gpt-5.4"
    assert models.escalation == "openai:gpt-5.4"
    assert models.researcher == "openai:gpt-5.4-mini"


def test_recommend_model_defaults_openai_surface_api_only():
    models = recommend_model_defaults(
        ["openai", "openai-codex", "zai"],
        ollama_available=False,
        codex_automation_supported=True,
        openai_surface="api-only",
    )
    assert models.planner == "openai:gpt-5.4"
    assert models.coder == "openai:gpt-5.4-mini"
    assert models.reviewer == "openai:gpt-5.4"
    assert models.sentinel == "openai:gpt-5.4"
    assert models.researcher == "openai:gpt-5.4-mini"


def test_recommend_model_defaults_openai_surface_codex_only():
    models = recommend_model_defaults(
        ["openai", "openai-codex", "zai"],
        ollama_available=False,
        codex_automation_supported=True,
        openai_surface="codex-only",
    )
    assert models.planner == "openai-codex:gpt-5.4"
    assert models.coder == "openai-codex:gpt-5.4"
    assert models.reviewer == "openai-codex:gpt-5.4"
    assert models.sentinel == "openai-codex:gpt-5.4"
    assert models.escalation == "openai-codex:gpt-5.4"
    assert models.researcher == "openai-codex:gpt-5.4"


def test_recommend_model_defaults_openai_surface_api_plus_codex():
    models = recommend_model_defaults(
        ["openai", "openai-codex", "zai"],
        ollama_available=False,
        codex_automation_supported=True,
        openai_surface="api+codex",
    )
    assert models.planner == "openai:gpt-5.4"
    assert models.coder == "openai:gpt-5.4-mini"
    assert models.reviewer == "openai-codex:gpt-5.4"
    assert models.sentinel == "openai:gpt-5.4"
    assert models.escalation == "openai:gpt-5.4"
    assert models.researcher == "openai:gpt-5.4-mini"


def test_resolve_openai_surface_degrades_cleanly():
    assert resolve_openai_surface("api+codex", {"openai", "openai-codex"}) == "api+codex"
    assert resolve_openai_surface("api+codex", {"openai"}) == "api-only"
    assert resolve_openai_surface("api+codex", {"openai-codex"}) == "codex-only"
    assert resolve_openai_surface("api-only", {"openai-codex"}) == "codex-only"
    assert resolve_openai_surface("codex-only", {"openai"}) == "api-only"
    assert openai_surface_label("api+codex") == "api+codex"


def test_init_project_writes_model_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        models = recommend_model_defaults(
            ["openai-codex"],
            ollama_available=False,
            codex_automation_supported=True,
        )
        project_dir = init_project(
            Path(tmpdir),
            model_defaults=models,
            harness_profile="single-model",
            preferred_provider="openai",
            openai_surface="api+codex",
        )
        data = toml.loads((project_dir / "config.toml").read_text(encoding="utf-8"))
        assert data["models"]["planner"] == "openai-codex:gpt-5.4"
        assert data["harness"]["profile"] == "single-model"
        assert data["harness"]["preferred_provider"] == "openai"
        assert data["harness"]["openai_surface"] == "api+codex"


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
