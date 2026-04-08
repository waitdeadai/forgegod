from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from forgegod.agent import Agent
from forgegod.config import ForgeGodConfig
from forgegod.models import ModelUsage
from forgegod.tools import reset_tool_context, set_tool_context
from forgegod.tools.filesystem import grep_files, read_file, write_file
from forgegod.tools.shell import bash


class ScenarioRouter:
    """Deterministic router used by the local parity harness."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0

    async def call(self, **_kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response, ModelUsage(provider="zai", model="glm-5.1")


def _scoped_config(workspace: Path) -> ForgeGodConfig:
    config = ForgeGodConfig()
    config.project_dir = workspace / ".forgegod"
    config.project_dir.mkdir()
    return config


def _init_git_repo(workspace: Path) -> None:
    subprocess.run(
        ["git", "init"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
async def test_parity_read_file_roundtrip(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "hello.txt").write_text("hello forgegod\n", encoding="utf-8")

    router = ScenarioRouter([
        json.dumps({
            "tool_calls": [{
                "id": "call_1",
                "name": "read_file",
                "arguments": {"path": "hello.txt"},
            }]
        }),
        "The file says hello forgegod.",
    ])

    agent = Agent(
        config=_scoped_config(workspace),
        router=router,
        system_prompt="You are a test agent.",
        max_turns=4,
    )
    agent.memory = None

    result = await agent.run("Explain the contents of hello.txt")
    agent.budget.close()

    assert result.success is True
    assert result.files_modified == []
    assert "hello forgegod" in result.output
    assert router.calls == 2


@pytest.mark.asyncio
async def test_parity_grep_roundtrip(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    src = workspace / "src"
    src.mkdir()
    (src / "app.py").write_text(
        "def hello():\n    return 'world'\n\ndef orbit():\n    return 'cyan'\n",
        encoding="utf-8",
    )

    router = ScenarioRouter([
        json.dumps({
            "tool_calls": [{
                "id": "call_1",
                "name": "grep",
                "arguments": {"pattern": "def ", "path": "src", "file_type": "py"},
            }]
        }),
        "Found hello and orbit in src/app.py.",
    ])

    agent = Agent(
        config=_scoped_config(workspace),
        router=router,
        system_prompt="You are a test agent.",
        max_turns=4,
    )
    agent.memory = None

    result = await agent.run("Analyze the Python functions in src/")
    agent.budget.close()

    assert result.success is True
    assert "hello" in result.output
    assert router.calls == 2


@pytest.mark.asyncio
async def test_parity_write_file_allowed_workspace_scoped(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    config = _scoped_config(workspace)

    token = set_tool_context(config)
    try:
        result = await write_file("notes/ritual.md", "forgegod rises\n")
    finally:
        reset_tool_context(token)

    assert "Written" in result
    assert (workspace / "notes" / "ritual.md").read_text(encoding="utf-8") == "forgegod rises\n"


@pytest.mark.asyncio
async def test_parity_write_file_denied_workspace_escape(tmp_path):
    workspace = tmp_path / "repo"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    config = _scoped_config(workspace)

    token = set_tool_context(config)
    try:
        result = await write_file(str(outside / "escape.md"), "nope\n")
    finally:
        reset_tool_context(token)

    assert "escapes workspace root" in result


@pytest.mark.asyncio
async def test_parity_multi_tool_turn_roundtrip(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    src = workspace / "src"
    src.mkdir()
    (src / "main.py").write_text(
        "def main():\n    # TODO: tighten harness\n    return 'ok'\n",
        encoding="utf-8",
    )

    router = ScenarioRouter([
        json.dumps({
            "tool_calls": [
                {"id": "call_1", "name": "repo_map", "arguments": {"path": "."}},
                {"id": "call_2", "name": "grep", "arguments": {"pattern": "TODO", "path": "src"}},
            ]
        }),
        json.dumps({
            "tool_calls": [{
                "id": "call_3",
                "name": "read_file",
                "arguments": {"path": "src/main.py"},
            }]
        }),
        "The TODO is in src/main.py and asks to tighten the harness.",
    ])

    agent = Agent(
        config=_scoped_config(workspace),
        router=router,
        system_prompt="You are a test agent.",
        max_turns=5,
    )
    agent.memory = None

    result = await agent.run("Inspect the repo and summarize the TODO in src/main.py")
    agent.budget.close()

    assert result.success is True
    assert "tighten the harness" in result.output
    assert router.calls == 3


@pytest.mark.asyncio
async def test_parity_bash_stdout_roundtrip(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    config = _scoped_config(workspace)

    token = set_tool_context(config)
    try:
        result = await bash("python --version")
    finally:
        reset_tool_context(token)

    assert "Python" in result
    assert "[exit code: 0]" in result


@pytest.mark.asyncio
async def test_parity_completion_gate_roundtrip(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    _init_git_repo(workspace)

    router = ScenarioRouter([
        json.dumps({
            "tool_calls": [{
                "id": "call_1",
                "name": "write_file",
                "arguments": {"path": "src/app.py", "content": "print('forgegod')\n"},
            }]
        }),
        "Implemented src/app.py.",
        json.dumps({
            "tool_calls": [{
                "id": "call_2",
                "name": "bash",
                "arguments": {"command": "python -m pytest --version"},
            }]
        }),
        json.dumps({
            "tool_calls": [{
                "id": "call_3",
                "name": "git_diff",
                "arguments": {},
            }]
        }),
        "Implemented src/app.py with verification complete.",
    ])

    agent = Agent(
        config=_scoped_config(workspace),
        router=router,
        system_prompt="You are a test agent.",
        max_turns=8,
    )
    agent.memory = None

    result = await agent.run("Implement src/app.py")
    agent.budget.close()

    assert result.success is True
    assert result.files_modified == ["src/app.py"]
    assert result.reviewed_final_diff is True
    assert result.verification_commands == ["python -m pytest --version"]
    assert router.calls == 5


@pytest.mark.asyncio
async def test_parity_direct_tool_roundtrips_are_scoped(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    config = _scoped_config(workspace)
    (workspace / "notes.txt").write_text("cyan halo\n", encoding="utf-8")

    token = set_tool_context(config)
    try:
        read_result = await read_file("notes.txt")
        grep_result = await grep_files("cyan", ".")
    finally:
        reset_tool_context(token)

    assert "cyan halo" in read_result
    assert "notes.txt" in grep_result
