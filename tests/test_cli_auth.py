from __future__ import annotations

from typer.testing import CliRunner

from forgegod.cli import app

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

    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    assert "zai-coding-plan" in result.stdout
    assert "ready" in result.stdout
    assert "ZAI_CODING_API_KEY" in result.stdout
