"""ForgeGod built-in tools — filesystem, shell, git, MCP."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from forgegod.models import ToolDef

# Global tool registry
_TOOLS: dict[str, tuple[ToolDef, Callable[..., Coroutine[Any, Any, str]]]] = {}

__all__ = ["register_tool", "get_tool_defs", "execute_tool", "load_all_tools"]


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
