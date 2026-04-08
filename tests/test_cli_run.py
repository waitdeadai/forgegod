from __future__ import annotations

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.models import AgentResult, ModelUsage, ReviewResult, ReviewVerdict

runner = CliRunner()


class FakeRouter:
    async def close(self):
        return None


class FakeAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def run(self, _task: str) -> AgentResult:
        return AgentResult(
            success=True,
            output="Implemented the change.",
            files_modified=["src/app.py"],
            total_usage=ModelUsage(cost_usd=0.12, input_tokens=10, output_tokens=20),
            verification_commands=["python -m pytest -q"],
        )


class FakeReviewer:
    def __init__(self, *args, **kwargs):
        pass

    async def review(self, **_kwargs) -> ReviewResult:
        return ReviewResult(
            verdict=ReviewVerdict.REVISE,
            reasoning="Need stronger verification evidence.",
            issues=["Missing acceptance proof"],
        )


class FakeProc:
    returncode = 0

    async def communicate(self):
        return b"diff --git a/src/app.py b/src/app.py", b""


def test_run_blocks_when_reviewer_requests_revision(monkeypatch, tmp_path):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()

    config = ForgeGodConfig()
    config.project_dir = project_dir

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return FakeProc()

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)
    monkeypatch.setattr("forgegod.agent.Agent", FakeAgent)
    monkeypatch.setattr("forgegod.reviewer.Reviewer", FakeReviewer)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda _config: FakeRouter())
    monkeypatch.setattr("forgegod.cli.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = runner.invoke(app, ["run", "Implement the handler"])

    assert result.exit_code == 1
    assert "Reviewer blocked completion" in result.stdout
    assert "Missing acceptance proof" in result.stdout
