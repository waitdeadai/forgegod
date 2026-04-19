from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forgegod.cli import _load_review_code
from forgegod.config import ForgeGodConfig
from forgegod.loop import RalphLoop
from forgegod.models import PRD, AgentResult, ModelUsage, Story, StoryStatus
from forgegod.review_artifacts import collect_review_artifact
from forgegod.reviewer import Reviewer


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "ForgeGod Tests")

    (repo / "target.txt").write_text("before target\n", encoding="utf-8")
    (repo / "other.txt").write_text("before other\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


@pytest.mark.asyncio
async def test_collect_review_artifact_scopes_to_changed_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "target.txt").write_text("after target\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("after other\n", encoding="utf-8")

    review_text = await collect_review_artifact(
        tmp_path,
        files_changed=["target.txt"],
        fallback_text="fallback",
    )

    assert "target.txt" in review_text
    assert "other.txt" not in review_text


@pytest.mark.asyncio
async def test_collect_review_artifact_falls_back_to_untracked_file_snapshot(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("hello from a new file\n", encoding="utf-8")

    review_text = await collect_review_artifact(
        tmp_path,
        files_changed=["new.txt"],
        fallback_text="fallback",
    )

    assert "### FILE: new.txt" in review_text
    assert "hello from a new file" in review_text


@pytest.mark.asyncio
async def test_collect_review_artifact_normalizes_windows_style_paths(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file_path = src_dir / "app.py"
    file_path.write_text("print('changed')\n", encoding="utf-8")

    review_text = await collect_review_artifact(
        tmp_path,
        files_changed=["src\\app.py"],
        fallback_text="fallback",
    )

    assert "src/app.py" in review_text or "### FILE: src/app.py" in review_text


@pytest.mark.asyncio
async def test_cli_load_review_code_uses_scoped_artifact(monkeypatch, tmp_path: Path) -> None:
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    result = AgentResult(
        success=True,
        output="model output",
        files_modified=["src/app.py"],
        total_usage=ModelUsage(),
    )
    captured: dict[str, object] = {}

    async def fake_collect(workspace_root, **kwargs):
        captured["workspace_root"] = workspace_root
        captured.update(kwargs)
        return "scoped diff"

    monkeypatch.setattr("forgegod.cli.collect_review_artifact", fake_collect)

    review_text = await _load_review_code(config, result)

    assert review_text == "scoped diff"
    assert captured["files_changed"] == ["src/app.py"]
    assert captured["fallback_text"] == "model output"


class _FakeRouter:
    async def close(self):
        return None


@pytest.mark.asyncio
async def test_loop_collect_review_code_uses_scoped_artifact(monkeypatch, tmp_path: Path) -> None:
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.taste.enabled = False
    config.effort.enabled = False

    loop = RalphLoop(config=config, prd=PRD(project="God IDE"), router=_FakeRouter())
    result = AgentResult(
        success=True,
        output="loop output",
        files_modified=["src/feature.py"],
        total_usage=ModelUsage(),
    )
    captured: dict[str, object] = {}

    async def fake_collect(workspace_root, **kwargs):
        captured["workspace_root"] = workspace_root
        captured.update(kwargs)
        return "loop scoped diff"

    monkeypatch.setattr("forgegod.loop.collect_review_artifact", fake_collect)

    review_text = await loop._collect_review_code(result)

    assert review_text == "loop scoped diff"
    assert captured["files_changed"] == ["src/feature.py"]
    assert captured["fallback_text"] == "loop output"


@pytest.mark.asyncio
async def test_loop_does_not_treat_preexisting_dirty_diff_as_story_output(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "other.txt").write_text("dirty before story\n", encoding="utf-8")

    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    config.review.enabled = False
    config.taste.enabled = False
    config.effort.enabled = False

    story = Story(id="A1", title="Story should do real work")
    loop = RalphLoop(
        config=config,
        prd=PRD(project="God IDE", stories=[story]),
        router=_FakeRouter(),
    )
    loop._story_dirty_baselines[story.id] = {"other.txt"}

    result = AgentResult(
        success=True,
        output="no actual changes",
        files_modified=[],
        total_usage=ModelUsage(),
    )

    await loop._finalize_story_result(story, result)

    assert story.status == StoryStatus.TODO
    assert any("Agent produced no output" in item for item in story.error_log)


@pytest.mark.asyncio
async def test_reviewer_review_path_uses_scoped_artifact_for_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (src_dir / "other.py").write_text("print('other')\n", encoding="utf-8")

    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    reviewer = Reviewer(config=config, router=_FakeRouter())

    captured: dict[str, object] = {}

    async def fake_collect(workspace_root, **kwargs):
        captured["workspace_root"] = workspace_root
        captured.update(kwargs)
        return "directory scoped diff"

    async def fake_review(*, task: str, code: str, **_kwargs):
        captured["task"] = task
        captured["code"] = code
        return "review result"

    monkeypatch.setattr("forgegod.reviewer.collect_review_artifact", fake_collect)
    monkeypatch.setattr(reviewer, "review", fake_review)

    result = await reviewer.review_path("src")

    assert result == "review result"
    assert captured["workspace_root"] == tmp_path
    assert set(captured["files_changed"]) == {"src/app.py", "src/other.py"}
    assert captured["code"] == "directory scoped diff"
    assert captured["task"] == "Review recent changes in src"
