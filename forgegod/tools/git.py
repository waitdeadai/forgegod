"""ForgeGod git tools — status, diff, commit, worktree."""

from __future__ import annotations

import asyncio
from pathlib import Path

from forgegod.sandbox import SandboxUnavailableError, run_in_real_sandbox
from forgegod.tools import get_tool_config, get_workspace_root, register_tool


async def _run_git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return output."""
    active_cwd = cwd
    config = get_tool_config()
    if active_cwd is None and config:
        active_cwd = get_workspace_root()

    security = getattr(config, "security", None) if config else None
    sandbox_mode = getattr(security, "sandbox_mode", "standard")
    if sandbox_mode == "strict" and active_cwd and config:
        try:
            result = await run_in_real_sandbox(
                argv=["git", *args],
                workspace_root=get_workspace_root().resolve(),
                sandbox_root=config.project_dir / "sandbox",
                timeout=120,
                security=security,
            )
        except SandboxUnavailableError as e:
            return f"Error: {e}"

        out = result.stdout.strip()
        err = result.stderr.strip()
        returncode = result.returncode
    else:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(active_cwd) if active_cwd else None,
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        returncode = proc.returncode

    if returncode != 0:
        return f"Error (exit {returncode}): {err or out}"
    return out or "(no output)"


async def git_status() -> str:
    """Get git status of current repo."""
    return await _run_git("status", "--short")


async def git_diff(ref: str = "") -> str:
    """Get git diff — staged + unstaged, or against a ref."""
    if ref:
        result = await _run_git("diff", ref)
    else:
        staged = await _run_git("diff", "--cached")
        unstaged = await _run_git("diff")
        parts = []
        if staged and not staged.startswith("Error"):
            parts.append(f"[staged]\n{staged}")
        if unstaged and not unstaged.startswith("Error"):
            parts.append(f"[unstaged]\n{unstaged}")
        result = "\n\n".join(parts) if parts else "(no changes)"

    # Truncate large diffs
    if len(result) > 15_000:
        result = result[:7_000] + "\n\n[... truncated ...]\n\n" + result[-3_000:]
    return result


async def git_commit(message: str, files: str = ".") -> str:
    """Stage files and create a git commit."""
    # Stage
    for f in files.split(","):
        f = f.strip()
        if f:
            await _run_git("add", f)

    # Commit
    return await _run_git("commit", "-m", message)


async def git_log(count: int = 10) -> str:
    """Get recent git log."""
    return await _run_git("log", "--oneline", f"-{count}")


async def git_worktree_create(branch: str) -> str:
    """Create a git worktree for parallel work."""
    import uuid

    head_check = await _run_git("rev-parse", "--verify", "HEAD")
    if head_check.startswith("Error"):
        return (
            "Error: Parallel worktrees require at least one git commit before "
            "ForgeGod can create an isolated worktree."
        )

    worktree_id = uuid.uuid4().hex[:8]
    path = f".forgegod/worktrees/{worktree_id}"

    result = await _run_git("worktree", "add", "-b", branch, path)
    if result.startswith("Error"):
        return result
    return f"Worktree created at {path} on branch {branch}"


async def git_worktree_remove(path: str) -> str:
    """Remove a git worktree."""
    return await _run_git("worktree", "remove", "--force", path)


# ── Register tools ──

register_tool(
    name="git_status",
    description="Show git status (short format).",
    parameters={"type": "object", "properties": {}},
    handler=git_status,
)

register_tool(
    name="git_diff",
    description="Show git diff. Optionally compare against a ref (branch, commit).",
    parameters={
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Git ref to diff against", "default": ""},
        },
    },
    handler=git_diff,
)

register_tool(
    name="git_commit",
    description="Stage files and create a git commit.",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message"},
            "files": {
                "type": "string",
                "description": "Comma-separated file paths to stage",
                "default": ".",
            },
        },
        "required": ["message"],
    },
    handler=git_commit,
)

register_tool(
    name="git_worktree_create",
    description="Create a git worktree on a new branch for parallel work.",
    parameters={
        "type": "object",
        "properties": {
            "branch": {"type": "string", "description": "Branch name for the worktree"},
        },
        "required": ["branch"],
    },
    handler=git_worktree_create,
)

register_tool(
    name="git_log",
    description="Get recent git log.",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "Number of commits to show", "default": 10},
        },
        "required": [],
    },
    handler=git_log,
)

register_tool(
    name="git_worktree_remove",
    description="Remove a git worktree.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the worktree to remove"},
        },
        "required": ["path"],
    },
    handler=git_worktree_remove,
)
