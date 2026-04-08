"""ForgeGod built-in tools — filesystem, shell, git, MCP."""

from __future__ import annotations

import inspect
import re
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Callable, Coroutine

from forgegod.models import ToolDef

# Global tool registry
_TOOLS: dict[str, tuple[ToolDef, Callable[..., Coroutine[Any, Any, str]]]] = {}
_TOOL_CONFIG: ContextVar[Any | None] = ContextVar("forgegod_tool_config", default=None)
_TOOL_APPROVER: ContextVar[Any | None] = ContextVar("forgegod_tool_approver", default=None)

__all__ = [
    "register_tool",
    "get_tool_defs",
    "execute_tool",
    "load_all_tools",
    "get_tool_config",
    "get_workspace_root",
    "get_project_dir",
    "resolve_tool_path",
    "blocked_path_reason",
    "tool_permission_error",
    "permission_policy_snapshot",
    "set_tool_approver",
    "reset_tool_approver",
    "set_tool_context",
    "reset_tool_context",
]

READ_ONLY_TOOLS = {
    "read_file", "glob", "grep", "repo_map", "git_status",
    "git_diff", "git_log", "mcp_list", "list_skills", "load_skill",
    "web_search", "web_fetch", "pypi_info", "github_search",
}

WORKSPACE_WRITE_BLOCKED_TOOLS = {
    "git_commit", "git_worktree_create", "git_worktree_remove",
    "mcp_connect", "mcp_call", "mcp_auth",
}

READ_ONLY_BASH_PREFIXES = (
    "python --version",
    "python -m pytest",
    "pytest",
    "ruff",
    "git status",
    "git diff",
    "git log",
    "ls",
    "dir",
    "cat",
    "type",
    "find",
    "findstr",
    "rg",
    "npm test",
    "npm run test",
    "npm run lint",
    "npm run build",
    "pnpm test",
    "pnpm lint",
    "pnpm build",
    "yarn test",
    "yarn lint",
    "yarn build",
    "bun test",
    "bun run lint",
    "bun run build",
    "cargo test",
    "go test",
    "deno test",
)


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    handler: Callable[..., Coroutine[Any, Any, str]],
):
    """Register a tool in the global registry."""
    _TOOLS[name] = (
        ToolDef(name=name, description=description, parameters=parameters),
        handler,
    )


def get_tool_config() -> Any | None:
    """Get the current runtime config for tool execution."""
    return _TOOL_CONFIG.get()


def set_tool_context(config: Any) -> Token:
    """Set runtime config for tool execution in the current async context."""
    return _TOOL_CONFIG.set(config)


def reset_tool_context(token: Token) -> None:
    """Reset runtime config for tool execution in the current async context."""
    _TOOL_CONFIG.reset(token)


def set_tool_approver(approver: Any) -> Token:
    """Set an approval callback for permission overrides in the current context."""
    return _TOOL_APPROVER.set(approver)


def reset_tool_approver(token: Token) -> None:
    """Reset the approval callback in the current async context."""
    _TOOL_APPROVER.reset(token)


def get_project_dir() -> Path:
    """Get the active .forgegod directory for tool execution."""
    config = get_tool_config()
    project_dir = getattr(config, "project_dir", None)
    if project_dir:
        return Path(project_dir)
    return Path.cwd() / ".forgegod"


def get_workspace_root() -> Path:
    """Get the active workspace root for tool execution."""
    project_dir = get_project_dir()
    return project_dir.parent if project_dir.name == ".forgegod" else Path.cwd()


def resolve_tool_path(path: str, *, must_exist: bool = False) -> tuple[Path | None, str | None]:
    """Resolve a tool path, enforcing workspace boundaries when config is present."""
    config = get_tool_config()
    raw = Path(path)
    if config:
        root = get_workspace_root().resolve()
        candidate = raw if raw.is_absolute() else root / raw
        try:
            resolved = candidate.resolve(strict=must_exist)
        except FileNotFoundError:
            return None, f"Error: Path not found: {path}"
        except OSError as e:
            return None, f"Error: Invalid path '{path}': {e}"

        try:
            resolved.relative_to(root)
        except ValueError:
            return None, f"Error: Path escapes workspace root: {path}"
        return resolved, None

    if must_exist and not raw.exists():
        return None, f"Error: Path not found: {path}"
    return raw, None


def blocked_path_reason(path: Path) -> str | None:
    """Return the blocked-path rule that matches a path, if any."""
    config = get_tool_config()
    if not config:
        return None

    security = getattr(config, "security", None)
    blocked_paths = getattr(security, "blocked_paths", []) if security else []
    root = get_workspace_root().resolve()
    target = path.resolve(strict=False)

    for raw in blocked_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = root / candidate
        blocked = candidate.resolve(strict=False)
        if target == blocked or blocked in target.parents:
            return raw
    return None


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().lower())


