"""ForgeGod CLI UX helpers: branding, logging, and human-readable narration."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

FORGE_THEME = Theme(
    {
        "forge.primary": "bold cyan",
        "forge.secondary": "yellow",
        "forge.highlight": "bold white",
        "forge.muted": "dim white",
        "forge.success": "green",
        "forge.warn": "yellow",
        "forge.error": "bold red",
    }
)

console = Console(theme=FORGE_THEME)

NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "openai",
    "anthropic",
    "urllib3",
    "asyncio",
)


def safe_console_text(text: str, *, active_console: Console | None = None) -> str:
    """Best-effort console-safe text for legacy Windows encodings."""
    if not isinstance(text, str):
        return text
    current_console = active_console or console
    encoding = getattr(getattr(current_console, "file", None), "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def build_banner_text(version: str) -> Text:
    """Build the ForgeGod mascot banner with brand colors."""
    text = Text()
    text.append("                 .\n", style="forge.secondary")
    text.append("            .-==========-.\n", style="forge.secondary")
    text.append("         .-'   .-====-.   '-.\n", style="forge.secondary")
    text.append("              \\________/\n", style="forge.secondary")
    text.append("                 /\\\n", style="forge.primary")
    text.append("                / /\\ \\\n", style="forge.primary")
    text.append("               / /  \\ \\\n", style="forge.primary")
    text.append("              / /(_", style="forge.primary")
    text.append("1", style="forge.highlight")
    text.append("_)\\ \\\n", style="forge.primary")
    text.append("             /_/_______\\_\\\n", style="forge.primary")
    text.append("\n")
    text.append("   F O R G E G O D", style="forge.primary")
    text.append(f"  v{version}\n", style="forge.muted")
    text.append("   Autonomous coding engine\n", style="forge.muted")
    return text


def build_mini_banner_text(version: str) -> Text:
    """Build the compact ForgeGod mascot mark for terse CLI surfaces."""
    text = Text()
    text.append("( ) ", style="forge.secondary")
    text.append("/", style="forge.primary")
    text.append("1", style="forge.highlight")
    text.append("\\ ", style="forge.primary")
    text.append("ForgeGod", style="forge.primary")
    text.append(f" v{version}", style="forge.muted")
    return text


def print_brand_panel(title: str, body: str, *, border_style: str = "forge.primary") -> None:
    """Print a branded panel."""
    console.print(
        Panel(
            safe_console_text(body),
            title=f"[forge.highlight]{title}[/forge.highlight]",
            border_style=border_style,
        )
    )


def configure_cli_logging(
    *,
    verbose: bool,
    log_file: Path | None = None,
    stream: bool,
) -> None:
    """Configure quiet console logging and richer file logging for ForgeGod CLI."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    root.setLevel(logging.WARNING)

    handlers: list[logging.Handler] = []
    if stream:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
        handlers.append(file_handler)

    for handler in handlers:
        root.addHandler(handler)

    forgegod_logger = logging.getLogger("forgegod")
    forgegod_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    forgegod_logger.propagate = True

    for logger_name in NOISY_LOGGERS:
        noisy = logging.getLogger(logger_name)
        noisy.setLevel(logging.WARNING)
        noisy.propagate = True


class RunNarrator:
    """Human-readable narration layer for forgegod run."""

    def __init__(self) -> None:
        self._last_activity = ""

    async def __call__(self, event: str, **payload: Any) -> None:
        if event == "task_started":
            print_brand_panel(
                "ForgeGod Session",
                (
                    "I'm taking in the task, inspecting the repo, "
                    "and I'll report progress in plain language."
                ),
            )
            return

        if event == "tool_batch_started":
            activity = self._describe_tool_batch(payload.get("tools", []))
            if activity and activity != self._last_activity:
                console.print(
                    "[forge.primary]ForgeGod[/forge.primary] "
                    f"{safe_console_text(activity)}"
                )
                self._last_activity = activity
            return

        if event == "completion_blocked":
            blockers = payload.get("blockers", [])
            if blockers:
                print_brand_panel(
                    "Not Done Yet",
                    "I still need to close a few credibility gaps:\n"
                    + "\n".join(f"- {safe_console_text(item)}" for item in blockers[:5]),
                    border_style="forge.warn",
                )
            return

        if event == "task_failed":
            error = payload.get("error") or payload.get("output") or "Unknown failure"
            print_brand_panel("Run Failed", error[:800], border_style="forge.error")
            return

        if event == "task_completed":
            files = payload.get("files_modified", [])
            if files:
                preview = ", ".join(str(item) for item in files[:3])
                console.print(
                    "[forge.success]ForgeGod[/forge.success] "
                    f"finished the patch and gathered proof for {safe_console_text(preview)}."
                )
            else:
                console.print(
                    "[forge.success]ForgeGod[/forge.success] "
                    "finished the task and has a final answer ready."
                )

    def _describe_tool_batch(self, tools: list[dict[str, Any]]) -> str:
        if not tools:
            return ""

        names = [str(item.get("name", "")) for item in tools]
        if all(name in {"repo_map", "glob", "grep", "read_file"} for name in names):
            return "Inspecting the repository and locating the right files."

        if any(name in {"write_file", "edit_file"} for name in names):
            files = [
                str(item.get("arguments", {}).get("path", "")).strip()
                for item in tools
                if item.get("name") in {"write_file", "edit_file"}
            ]
            files = [path for path in files if path]
            if files:
                preview = ", ".join(files[:3])
                return f"Applying changes to {preview}."
            return "Applying the next patch."

        if any(name == "bash" for name in names):
            for item in tools:
                if item.get("name") == "bash":
                    command = str(item.get("arguments", {}).get("command", "")).strip()
                    if command:
                        return f"Running checks: {command}"
            return "Running shell checks."

        if "git_diff" in names:
            return "Reviewing the patch before calling it done."

        if any(name.startswith("mcp_") for name in names):
            return "Using external tools for extra context."

        return ""


class LoopNarrator:
    """Human-readable narration layer for forgegod loop."""

    def __init__(self) -> None:
        self._run_narrator = RunNarrator()

    async def __call__(self, event: str, **payload: Any) -> None:
        if event == "loop_started":
            print_brand_panel(
                "Ralph Loop",
                (
                    "ForgeGod is working through the PRD story by story. "
                    "I'll announce what it's doing instead of dumping transport logs."
                ),
            )
            return

        if event == "story_started":
            story_id = payload.get("story_id", "")
            title = payload.get("story_title", "")
            console.print(
                f"[forge.secondary]{story_id}[/forge.secondary] "
                f"[forge.highlight]{safe_console_text(title)}[/forge.highlight]"
            )
            return

        if event == "story_done":
            console.print(
                f"[forge.success]Done:[/forge.success] "
                f"{payload.get('story_id', '')} {safe_console_text(payload.get('story_title', ''))}"
            )
            return

        if event == "story_retry":
            reason = safe_console_text(payload.get("reason", ""))[:200]
            console.print(
                f"[forge.warn]Retrying:[/forge.warn] "
                f"{payload.get('story_id', '')} {reason}"
            )
            return

        if event == "story_blocked":
            reason = safe_console_text(payload.get("reason", ""))[:200]
            console.print(
                f"[forge.error]Blocked:[/forge.error] "
                f"{payload.get('story_id', '')} {reason}"
            )
            return

        await self._run_narrator(event, **payload)


async def emit_cli_event(callback: Any, event: str, **payload: Any) -> None:
    """Deliver a UX event to a sync or async callback if present."""
    if callback is None:
        return
    result = callback(event, **payload)
    if inspect.isawaitable(result):
        await result
