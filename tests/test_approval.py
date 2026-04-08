from __future__ import annotations

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.tools import (
    execute_tool,
    load_all_tools,
    reset_tool_approver,
    reset_tool_context,
    set_tool_approver,
    set_tool_context,
)


@pytest.fixture(autouse=True)
def _load_tools():
    load_all_tools()


@pytest.mark.asyncio
async def test_approval_mode_approve_allows_blocked_write(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "read-only"
    config.security.approval_mode = "approve"

    token = set_tool_context(config)
    try:
        result = await execute_tool("write_file", {"path": "notes.txt", "content": "ok\n"})
    finally:
        reset_tool_context(token)

    assert "Written" in result
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "ok\n"


@pytest.mark.asyncio
async def test_approval_mode_prompt_uses_callback(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "read-only"
    config.security.approval_mode = "prompt"

    token = set_tool_context(config)
    approval_token = set_tool_approver(lambda *_args, **_kwargs: True)
    try:
        result = await execute_tool("write_file", {"path": "notes.txt", "content": "ok\n"})
    finally:
        reset_tool_approver(approval_token)
        reset_tool_context(token)

    assert "Written" in result
    assert (tmp_path / "notes.txt").exists()


@pytest.mark.asyncio
async def test_approval_mode_prompt_denied_keeps_block(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.security.permission_mode = "read-only"
    config.security.approval_mode = "prompt"

    token = set_tool_context(config)
    approval_token = set_tool_approver(lambda *_args, **_kwargs: False)
    try:
        result = await execute_tool("write_file", {"path": "notes.txt", "content": "ok\n"})
    finally:
        reset_tool_approver(approval_token)
        reset_tool_context(token)

    assert "blocked in read-only permission mode" in result
    assert not (tmp_path / "notes.txt").exists()
