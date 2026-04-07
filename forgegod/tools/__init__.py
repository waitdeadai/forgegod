"""ForgeGod built-in tools — filesystem, shell, git, MCP."""

from __future__ import annotations

from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Callable, Coroutine

from forgegod.models import ToolDef

# Global tool registry
_TOOLS: dict[str, tuple[ToolDef, Callable[..., Coroutine[Any, Any, str]]]] = {}
_TOOL_CONFIG: ContextVar[Any | None] = ContextVar("forgegod_tool_config", default=None)

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
    "set_tool_context",
    "reset_tool_context",
]


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
