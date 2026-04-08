from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.models import AgentResult, Story
from forgegod.worktree import WorktreePool


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


def test_worktree_pool_blocks_prompt_approval_with_parallel_workers(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.loop.parallel_workers = 2
    config.security.approval_mode = "prompt"

    with pytest.raises(
        ValueError,
        match="Prompt approval mode is only supported with WorktreePool max_workers=1",
    ):
        WorktreePool(config=config)


def test_worktree_pool_requires_prompt_callback(tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.loop.parallel_workers = 1
    config.security.approval_mode = "prompt"

    with pytest.raises(
        ValueError,
        match="Prompt approval mode requires a tool_approver callback",
    ):
        WorktreePool(config=config)


@pytest.mark.asyncio
async def test_worktree_pool_passes_tool_approver_to_worker_agent(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.loop.parallel_workers = 1
    config.security.approval_mode = "prompt"

    story = Story(
        id="T1",
        title="Write the note",
        description="Create a file in the worker tree.",
        acceptance_criteria=["notes.txt exists"],
    )
    approver = object()
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            captured["tool_approver"] = kwargs.get("tool_approver")
            captured["project_dir"] = kwargs["config"].project_dir

        async def run(self, _prompt: str) -> AgentResult:
            return AgentResult(success=True, files_modified=["notes.txt"])

    async def fake_create_worktree(self, path: str, _branch: str) -> bool:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True

    async def fake_cleanup_all(self):
        self._workers.clear()

    monkeypatch.setattr("forgegod.worktree.Agent", FakeAgent)
    monkeypatch.setattr(WorktreePool, "_create_worktree", fake_create_worktree)
    monkeypatch.setattr(WorktreePool, "_cleanup_all", fake_cleanup_all)

    pool = WorktreePool(config=config, max_workers=1, tool_approver=approver)
    results = await pool.run_parallel([story])

    assert len(results) == 1
    assert results[0][1].success is True
    assert captured["tool_approver"] is approver
    assert isinstance(captured["project_dir"], Path)
    assert captured["project_dir"].parent.parent == config.project_dir / "worktrees"


@pytest.mark.asyncio
async def test_worktree_pool_applies_worker_patch_back_to_main_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    _init_git_repo(workspace)

    config = ForgeGodConfig()
    config.project_dir = workspace / ".forgegod"
    config.project_dir.mkdir()

    story = Story(
        id="T2",
        title="Create notes",
        description="Write notes.txt from an isolated worker.",
        acceptance_criteria=["notes.txt exists"],
    )

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            self.workspace_root = kwargs["config"].project_dir.parent

        async def run(self, _prompt: str) -> AgentResult:
            (self.workspace_root / "notes.txt").write_text(
                "hello from worktree\n",
                encoding="utf-8",
            )
            return AgentResult(success=True, files_modified=["notes.txt"])

    monkeypatch.setattr("forgegod.worktree.Agent", FakeAgent)

    pool = WorktreePool(config=config, max_workers=1)
    results = await pool.run_parallel([story])

    assert len(results) == 1
    assert results[0][1].success is True
    assert not (workspace / "notes.txt").exists()

    diff = await pool.diff_for_story("T2")
    assert "hello from worktree" in diff

    apply_result = await pool.apply_patch_for_story("T2")
    assert apply_result == "applied"
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "hello from worktree\n"

    worker = pool.get_worker("T2")
    assert worker is not None
    worker_path = Path(worker.worktree_path)
    await pool.cleanup()
    assert not worker_path.exists()


@pytest.mark.asyncio
async def test_worktree_pool_requires_at_least_one_commit(tmp_path):
    workspace = tmp_path / "repo-no-head"
    workspace.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )

    config = ForgeGodConfig()
    config.project_dir = workspace / ".forgegod"
    config.project_dir.mkdir()

    pool = WorktreePool(config=config, max_workers=1)
    readiness_error = await pool.ensure_parallel_ready()

    assert readiness_error is not None
    assert "at least one git commit" in readiness_error
