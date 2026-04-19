from __future__ import annotations

from io import StringIO

import pytest
import toml
from rich.console import Console
from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig, ModelsConfig
from forgegod.models import BudgetMode

runner = CliRunner()


@pytest.fixture
def printed(monkeypatch):
    buffer = StringIO()
    capture_console = Console(file=buffer, force_terminal=False, width=120)

    monkeypatch.setattr(
        "forgegod.cli.console.print",
        capture_console.print,
    )
    return buffer


def test_auth_status_loads_project_dotenv(tmp_path, monkeypatch, printed):
    project_env = tmp_path / ".forgegod"
    project_env.mkdir()
    (project_env / ".env").write_text("ZAI_CODING_API_KEY=test-value\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZAI_CODING_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        "forgegod.native_auth.codex_login_status_sync",
        lambda: (False, "Not logged in"),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (False, "Codex CLI not found on native Windows and WSL is not installed."),
    )

    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    visible = printed.getvalue()
    assert "zai-coding-plan" in visible
    assert "ready" in visible
    assert "ZAI_CODING_API_KEY" in visible


def test_auth_status_loads_global_dotenv(tmp_path, monkeypatch, printed):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / ".env").write_text("MINIMAX_API_KEY=test-global\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FORGEGOD_GLOBAL_DIR", str(global_dir))
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_CODING_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        "forgegod.native_auth.codex_login_status_sync",
        lambda: (False, "Not logged in"),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (False, "Codex CLI not found on native Windows and WSL is not installed."),
    )

    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    visible = printed.getvalue()
    assert "minimax" in visible
    assert "ready" in visible
    assert "MINIMAX_API_KEY" in visible


def test_auth_status_marks_codex_needs_setup_when_logged_in(tmp_path, monkeypatch, printed):
    project_env = tmp_path / ".forgegod"
    project_env.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "forgegod.native_auth.codex_login_status_sync",
        lambda: (True, "Logged in using ChatGPT"),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (False, "Use WSL for best Windows experience"),
    )

    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    visible = printed.getvalue()
    assert "needs setup" in visible
    assert "Use WSL for best Windows experience" in visible


def test_auth_status_ready_codex_mentions_live_probe(tmp_path, monkeypatch, printed):
    project_env = tmp_path / ".forgegod"
    project_env.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "forgegod.native_auth.codex_login_status_sync",
        lambda: (True, "Logged in using ChatGPT"),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (True, "Codex automation supported"),
    )

    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    visible = printed.getvalue()
    assert "openai-codex" in visible
    assert "ready" in visible
    assert "openai-live" in visible


