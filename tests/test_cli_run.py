from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from forgegod.cli import _build_run_config, _safe_console_text, app
from forgegod.cli_ux import RunNarrator
from forgegod.config import ForgeGodConfig
from forgegod.models import AgentResult, ModelUsage, ResearchBrief, ReviewResult, ReviewVerdict

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


class FakeReviewerApprove:
    def __init__(self, *args, **kwargs):
        pass

    async def review(self, **_kwargs) -> ReviewResult:
        return ReviewResult(
            verdict=ReviewVerdict.APPROVE,
            reasoning="Looks good.",
        )


class SequencedAgent:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def run(self, _task: str) -> AgentResult:
        type(self).calls += 1
        if type(self).calls == 1:
            return AgentResult(
                success=True,
                output="Initial implementation.",
                files_modified=["src/app.py"],
                total_usage=ModelUsage(cost_usd=0.10, input_tokens=10, output_tokens=20),
                verification_commands=["python -m pytest -q"],
            )
        return AgentResult(
            success=True,
            output="Follow-up fix applied.",
            files_modified=["tests/test_app.py"],
            total_usage=ModelUsage(cost_usd=0.05, input_tokens=5, output_tokens=10),
            verification_commands=["ruff check forgegod tests"],
        )


class SequencedReviewer:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def review(self, **_kwargs) -> ReviewResult:
        type(self).calls += 1
        if type(self).calls == 1:
            return ReviewResult(
                verdict=ReviewVerdict.REVISE,
                reasoning="Tests need stronger proof.",
                issues=["Add stronger verification"],
            )
        return ReviewResult(
            verdict=ReviewVerdict.APPROVE,
            reasoning="Looks good now.",
        )


class FakeResearcher:
    def __init__(self, *args, **kwargs):
        pass

    async def research(self, task: str, depth=None) -> ResearchBrief:
        return ResearchBrief(
            task=task,
            best_practices=["Re-run pytest after applying the reviewer feedback."],
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


def test_root_interactive_session_propagates_runtime_flags(monkeypatch):
    prompts = iter(["Add a status page", "/exit"])
    calls: list[tuple[str, dict[str, object]]] = []
    printed: list[str] = []

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli._cli_is_interactive", lambda: True)
    monkeypatch.setattr("forgegod.cli.console.input", lambda *_args, **_kwargs: next(prompts))
    monkeypatch.setattr(
        "forgegod.cli.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )
    monkeypatch.setattr("forgegod.cli._ensure_project_bootstrap", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        "forgegod.cli._run_task_entrypoint",
        lambda task, **kwargs: calls.append((task, kwargs)) or 0,
    )

    result = runner.invoke(
        app,
        [
            "--terse",
            "--no-review",
            "--permission-mode",
            "read-only",
            "--approval-mode",
            "approve",
            "--allow-tool",
            "read_file",
            "--model",
            "ollama:qwen3-coder-next",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "Add a status page",
            {
                "model": "ollama:qwen3-coder-next",
                "review": False,
                "permission_mode": "read-only",
                "approval_mode": "approve",
                "allowed_tool": ["read_file"],
                "verbose": False,
                "terse": True,
                "show_banner": False,
                "subagents_enabled": None,
            },
        )
    ]
    visible = "\n".join(printed)
    assert "Caveman mode enabled" in visible


def test_root_interactive_session_propagates_subagents_flag(monkeypatch):
    prompts = iter(["Add a status page", "/exit"])
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli._cli_is_interactive", lambda: True)
    monkeypatch.setattr("forgegod.cli.console.input", lambda *_args, **_kwargs: next(prompts))
    monkeypatch.setattr("forgegod.cli.console.print", lambda *args, **_kwargs: None)
    monkeypatch.setattr("forgegod.cli._ensure_project_bootstrap", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        "forgegod.cli._run_task_entrypoint",
        lambda task, **kwargs: calls.append((task, kwargs)) or 0,
    )

    result = runner.invoke(app, ["--subagents"])

    assert result.exit_code == 0
    assert calls == [
        (
            "Add a status page",
            {
                "model": None,
                "review": True,
                "permission_mode": None,
                "approval_mode": None,
                "allowed_tool": None,
                "verbose": False,
                "terse": False,
                "show_banner": False,
                "subagents_enabled": True,
            },
        )
    ]


def test_run_command_propagates_subagents_flag(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        "forgegod.cli._run_task_entrypoint",
        lambda task, **kwargs: calls.append((task, kwargs)) or 0,
    )

    result = runner.invoke(app, ["run", "--subagents", "Implement the handler"])

    assert result.exit_code == 0
    assert calls == [
        (
            "Implement the handler",
            {
                "model": None,
                "review": True,
                "research": True,
                "permission_mode": None,
                "approval_mode": None,
                "allowed_tool": None,
                "verbose": False,
                "terse": False,
                "debug_wire": False,
                "json_out": None,
                "subagents_enabled": True,
            },
        )
    ]


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


def test_build_run_config_applies_terse_and_session_overrides(monkeypatch):
    config = ForgeGodConfig()

    monkeypatch.setattr("forgegod.cli._ensure_project_bootstrap", lambda *args, **kwargs: False)
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)

    built = _build_run_config(
        model="ollama:qwen3-coder-next",
        review=False,
        permission_mode="read-only",
        approval_mode="approve",
        allowed_tool=["read_file"],
        terse=True,
    )

    assert built.models.coder == "ollama:qwen3-coder-next"
    assert built.review.always_review_run is False
    assert built.security.permission_mode == "read-only"
    assert built.security.approval_mode == "approve"
    assert built.security.allowed_tools == ["read_file"]
    assert built.terse.enabled is True


def test_run_retries_once_after_bad_review_with_research(monkeypatch, tmp_path):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()

    config = ForgeGodConfig()
    config.project_dir = project_dir
    printed: list[str] = []
    SequencedAgent.calls = 0
    SequencedReviewer.calls = 0

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return FakeProc()

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "forgegod.cli.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)
    monkeypatch.setattr("forgegod.agent.Agent", SequencedAgent)
    monkeypatch.setattr("forgegod.reviewer.Reviewer", SequencedReviewer)
    monkeypatch.setattr("forgegod.researcher.Researcher", FakeResearcher)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda _config: FakeRouter())
    monkeypatch.setattr("forgegod.cli.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = runner.invoke(app, ["run", "Implement the handler"])

    assert result.exit_code == 0
    assert SequencedAgent.calls == 2
    assert SequencedReviewer.calls == 2
    joined = "\n".join(printed)
    assert "research-backed troubleshooting" in joined
    assert "Task completed" in joined


def test_run_json_out_writes_machine_readable_summary(monkeypatch, tmp_path):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    json_out = tmp_path / "result.json"

    config = ForgeGodConfig()
    config.project_dir = project_dir

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli.console.print", lambda *args, **_kwargs: None)
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)
    monkeypatch.setattr("forgegod.agent.Agent", FakeAgent)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda _config: FakeRouter())

    result = runner.invoke(
        app,
        ["run", "Implement the handler", "--no-review", "--json-out", str(json_out)],
    )

    assert result.exit_code == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["files_modified"] == ["src/app.py"]
    assert payload["verification_commands"] == ["python -m pytest -q"]


