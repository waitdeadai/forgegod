"""ForgeGod git tools — status, diff, commit, worktree."""

from __future__ import annotations

import asyncio

from forgegod.tools import register_tool


async def _run_git(*args: str) -> str:
    """Run a git command and return output."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        return f"Error (exit {proc.returncode}): {err or out}"
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

    worktree_id = uuid.uuid4().hex[:8]
    path = f".forgegod/worktrees/{worktree_id}"

    # Create branch if it doesn't exist
    await _run_git("branch", branch, "HEAD")
    result = await _run_git("worktree", "add", path, branch)
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
