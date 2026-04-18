"""Shared worktree path helpers.

Git worktrees must live outside the main repository working tree on Linux.
ForgeGod keeps a stable hidden sibling directory per repo to make the path
predictable while avoiding nested worktree failures.
"""

from __future__ import annotations

from pathlib import Path


def resolve_worktree_base(project_dir: Path) -> Path:
    """Return the external base directory for isolated git worktrees."""
    repo_root = project_dir.parent.resolve()
    return repo_root.parent / ".forgegod-worktrees" / repo_root.name


def ensure_worktree_base(project_dir: Path) -> Path:
    """Create and return the external base directory for isolated worktrees."""
    base = resolve_worktree_base(project_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base
