from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import toml
from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.sandbox import SandboxExecutionResult, SandboxUnavailableError
from forgegod.testing.mock_openai_service import SCENARIOS, start_mock_openai_server

runner = CliRunner()


def _write_config(
    workspace: Path,
    base_url: str,
    *,
    story_max_retries: int = 3,
    sandbox_mode: str = "standard",
) -> None:
    config = ForgeGodConfig()
    config.models.coder = "openai:gpt-5.4-mini"
    config.models.reviewer = "openai:gpt-5.4-mini"
    config.models.sentinel = "openai:gpt-5.4-mini"
    config.models.escalation = "openai:gpt-5.4-mini"
    config.openai.base_url = base_url
    config.review.always_review_run = False
    config.review.enabled = False
    config.memory.enabled = False
    config.memory.extraction_enabled = False
    config.agent.research_before_code = False
    config.security.sandbox_mode = sandbox_mode
    config.loop.cooldown_seconds = 0.0
    config.loop.story_max_retries = story_max_retries

    project_dir = workspace / ".forgegod"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "config.toml").write_text(
        toml.dumps(
            config.model_dump(
                mode="json",
                exclude={"global_dir", "project_dir"},
            )
        ),
        encoding="utf-8",
    )


def _init_git_repo(workspace: Path) -> None:
    subprocess.run(
        ["git", "init"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "forgegod@example.com"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "ForgeGod"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )
    (workspace / "README.md").write_text("forgegod\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )


def _write_prd(
    workspace: Path,
    *,
    story_id: str,
    title: str,
    description: str,
    acceptance_criteria: list[str] | None = None,
) -> Path:
    project_dir = workspace / ".forgegod"
    project_dir.mkdir(parents=True, exist_ok=True)
    prd_path = project_dir / "prd.json"
    prd_path.write_text(
        json.dumps(
            {
                "project": "ForgeGod CLI Loop Parity",
                "description": "Deterministic loop parity harness.",
                "stories": [
                    {
                        "id": story_id,
                        "title": title,
                        "description": description,
                        "status": "todo",
                        "priority": 1,
                        "acceptance_criteria": acceptance_criteria or [],
                        "depends_on": [],
                        "files_touched": [],
                        "iterations": 0,
                        "max_iterations": 5,
                        "error_log": [],
                        "completed_at": "",
                    }
                ],
                "guardrails": [],
                "learnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return prd_path


@pytest.mark.parametrize(
    (
        "scenario_name",
        "setup_kind",
        "expected_exit_code",
        "expected_output",
        "expected_path",
        "expected_contents",
        "expected_request_count",
    ),
    [
        (
            "cli_read_file_roundtrip",
            "hello",
            0,
            "The file says hello forgegod.",
            "hello.txt",
            "hello forgegod\n",
            2,
        ),
        (
            "cli_write_file_allowed",
            "git",
            0,
            "Created notes.txt successfully.",
            "notes.txt",
            "hello forgegod\n",
            3,
        ),
        (
            "cli_write_file_denied",
            "none",
            1,
            "ForgeGod blocked tool 'write_file'",
            "blocked.txt",
            None,
            1,
        ),
        (
            "cli_completion_gate_roundtrip",
            "git_src",
            0,
            "Files modified: src/app.py",
            "src/app.py",
            "print('forgegod')\n",
            3,
        ),
    ],
)
def test_cli_mock_parity_roundtrips(
    monkeypatch,
    tmp_path,
    scenario_name: str,
    setup_kind: str,
    expected_exit_code: int,
    expected_output: str,
    expected_path: str,
    expected_contents: str | None,
    expected_request_count: int,
):
    workspace = tmp_path / scenario_name
    workspace.mkdir()

    if setup_kind == "hello":
        (workspace / "hello.txt").write_text("hello forgegod\n", encoding="utf-8")
    elif setup_kind == "git":
        _init_git_repo(workspace)
    elif setup_kind == "git_src":
        _init_git_repo(workspace)
        (workspace / "src").mkdir()

    started = start_mock_openai_server(scenario_name)
    try:
        _write_config(workspace, started.base_url)

        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")

        scenario = SCENARIOS[scenario_name]
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--no-research",
                "--permission-mode",
                scenario.permission_mode,
                scenario.task,
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == expected_exit_code, result.stdout
    assert expected_output in result.stdout
    assert len(started.server.requests) == expected_request_count

    target = workspace / expected_path
    if expected_contents is None:
        assert not target.exists()
    else:
        assert target.read_text(encoding="utf-8") == expected_contents

    first_payload = started.server.requests[0]
    assert first_payload["model"] == "gpt-5.4-mini"
    assert "tools" in first_payload


def test_cli_mock_parity_captures_tool_result_turns(monkeypatch, tmp_path):
    workspace = tmp_path / "turn-capture"
    workspace.mkdir()
    (workspace / "hello.txt").write_text("hello forgegod\n", encoding="utf-8")

    started = start_mock_openai_server("cli_read_file_roundtrip")
    try:
        _write_config(workspace, started.base_url)
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--no-research",
                "--permission-mode",
                "read-only",
                "Explain the contents of hello.txt",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert len(started.server.requests) == 2

    second_messages = started.server.requests[1]["messages"]
    tool_messages = [msg for msg in second_messages if msg.get("role") == "tool"]
    assert tool_messages
    assert "hello forgegod" in tool_messages[-1]["content"]


def test_cli_prompt_approval_allows_write(monkeypatch, tmp_path):
    workspace = tmp_path / "prompt-approve"
    workspace.mkdir()
    _init_git_repo(workspace)

    started = start_mock_openai_server("cli_write_file_allowed")
    try:
        _write_config(workspace, started.base_url)
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--no-research",
                "--permission-mode",
                "read-only",
                "--approval-mode",
                "prompt",
                "Create notes.txt with the line hello forgegod",
            ],
            input="y\n",
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "Approval required" in result.stdout
    assert "Created notes.txt successfully." in result.stdout
    assert len(started.server.requests) == 3
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "hello forgegod\n"


def test_cli_prompt_approval_denies_write(monkeypatch, tmp_path):
    workspace = tmp_path / "prompt-deny"
    workspace.mkdir()
    _init_git_repo(workspace)

    started = start_mock_openai_server("cli_write_file_allowed")
    try:
        _write_config(workspace, started.base_url)
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--no-research",
                "--permission-mode",
                "read-only",
                "--approval-mode",
                "prompt",
                "Create notes.txt with the line hello forgegod",
            ],
            input="n\n",
        )
    finally:
        started.stop()

    assert result.exit_code == 1, result.stdout
    assert "Approval required" in result.stdout
    assert "ForgeGod blocked tool 'write_file'" in result.stdout
    assert len(started.server.requests) == 1
    assert not (workspace / "notes.txt").exists()


def test_cli_loop_completes_story_via_mock_provider(monkeypatch, tmp_path):
    workspace = tmp_path / "loop-success"
    workspace.mkdir()
    _init_git_repo(workspace)
    (workspace / "src").mkdir()

    started = start_mock_openai_server("cli_loop_story_success")
    try:
        _write_config(workspace, started.base_url)
        prd_path = _write_prd(
            workspace,
            story_id="T001",
            title="Create the app entrypoint",
            description="Implement src/app.py for the loop parity harness.",
        )
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "loop",
                "--prd",
                str(prd_path),
                "--workers",
                "1",
                "--max",
                "2",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "Completed: 1 | Failed: 0" in result.stdout
    assert len(started.server.requests) == 3
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == "print('forgegod loop')\n"

    prd_data = json.loads(prd_path.read_text(encoding="utf-8"))
    story = prd_data["stories"][0]
    assert story["status"] == "done"
    assert story["files_touched"] == ["src/app.py"]


def test_cli_loop_blocks_story_when_permissions_forbid_required_write(monkeypatch, tmp_path):
    workspace = tmp_path / "loop-blocked"
    workspace.mkdir()
    _init_git_repo(workspace)

    started = start_mock_openai_server("cli_loop_story_denied")
    try:
        _write_config(workspace, started.base_url, story_max_retries=1)
        prd_path = _write_prd(
            workspace,
            story_id="T002",
            title="Blocked write story",
            description="Attempt a forbidden write from the loop parity harness.",
        )
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "loop",
                "--prd",
                str(prd_path),
                "--workers",
                "1",
                "--max",
                "1",
                "--permission-mode",
                "read-only",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "Completed: 0 | Failed: 1" in result.stdout
    assert len(started.server.requests) == 1
    assert not (workspace / "blocked.txt").exists()

    prd_data = json.loads(prd_path.read_text(encoding="utf-8"))
    story = prd_data["stories"][0]
    assert story["status"] == "blocked"
    assert any("ForgeGod blocked tool 'write_file'" in entry for entry in story["error_log"])


def test_cli_loop_parallel_uses_worktree_path(monkeypatch, tmp_path):
    workspace = tmp_path / "loop-parallel-worktree"
    workspace.mkdir()
    _init_git_repo(workspace)
    (workspace / "src").mkdir()

    started = start_mock_openai_server("cli_loop_story_success")
    try:
        _write_config(workspace, started.base_url)
        prd_path = _write_prd(
            workspace,
            story_id="T003",
            title="Create the isolated app entrypoint",
            description="Implement src/app.py through the parallel worktree path.",
        )
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "loop",
                "--prd",
                str(prd_path),
                "--workers",
                "2",
                "--max",
                "2",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "Completed: 1 | Failed: 0" in result.stdout
    assert len(started.server.requests) == 3
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == "print('forgegod loop')\n"

    prd_data = json.loads(prd_path.read_text(encoding="utf-8"))
    story = prd_data["stories"][0]
    assert story["status"] == "done"
    assert story["files_touched"] == ["src/app.py"]

    worktree_root = workspace / ".forgegod" / "worktrees"
    if worktree_root.exists():
        assert not any(child.is_dir() for child in worktree_root.iterdir())


def test_cli_strict_bash_roundtrip_uses_real_sandbox_interface(monkeypatch, tmp_path):
    workspace = tmp_path / "strict-bash"
    workspace.mkdir()
    captured: dict[str, object] = {}

    async def fake_sandbox(**kwargs):
        captured.update(kwargs)
        return SandboxExecutionResult(
            backend="docker",
            returncode=0,
            stdout="Python 3.13.5\n",
            stderr="",
        )

    started = start_mock_openai_server("cli_strict_bash_roundtrip")
    try:
        _write_config(workspace, started.base_url, sandbox_mode="strict")
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        monkeypatch.setattr("forgegod.tools.shell.run_in_real_sandbox", fake_sandbox)
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--no-research",
                "--permission-mode",
                "read-only",
                "Run python --version and report it.",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "Strict sandbox reported Python 3.13.5." in result.stdout
    assert len(started.server.requests) == 2
    assert captured["argv"] == ["python", "--version"]
    assert captured["workspace_root"] == workspace.resolve()
    assert captured["security"].sandbox_mode == "strict"


def test_cli_strict_backend_unavailable_surfaces_block(monkeypatch, tmp_path):
    workspace = tmp_path / "strict-blocked"
    workspace.mkdir()

    async def fake_sandbox(**_kwargs):
        raise SandboxUnavailableError("Strict mode requires a real sandbox backend")

    started = start_mock_openai_server("cli_strict_backend_blocked")
    try:
        _write_config(workspace, started.base_url, sandbox_mode="strict")
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        monkeypatch.setattr("forgegod.tools.shell.run_in_real_sandbox", fake_sandbox)
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--no-research",
                "--permission-mode",
                "read-only",
                "Check whether strict sandbox execution is available.",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "backend is unavailable" in result.stdout
    assert len(started.server.requests) == 2