def _read_only_bash_allowed(command: str) -> bool:
    normalized = _normalize_command(command)
    for prefix in READ_ONLY_BASH_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + " "):
            return True
    return False


def tool_permission_error(name: str, arguments: dict[str, Any]) -> str | None:
    """Return a permission error for a tool call, or None if allowed."""
    config = get_tool_config()
    if not config:
        return None

    security = getattr(config, "security", None)
    if not security:
        return None

    mode = getattr(security, "permission_mode", "workspace-write")
    allowed_tools = {
        str(tool).strip()
        for tool in getattr(security, "allowed_tools", []) or []
        if str(tool).strip()
    }

    if allowed_tools and name not in allowed_tools:
        return (
            f"Tool '{name}' is not in the allowed tool list for this run. "
            f"Allowed: {', '.join(sorted(allowed_tools))}"
        )

    if mode == "danger-full-access":
        return None

    if mode == "read-only":
        if name in READ_ONLY_TOOLS:
            return None
        if name == "bash" and _read_only_bash_allowed(str(arguments.get("command", ""))):
            return None
        return f"Tool '{name}' is blocked in read-only permission mode"

    if mode == "workspace-write":
        if name in WORKSPACE_WRITE_BLOCKED_TOOLS:
            return f"Tool '{name}' is blocked in workspace-write permission mode"
        return None

    return f"Unknown permission mode: {mode}"


async def _tool_permission_approved(
    name: str,
    arguments: dict[str, Any],
    permission_error: str,
) -> bool:
    config = get_tool_config()
    security = getattr(config, "security", None) if config else None
    approval_mode = getattr(security, "approval_mode", "deny") if security else "deny"

    if approval_mode == "approve":
        return True
    if approval_mode != "prompt":
        return False

    approver = _TOOL_APPROVER.get()
    if approver is None:
        return False

    decision = approver(name, arguments, permission_error)
    if inspect.isawaitable(decision):
        decision = await decision
    return bool(decision)


def permission_policy_snapshot(config: Any) -> dict[str, Any]:
    """Describe the effective tool-permission surface for the current config."""
    security = getattr(config, "security", None)
    if security:
        mode = getattr(security, "permission_mode", "workspace-write")
    else:
        mode = "workspace-write"
    allowed_tools = {
        str(tool).strip()
        for tool in getattr(security, "allowed_tools", []) or []
        if str(tool).strip()
    }
    registered_tools = set(_TOOLS.keys())

    if allowed_tools:
        effective_allowed_tools = sorted(registered_tools & allowed_tools)
        blocked_tools = sorted(registered_tools - allowed_tools)
    elif mode == "read-only":
        effective_allowed_tools = sorted(registered_tools & READ_ONLY_TOOLS)
        blocked_tools = sorted(
            tool for tool in registered_tools
            if tool not in READ_ONLY_TOOLS and tool != "bash"
        )
    elif mode == "workspace-write":
        effective_allowed_tools = sorted(
            tool for tool in registered_tools if tool not in WORKSPACE_WRITE_BLOCKED_TOOLS
        )
        blocked_tools = sorted(registered_tools & WORKSPACE_WRITE_BLOCKED_TOOLS)
    elif mode == "danger-full-access":
        effective_allowed_tools = sorted(registered_tools)
        blocked_tools = []
    else:
        effective_allowed_tools = sorted(registered_tools)
        blocked_tools = []

    return {
        "mode": mode,
        "approval_mode": getattr(security, "approval_mode", "deny") if security else "deny",
        "registered_tools": sorted(registered_tools),
        "allowed_tools": sorted(allowed_tools),
        "effective_allowed_tools": effective_allowed_tools,
        "blocked_tools": blocked_tools,
        "read_only_bash_prefixes": list(READ_ONLY_BASH_PREFIXES) if mode == "read-only" else [],
    }


def get_tool_defs() -> list[dict]:
    """Get all tool definitions in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": td.name,
                "description": td.description,
                "parameters": td.parameters,
            },
        }
        for td, _ in _TOOLS.values()
    ]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a registered tool by name."""
    if name not in _TOOLS:
        return f"Error: Unknown tool '{name}'"
    permission_error = tool_permission_error(name, arguments)
    if permission_error and not await _tool_permission_approved(name, arguments, permission_error):
        return f"Error: {permission_error}"
    _, handler = _TOOLS[name]
    try:
        return await handler(**arguments)
    except Exception as e:
        return f"Error executing {name}: {e}"


def load_all_tools():
    """Load all built-in tools into the registry."""
    from forgegod.tools import filesystem, git, mcp, shell, skills  # noqa: F401
    from forgegod.tools.web import register_web_tools

    register_web_tools()
