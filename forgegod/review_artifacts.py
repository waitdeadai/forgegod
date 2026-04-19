"""Helpers for collecting scoped review artifacts.

The reviewer should inspect the changes produced by the current run/story,
not every unrelated dirty file already present in the workspace.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Sequence


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip()


async def _run_git(
    workspace_root: Path,
    *args: str,
) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace_root),
    )
    stdout, _stderr = await proc.communicate()
    return stdout.decode("utf-8", errors="replace")


def _render_file_snapshots(
    workspace_root: Path,
    files_changed: Sequence[str],
    *,
    max_chars: int,
) -> str:
    sections: list[str] = []
    remaining = max_chars
    for rel_path in files_changed:
        if remaining <= 0:
            break
        path = workspace_root / rel_path
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        section = f"### FILE: {rel_path}\n{content}\n"
        if len(section) > remaining:
            section = section[:remaining]
        sections.append(section)
        remaining -= len(section)
    return "\n".join(sections)


async def collect_review_artifact(
    workspace_root: Path,
    *,
    files_changed: Sequence[str] | None = None,
    fallback_text: str = "",
    max_chars: int = 6000,
) -> str:
    """Collect reviewable text scoped to the current run/story.

    Preference order:
    1. Scoped git diff for files_changed
    2. Current file snapshots for untracked/new files in files_changed
    3. Global diff / last commit patch when no scoped file list exists
    4. Fallback text from the model output
    """

    review_text = fallback_text[:max_chars]
    scoped_files = [
        _normalize_repo_path(path)
        for path in (files_changed or [])
        if _normalize_repo_path(path)
    ]

    try:
        if scoped_files:
            diff_text = await _run_git(workspace_root, "diff", "HEAD", "--", *scoped_files)
            if diff_text.strip():
                return diff_text[:max_chars]

            snapshot_text = _render_file_snapshots(
                workspace_root,
                scoped_files,
                max_chars=max_chars,
            )
            if snapshot_text.strip():
                return snapshot_text[:max_chars]

        diff_text = await _run_git(workspace_root, "diff", "HEAD")
        if diff_text.strip():
            return diff_text[:max_chars]

        last_commit = await _run_git(workspace_root, "log", "-1", "-p", "--stat")
        if last_commit.strip():
            return last_commit[:max_chars]
    except Exception:
        pass

    return review_text