def test_auth_sync_rewrites_models_and_normalizes_budget(tmp_path, monkeypatch, printed):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()

    config = ForgeGodConfig()
    config.budget.mode = BudgetMode.LOCAL_ONLY
    config.budget.daily_limit_usd = 0.0
    (project_dir / "config.toml").write_text(
        toml.dumps(config.model_dump(mode="json", exclude={"global_dir", "project_dir"})),
        encoding="utf-8",
    )

    recommended = ModelsConfig(
        planner="openai-codex:gpt-5.4",
        coder="zai:glm-5.1",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai-codex:gpt-5.4",
        escalation="openai-codex:gpt-5.4",
        researcher="openai-codex:gpt-5.4",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai-codex:gpt-5.4", "zai:glm-5.1"],
            ["openai-codex", "zai"],
            False,
            recommended,
        ),
    )

    result = runner.invoke(app, ["auth", "sync", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    updated = toml.loads((project_dir / "config.toml").read_text(encoding="utf-8"))
    assert updated["models"] == recommended.model_dump()
    assert updated["harness"]["profile"] == "adversarial"
    assert updated["harness"]["preferred_provider"] == "auto"
    assert updated["harness"]["openai_surface"] == "auto"
    assert updated["budget"]["mode"] == "normal"
    assert updated["budget"]["daily_limit_usd"] == 5.0
    visible = printed.getvalue()
    assert "zai:glm-5.1" in visible
    assert "openai-codex:gpt-5.4" in visible
    assert "cloud-ready config ensured" in visible
    assert "Provider preference:" in visible
    assert "Requested OpenAI surface:" in visible
    assert "Effective OpenAI surface:" in visible


def test_auth_sync_persists_minimax_region_preset(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="minimax:MiniMax-M2.7-highspeed",
        coder="minimax:MiniMax-M2.7-highspeed",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai-codex:gpt-5.4",
        escalation="openai-codex:gpt-5.4",
        researcher="openai-codex:gpt-5.4",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["minimax:MiniMax-M2.7-highspeed", "openai-codex:gpt-5.4"],
            ["minimax", "openai-codex"],
            False,
            recommended,
        ),
    )

    result = runner.invoke(
        app,
        ["auth", "sync", "--path", str(tmp_path), "--minimax-region", "global"],
    )

    assert result.exit_code == 0, result.stdout
    updated = toml.loads(
        (tmp_path / ".forgegod" / "config.toml").read_text(encoding="utf-8")
    )
    assert updated["minimax"]["region"] == "global"
    assert updated["minimax"]["base_url"] == "auto"
    assert "MiniMax region preset:" in printed.getvalue()


def test_auth_sync_shows_codex_coder_production_note(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="openai-codex:gpt-5.4",
        coder="openai-codex:gpt-5.4",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai-codex:gpt-5.4",
        escalation="openai-codex:gpt-5.4",
        researcher="openai-codex:gpt-5.4",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai-codex:gpt-5.4"],
            ["openai-codex"],
            False,
            recommended,
        ),
    )

    result = runner.invoke(app, ["auth", "sync", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    normalized = " ".join(printed.getvalue().split())
    assert "production-ready ForgeGod surface" in normalized


def test_auth_sync_notes_when_codex_is_detected_but_not_selected(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="zai:glm-5.1",
        coder="zai:glm-5.1",
        reviewer="zai:glm-5.1",
        sentinel="zai:glm-5.1",
        escalation="zai:glm-5.1",
        researcher="zai:glm-5.1",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai-codex:gpt-5.4", "zai:glm-5.1"],
            ["openai-codex", "zai"],
            False,
            recommended,
        ),
    )

    result = runner.invoke(app, ["auth", "sync", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    normalized = " ".join(printed.getvalue().split())
    assert "did not choose it as a default automation backend" in normalized


def test_auth_sync_single_model_profile(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="zai:glm-5.1",
        coder="zai:glm-5.1",
        reviewer="zai:glm-5.1",
        sentinel="zai:glm-5.1",
        escalation="zai:glm-5.1",
        researcher="zai:glm-5.1",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["zai:glm-5.1"],
            ["zai"],
            False,
            recommended,
        ),
    )

    result = runner.invoke(
        app,
        ["auth", "sync", "--path", str(tmp_path), "--profile", "single-model"],
    )

    assert result.exit_code == 0, result.stdout
    updated = toml.loads(
        (tmp_path / ".forgegod" / "config.toml").read_text(encoding="utf-8")
    )
    assert updated["harness"]["profile"] == "single-model"
    assert updated["harness"]["preferred_provider"] == "auto"
    visible = printed.getvalue()
    assert "Harness profile:" in visible
    assert "single-model" in visible


def test_auth_sync_openai_preference(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="openai:gpt-5.4",
        coder="openai:gpt-5.4-mini",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai:gpt-5.4",
        escalation="openai:gpt-5.4",
        researcher="openai:gpt-5.4-mini",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai:gpt-5.4-mini", "openai-codex:gpt-5.4", "zai:glm-5.1"],
            ["openai", "openai-codex", "zai"],
            False,
            recommended,
        ),
    )

    result = runner.invoke(
        app,
        ["auth", "sync", "--path", str(tmp_path), "--prefer-provider", "openai"],
    )

    assert result.exit_code == 0, result.stdout
    updated = toml.loads(
        (tmp_path / ".forgegod" / "config.toml").read_text(encoding="utf-8")
    )
    assert updated["harness"]["preferred_provider"] == "openai"
    assert updated["models"]["planner"] == "openai:gpt-5.4"
    normalized = " ".join(printed.getvalue().split())
    assert "Provider preference:" in normalized
    assert "openai" in normalized


def test_auth_sync_openai_surface_hybrid(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="openai:gpt-5.4",
        coder="openai:gpt-5.4-mini",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai:gpt-5.4",
        escalation="openai:gpt-5.4",
        researcher="openai:gpt-5.4-mini",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai:gpt-5.4-mini", "openai-codex:gpt-5.4"],
            ["openai", "openai-codex"],
            False,
            recommended,
        ),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (True, "Supported"),
    )

    result = runner.invoke(
        app,
        [
            "auth",
            "sync",
            "--path",
            str(tmp_path),
            "--prefer-provider",
            "openai",
            "--openai-surface",
            "api+codex",
        ],
    )

    assert result.exit_code == 0, result.stdout
    updated = toml.loads(
        (tmp_path / ".forgegod" / "config.toml").read_text(encoding="utf-8")
    )
    assert updated["harness"]["openai_surface"] == "api+codex"
    normalized = " ".join(printed.getvalue().split())
    assert "Requested OpenAI surface:" in normalized
    assert "api+codex" in normalized
    assert "Effective OpenAI surface:" in normalized


def test_auth_sync_openai_surface_fallback(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="openai-codex:gpt-5.4",
        coder="openai-codex:gpt-5.4",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai-codex:gpt-5.4",
        escalation="openai-codex:gpt-5.4",
        researcher="openai-codex:gpt-5.4",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai-codex:gpt-5.4"],
            ["openai-codex"],
            False,
            recommended,
        ),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (True, "Supported"),
    )

    result = runner.invoke(
        app,
        [
            "auth",
            "sync",
            "--path",
            str(tmp_path),
            "--openai-surface",
            "api+codex",
        ],
    )

    assert result.exit_code == 0, result.stdout
    normalized = " ".join(printed.getvalue().split())
    assert "OpenAI surface fallback:" in normalized
    assert "requested api+codex" in normalized
    assert "codex-only" in normalized


