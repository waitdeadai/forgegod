from __future__ import annotations

import pytest
from typer.testing import CliRunner

from forgegod.cli import _build_run_config, _safe_console_text, app
from forgegod.cli_ux import RunNarrator
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


@pytest.mark.asyncio
async def test_run_narrator_reports_human_activity(monkeypatch):
    printed: list[str] = []

    monkeypatch.setattr(
        "forgegod.cli_ux.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )

    narrator = RunNarrator()
    await narrator("task_started")
    await narrator(
        "tool_batch_started",
        tools=[{"name": "read_file", "arguments": {"path": "src/app.py"}}],
    )
    await narrator("task_completed", files_modified=["src/app.py"])

    joined = "\n".join(printed)
    assert "plain language" in joined
    assert "Inspecting the repository" in joined
    assert "finished the patch" in joined


def test_root_no_args_prints_guidance_when_not_tty(monkeypatch):
    printed: list[str] = []

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli._cli_is_interactive", lambda: False)
    monkeypatch.setattr(
        "forgegod.cli.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    visible = "\n".join(printed)
    assert "natural-language session" in visible
    assert "forgegod run" in visible


def test_root_interactive_session_runs_task_and_exits(monkeypatch):
    prompts = iter(["Add a status page", "/exit"])
    tasks: list[str] = []
    printed: list[str] = []

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli._cli_is_interactive", lambda: True)
    monkeypatch.setattr("forgegod.cli.console.input", lambda *_args, **_kwargs: next(prompts))
    monkeypatch.setattr(
        "forgegod.cli.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )
    monkeypatch.setattr(
        "forgegod.cli._run_task_entrypoint",
        lambda task, **_kwargs: tasks.append(task) or 0,
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert tasks == ["Add a status page"]
    visible = "\n".join(printed)
    assert "Talk to ForgeGod in natural language" in visible


def test_root_interactive_session_bootstraps_project(monkeypatch):
    prompts = iter(["/exit"])
    bootstrap_calls: list[dict[str, object]] = []

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli._cli_is_interactive", lambda: True)
    monkeypatch.setattr("forgegod.cli.console.input", lambda *_args, **_kwargs: next(prompts))
    monkeypatch.setattr("forgegod.cli.console.print", lambda *args, **_kwargs: None)
    monkeypatch.setattr(
        "forgegod.cli._ensure_project_bootstrap",
        lambda *args, **kwargs: bootstrap_calls.append(kwargs) or True,
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert bootstrap_calls == [{"announce": True}]


def test_build_run_config_bootstraps_project(monkeypatch):
    config = ForgeGodConfig()
    bootstrap_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "forgegod.cli._ensure_project_bootstrap",
        lambda *args, **kwargs: bootstrap_calls.append(kwargs) or True,
    )
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)

    built = _build_run_config()

    assert built is config
    assert bootstrap_calls == [{"announce": False}]
