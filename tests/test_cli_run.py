from __future__ import annotations

from typer.testing import CliRunner

from forgegod.cli import _safe_console_text, app
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


def _capture_print_arg(renderable) -> str:
    body = getattr(renderable, "renderable", renderable)
    return str(body)


def test_safe_console_text_replaces_unencodable_chars(monkeypatch):
    class FakeFile:
        encoding = "cp1252"

    monkeypatch.setattr("forgegod.cli.console.file", FakeFile())

    result = _safe_console_text("### ❌ ALL commands BLOCKED")
    assert "❌" not in result
    assert "?" in result


def test_run_blocks_when_reviewer_requests_revision(monkeypatch, tmp_path):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()

    config = ForgeGodConfig()
    config.project_dir = project_dir
    printed: list[str] = []

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return FakeProc()

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "forgegod.cli.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)
    monkeypatch.setattr("forgegod.agent.Agent", FakeAgent)
    monkeypatch.setattr("forgegod.reviewer.Reviewer", FakeReviewer)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda _config: FakeRouter())
    monkeypatch.setattr("forgegod.cli.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = runner.invoke(app, ["run", "Implement the handler"])

    assert result.exit_code == 1
    joined = "\n".join(printed)
    assert "Reviewer blocked completion" in joined
    assert "Missing acceptance proof" in joined