def test_worker_maps_payload_to_run_entrypoint(monkeypatch, tmp_path):
    payload_path = tmp_path / "payload.json"
    json_out = tmp_path / "worker-result.json"
    calls: list[tuple[str, dict[str, object]]] = []

    payload_path.write_text(
        json.dumps(
            {
                "task": "Implement the handler",
                "story_id": "T001",
                "review": False,
                "model": "openai:gpt-5.4-mini",
                "permission_mode": "workspace-write",
                "approval_mode": "approve",
                "allowed_tools": ["read_file", "write_file"],
                "terse": True,
                "subagents_enabled": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "forgegod.cli._run_task_entrypoint",
        lambda task, **kwargs: calls.append((task, kwargs)) or 0,
    )

    result = runner.invoke(
        app,
        ["worker", "--payload", str(payload_path), "--json-out", str(json_out)],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "Implement the handler",
            {
                "model": "openai:gpt-5.4-mini",
                "review": False,
                "permission_mode": "workspace-write",
                "approval_mode": "approve",
                "allowed_tool": ["read_file", "write_file"],
                "terse": True,
                "show_banner": False,
                "json_out": json_out,
                "story_id": "T001",
                "subagents_enabled": True,
            },
        )
    ]


def test_hive_command_invokes_coordinator(monkeypatch, tmp_path):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    prd = tmp_path / "prd.json"
    prd.write_text('{"project":"x","stories":[]}', encoding="utf-8")

    config = ForgeGodConfig()
    config.project_dir = project_dir
    printed: list[str] = []
    captured: list[tuple[str, int, int | None, bool]] = []

    class FakeCoordinator:
        def __init__(self, config, router):
            self.config = config

        async def run(self, prd_path, *, max_iterations, max_workers, dry_run):
            captured.append((str(prd_path), max_workers, max_iterations, dry_run))
            return type(
                "State",
                (),
                {
                    "stories_completed": 2,
                    "stories_failed": 0,
                    "total_iterations": 1,
                },
            )()

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "forgegod.cli.console.print",
        lambda *args, **_kwargs: printed.extend(_capture_print_arg(arg) for arg in args),
    )
    monkeypatch.setattr("forgegod.config.load_config", lambda: config)
    monkeypatch.setattr("forgegod.hive.HiveCoordinator", FakeCoordinator)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda _config: FakeRouter())

    result = runner.invoke(app, ["hive", "--prd", str(prd), "--workers", "3"])

    assert result.exit_code == 0
    assert captured == [(str(prd), 3, None, False)]
    assert any("Completed: 2 | Failed: 0 | Iterations: 1" in line for line in printed)