def test_auth_explain_shows_effective_surface(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="openai:gpt-5.4",
        coder="openai:gpt-5.4-mini",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai:gpt-5.4",
        escalation="openai:gpt-5.4",
        researcher="openai:gpt-5.4-mini",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai:gpt-5.4-mini", "openai-codex:gpt-5.4"],
            ["openai", "openai-codex"],
            False,
            recommended,
        ),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (True, "Supported"),
    )

    result = runner.invoke(
        app,
        ["auth", "explain", "--path", str(tmp_path), "--openai-surface", "api+codex"],
    )

    assert result.exit_code == 0, result.stdout
    visible = printed.getvalue()
    assert "Requested OpenAI surface" in visible
    assert "Effective OpenAI surface" in visible
    assert "Role Mapping" in visible
    assert "openai-codex:gpt-5.4" in visible


def test_auth_explain_shows_minimax_region_preset(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="minimax:MiniMax-M2.7-highspeed",
        coder="minimax:MiniMax-M2.7-highspeed",
        reviewer="openai-codex:gpt-5.4",
        sentinel="openai-codex:gpt-5.4",
        escalation="openai-codex:gpt-5.4",
        researcher="openai-codex:gpt-5.4",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["minimax:MiniMax-M2.7-highspeed", "openai-codex:gpt-5.4"],
            ["minimax", "openai-codex"],
            False,
            recommended,
        ),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (True, "Supported"),
    )

    result = runner.invoke(
        app,
        ["auth", "explain", "--path", str(tmp_path), "--minimax-region", "global"],
    )

    assert result.exit_code == 0, result.stdout
    visible = printed.getvalue()
    assert "MiniMax region preset" in visible
    assert "global" in visible


def test_auth_explain_downgrades_when_codex_is_not_supported(tmp_path, monkeypatch, printed):
    recommended = ModelsConfig(
        planner="zai:glm-5.1",
        coder="zai:glm-5.1",
        reviewer="zai:glm-5.1",
        sentinel="zai:glm-5.1",
        escalation="zai:glm-5.1",
        researcher="zai:glm-5.1",
    )

    monkeypatch.setattr(
        "forgegod.cli._detect_runtime_model_defaults",
        lambda *_args, **_kwargs: (
            ["openai-codex:gpt-5.4", "zai:glm-5.1"],
            ["openai-codex", "zai"],
            False,
            recommended,
        ),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (False, "Use WSL for best Windows experience"),
    )

    result = runner.invoke(
        app,
        ["auth", "explain", "--path", str(tmp_path), "--openai-surface", "api+codex"],
    )

    assert result.exit_code == 0, result.stdout
    visible = printed.getvalue()
    assert "Effective OpenAI surface" in visible
    assert "auto" in visible
    assert "OpenAI surface fallback" in visible


def test_init_quick_writes_openai_surface(tmp_path, monkeypatch, printed):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(
        "forgegod.native_auth.codex_login_status_sync",
        lambda: (True, "Logged in using ChatGPT"),
    )
    monkeypatch.setattr(
        "forgegod.native_auth.codex_automation_status",
        lambda: (True, "Supported"),
    )
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("no ollama")),
    )

    result = runner.invoke(
        app,
        [
            "init",
            str(tmp_path),
            "--quick",
            "--prefer-provider",
            "openai",
            "--openai-surface",
            "api+codex",
        ],
    )

    assert result.exit_code == 0, result.stdout
    config_path = tmp_path / ".forgegod" / "config.toml"
    data = toml.loads(config_path.read_text(encoding="utf-8"))
    assert data["harness"]["openai_surface"] == "api+codex"
    assert data["models"]["reviewer"] == "openai-codex:gpt-5.4"
    assert data["models"]["planner"] == "openai:gpt-5.4"


def test_auth_verify_minimax_success(tmp_path, monkeypatch, printed):
    async def fake_verify(*_args, **_kwargs):
        return True, "MiniMax-M2.7-highspeed OK via https://api.minimax.io/v1 -> OK"

    monkeypatch.setattr(
        "forgegod.doctor.verify_minimax_live",
        fake_verify,
    )

    result = runner.invoke(
        app,
        ["auth", "verify", "minimax", "--path", str(tmp_path), "--region", "global"],
    )

    assert result.exit_code == 0, result.stdout
    visible = printed.getvalue()
    assert "Live MiniMax probe:" in visible
    assert "region=global" in visible
    assert "MiniMax live verification passed" in visible


def test_auth_verify_minimax_failure(tmp_path, monkeypatch, printed):
    async def fake_verify(*_args, **_kwargs):
        return False, "https://api.minimaxi.com/v1: 401 invalid api key (2049)"

    monkeypatch.setattr(
        "forgegod.doctor.verify_minimax_live",
        fake_verify,
    )

    result = runner.invoke(
        app,
        ["auth", "verify", "minimax", "--path", str(tmp_path), "--region", "cn"],
    )

    assert result.exit_code == 1, result.stdout
    visible = printed.getvalue()
    assert "Live MiniMax probe:" in visible
    assert "region=cn" in visible
    assert "MiniMax live verification failed" in visible
