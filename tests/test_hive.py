from __future__ import annotations

import subprocess

import pytest
import toml

from forgegod.config import ForgeGodConfig
from forgegod.hive import HiveCoordinator, HiveWorker
from forgegod.models import PRD, HiveWorkerResult, Story, StoryStatus


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_hive_applies_worktree_patch(tmp_path):
    if not _git_available():
        pytest.skip("git is required for hive worktree tests")

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    config = ForgeGodConfig()
    config.project_dir = repo / ".forgegod"
    config.project_dir.mkdir(parents=True, exist_ok=True)
    (config.project_dir / "config.toml").write_text(
        toml.dumps(config.model_dump(mode="json", exclude={"global_dir", "project_dir"})),
        encoding="utf-8",
    )

    prd_path = config.project_dir / "prd.json"
    prd = PRD(
        project="Hive Test",
        description="Test hive patch apply",
        stories=[
            Story(
                id="T001",
                title="Create app file",
                description="Write src/app.py",
                status=StoryStatus.TODO,
                acceptance_criteria=["File exists"],
            )
        ],
    )
    prd_path.write_text(prd.model_dump_json(indent=2), encoding="utf-8")

    async def fake_runner(worker: HiveWorker) -> HiveWorkerResult:
        target = worker.worktree_path / "src" / "app.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("print('hive')\n", encoding="utf-8")
        return HiveWorkerResult(
            story_id=worker.story_id,
            success=True,
            exit_code=0,
            files_modified=["src/app.py"],
        )

    coordinator = HiveCoordinator(config=config, worker_runner=fake_runner)
    await coordinator.run(prd_path, max_iterations=1, max_workers=1, dry_run=False)

    assert (repo / "src" / "app.py").exists()
    assert "print('hive')" in (repo / "src" / "app.py").read_text(encoding="utf-8")

    worktree_base = config.project_dir / "worktrees"
    assert not any(worktree_base.glob("*"))

    branches = subprocess.run(
        ["git", "branch", "--list", "forgegod/hive/*"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert branches.stdout.strip() == ""


@pytest.mark.asyncio
async def test_hive_rejects_prompt_approval_mode(tmp_path):
    if not _git_available():
        pytest.skip("git is required for hive worktree tests")

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    config = ForgeGodConfig()
    config.project_dir = repo / ".forgegod"
    config.project_dir.mkdir(parents=True, exist_ok=True)
    config.security.approval_mode = "prompt"

    prd_path = config.project_dir / "prd.json"
    prd = PRD(
        project="Hive Prompt Test",
        stories=[Story(id="T001", title="Blocked by prompt mode")],
    )
    prd_path.write_text(prd.model_dump_json(indent=2), encoding="utf-8")

    coordinator = HiveCoordinator(config=config, worker_runner=None)
    with pytest.raises(RuntimeError, match="does not support prompt approvals"):
        await coordinator.run(prd_path, max_iterations=1, max_workers=1, dry_run=True)
