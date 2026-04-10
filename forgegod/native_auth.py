"""Native auth helpers for provider-owned CLIs and subscription surfaces."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def find_command(command: str) -> str | None:
    """Return the resolved executable path for a command if present."""
    return shutil.which(command)


def codex_automation_status() -> tuple[bool, str]:
    """Return whether Codex CLI is a reliable automation backend in this environment."""
    if sys.platform != "win32":
        return True, "Codex automation supported"

    release = platform.release().lower()
    if os.environ.get("WSL_DISTRO_NAME") or "microsoft" in release:
        return True, "Codex automation supported in WSL"

    if os.environ.get("FORGEGOD_ALLOW_EXPERIMENTAL_CODEX_WINDOWS") == "1":
        return True, "Codex automation forced on native Windows (experimental)"

    return (
        False,
        "Codex CLI automation is experimental on native Windows. "
        "OpenAI recommends running Codex in WSL for the best Windows experience. "
        "Use WSL or set FORGEGOD_ALLOW_EXPERIMENTAL_CODEX_WINDOWS=1 to force it.",
    )


async def run_command(
    argv: list[str],
    cwd: Path | None = None,
    timeout: float = 30.0,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess and return (code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd) if cwd else None,
        stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdin_bytes = (
        stdin_text.encode("utf-8", errors="replace")
        if stdin_text is not None
        else None
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin_bytes),
            timeout=timeout,
        )
    except asyncio.TimeoutError as e:
        proc.kill()
        try:
            await proc.communicate()
        except Exception:
            pass
        preview = " ".join(argv[:6])
        raise RuntimeError(
            f"Command timed out after {timeout:.0f}s: {preview}"
        ) from e
    return (
        proc.returncode,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


async def codex_login_status(command: str = "codex") -> tuple[bool, str]:
    """Check whether Codex CLI is installed and logged in."""
    resolved = find_command(command)
    if not resolved:
        return False, "Codex CLI not found"

    try:
        code, stdout, stderr = await run_command(
            [resolved, "login", "status"],
            timeout=20.0,
        )
    except RuntimeError as e:
        return False, str(e)
    text = (stdout or stderr).strip()
    return code == 0 and "Logged in" in text, text


def codex_login_status_sync(command: str = "codex") -> tuple[bool, str]:
    """Synchronous version of Codex login-status checks."""
    resolved = find_command(command)
    if not resolved:
        return False, "Codex CLI not found"

    proc = subprocess.run(
        [resolved, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20.0,
        check=False,
    )
    text = (proc.stdout or proc.stderr).strip()
    return proc.returncode == 0 and "Logged in" in text, text


def render_messages_as_prompt(messages: list[dict]) -> str:
    """Flatten ForgeGod chat messages into a plain-text prompt for Codex CLI."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user").upper()
        content = msg.get("content", "")
        if isinstance(content, list):
            rendered = []
            for item in content:
                if isinstance(item, dict):
                    rendered.append(str(item.get("text", item)))
                else:
                    rendered.append(str(item))
            content = "\n".join(rendered)
        parts.append(f"[{role}]\n{content}".strip())
    return "\n\n".join(parts).strip()


async def codex_exec(
    prompt: str,
    cwd: Path,
    *,
    model: str = "",
    command: str = "codex",
    timeout: float = 180.0,
    sandbox: str = "read-only",
    ephemeral: bool = True,
    json_mode: bool = False,
) -> tuple[str, dict]:
    """Run Codex CLI non-interactively and return (text, usage)."""
    resolved = find_command(command)
    if not resolved:
        raise RuntimeError(
            "error: Codex CLI not found.\n"
            "  Fix: install Codex CLI or make `codex` available on PATH.\n"
            "  Then run: codex login"
        )

    argv = [
        resolved,
        "exec",
        "--skip-git-repo-check",
        "--json",
        "-C",
        str(cwd),
        "-s",
        sandbox,
    ]
    if ephemeral:
        argv.append("--ephemeral")
    if model:
        argv.extend(["-m", model])

    argv.append("-")
    code, stdout, stderr = await run_command(
        argv,
        cwd=cwd,
        timeout=timeout,
        stdin_text=prompt,
    )

    if code != 0 and not stdout.strip():
        raise RuntimeError(
            "error: Codex CLI execution failed.\n"
            f"  Exit code: {code}\n"
            f"  Details: {(stderr or 'no stderr').strip()}"
        )

    text = ""
    usage: dict[str, int] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                text = item.get("text", text)
        elif event_type == "turn.completed":
            usage = event.get("usage") or usage

    if not text and stdout.strip():
        text = stdout.strip().splitlines()[-1]

    if code != 0:
        detail = (stderr or stdout).strip()
        raise RuntimeError(
            "error: Codex CLI returned a non-zero status.\n"
            f"  Exit code: {code}\n"
            f"  Details: {detail}"
        )

    return text, {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cached_input_tokens", 0),
        "subscription_billing": True,
    }
