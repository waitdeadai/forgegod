from __future__ import annotations

import toml
from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig, ModelsConfig
from forgegod.models import BudgetMode

runner = CliRunner()


def test_auth_status_loads_project_dotenv(tmp_path, monkeypatch):
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
        lambda: (False, "Codex CLI automation is experimental on native Windows."),
    )

    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    assert "zai-coding-plan" in result.stdout
    assert "ready" in result.stdout
    assert "ZAI_CODING_API_KEY" in result.stdout


def test_auth_status_marks_codex_experimental_when_logged_in(tmp_path, monkeypatch):
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
    assert "experimental" in result.stdout
    assert "Use WSL for best Windows experience" in result.stdout


def test_auth_sync_rewrites_models_and_normalizes_budget(tmp_path, monkeypatch):
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
    assert updated["budget"]["mode"] == "normal"
    assert updated["budget"]["daily_limit_usd"] == 5.0
    assert "zai:glm-5.1" in result.stdout
    assert "openai-codex:gpt-5.4" in result.stdout
    assert "cloud-ready config ensured" in result.stdout


def test_auth_sync_shows_codex_coder_experimental_note(tmp_path, monkeypatch):
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
    assert "coder-loop use remains experimental" in result.stdout


def test_auth_sync_notes_when_codex_is_detected_but_not_selected(tmp_path, monkeypatch):
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
    normalized = " ".join(result.stdout.split())
    assert "did not choose it as a default automation backend" in normalized


def test_auth_sync_single_model_profile(tmp_path, monkeypatch):
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
    assert "Harness profile:" in result.stdout
    assert "single-model" in result.stdout
