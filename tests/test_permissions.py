from __future__ import annotations

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.tools import execute_tool, load_all_tools, reset_tool_context, set_tool_context


@pytest.fixture(autouse=True)
def _load_tools():
    load_all_tools()


@pytest.mark.asyncio
async def test_read_only_mode_blocks_write_file(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "read-only"

    token = set_tool_context(config)
    try:
        result = await execute_tool(
            "write_file",
            {"path": "notes.txt", "content": "blocked\n"},
        )
    finally:
        reset_tool_context(token)

    assert "blocked in read-only permission mode" in result
    assert not (tmp_path / "notes.txt").exists()


@pytest.mark.asyncio
async def test_read_only_mode_allows_safe_bash(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "read-only"

    token = set_tool_context(config)
    try:
        result = await execute_tool("bash", {"command": "python --version"})
    finally:
        reset_tool_context(token)

    assert "Python" in result
    assert "[exit code: 0]" in result


@pytest.mark.asyncio
async def test_workspace_write_mode_blocks_git_commit(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "workspace-write"

    token = set_tool_context(config)
    try:
        result = await execute_tool("git_commit", {"message": "test"})
    finally:
        reset_tool_context(token)

    assert "blocked in workspace-write permission mode" in result


@pytest.mark.asyncio
async def test_allowed_tools_override_blocks_otherwise_allowed_tool(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "danger-full-access"
    config.security.allowed_tools = ["read_file"]
    target = tmp_path / "notes.txt"
    target.write_text("cyan\n", encoding="utf-8")

    token = set_tool_context(config)
    try:
        blocked = await execute_tool("grep", {"pattern": "cyan", "path": "."})
        allowed = await execute_tool("read_file", {"path": str(target)})
    finally:
        reset_tool_context(token)

    assert "not in the allowed tool list" in blocked
    assert "cyan" in allowed
