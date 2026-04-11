"""Native auth helpers for provider-owned CLIs and subscription surfaces."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def find_command(command: str) -> str | None:
    """Return the resolved executable path for a command if present."""
    return shutil.which(command)


@dataclass(frozen=True)
class CodexBackend:
    """Resolved execution backend for Codex automation."""

    mode: str  # native | wsl | unsupported
    detail: str
    command: str = ""
    wsl_exe: str = ""
    wsl_distribution: str = ""


def _inside_wsl() -> bool:
    """Return whether the current Python process is already running inside WSL."""
    release = platform.release().lower()
    return bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in release


def _normalize_subprocess_text(text: str) -> str:
    """Normalize subprocess output from Windows/WSL tools."""
    return text.replace("\x00", "").strip()


def _wsl_base_argv(wsl_exe: str, distribution: str = "") -> list[str]:
    """Return a base argv for invoking WSL."""
    argv = [wsl_exe]
    if distribution:
        argv.extend(["--distribution", distribution])
    return argv


def _wsl_shell_argv(wsl_exe: str, distribution: str, script: str) -> list[str]:
    """Return a bash login-shell invocation inside WSL."""
    return _wsl_base_argv(wsl_exe, distribution) + ["bash", "-lc", script]


def _list_wsl_distributions(wsl_exe: str) -> list[str]:
    """Return installed non-Docker WSL distributions."""
    try:
        proc = subprocess.run(
            [wsl_exe, "--list", "--quiet"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if proc.returncode != 0:
        return []

    distros: list[str] = []
    for raw_line in _normalize_subprocess_text(proc.stdout).splitlines():
        name = raw_line.strip().lstrip("*").strip()
        if not name:
            continue
        lowered = name.lower()
        if lowered.startswith("docker-desktop"):
            continue
        distros.append(name)
    return distros


def _wsl_command_exists(wsl_exe: str, command: str, distribution: str) -> bool:
    """Return whether a command is available on PATH inside a WSL distro."""
    if not command or any(sep in command for sep in ("\\", "/")):
        return False
    script = f"command -v {shlex.quote(command)}"
    try:
        proc = subprocess.run(
            _wsl_shell_argv(wsl_exe, distribution, script),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and bool(_normalize_subprocess_text(proc.stdout))


def _windows_path_to_wsl(path: Path, wsl_exe: str, distribution: str) -> str:
    """Translate a Windows path to a WSL path."""
    resolved = Path(path).resolve()
    try:
        proc = subprocess.run(
            _wsl_base_argv(wsl_exe, distribution) + ["wslpath", "-a", str(resolved)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        proc = None

    if proc and proc.returncode == 0:
        converted = _normalize_subprocess_text(proc.stdout)
        if converted:
            return converted

    drive = resolved.drive.rstrip(":").lower()
    if drive:
        parts = [part for part in resolved.parts[1:] if part not in {"\\", "/"}]
        suffix = "/".join(part.replace("\\", "/") for part in parts)
        return f"/mnt/{drive}/{suffix}".rstrip("/")
    return str(resolved).replace("\\", "/")


def resolve_codex_backend(command: str = "codex") -> CodexBackend:
    """Resolve the best available backend for Codex automation."""
    if sys.platform != "win32":
        resolved = find_command(command)
        if resolved:
            return CodexBackend("native", "Codex automation supported", resolved)
        return CodexBackend("unsupported", "Codex CLI not found", command)

    if _inside_wsl():
        resolved = find_command(command)
        if resolved:
            return CodexBackend("native", "Codex automation supported in WSL", resolved)
        return CodexBackend(
            "unsupported",
            "Codex CLI not found inside WSL. Install it with `npm i -g @openai/codex`.",
            command,
        )

    native = find_command(command)
    release = platform.release().strip()
    if native:
        if release == "10":
            detail = (
                "Codex automation supported on native Windows 10 "
                "(best effort; OpenAI recommends Windows 11 when standardizing)."
            )
        else:
            detail = "Codex automation supported on native Windows"
        return CodexBackend("native", detail, native)

    wsl_exe = find_command("wsl.exe") or find_command("wsl")
    if not wsl_exe:
        return CodexBackend(
            "unsupported",
            "Codex CLI not found on native Windows and WSL is not installed. "
            "Install Codex on Windows, or run `wsl --install` and install Codex inside WSL.",
            command,
        )

    preferred = os.environ.get("FORGEGOD_CODEX_WSL_DISTRO", "").strip()
    distros = _list_wsl_distributions(wsl_exe)
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    for distro in distros:
        if distro not in candidates:
            candidates.append(distro)

    if not candidates:
        return CodexBackend(
            "unsupported",
            "WSL is installed, but no Linux distribution is ready for Codex. "
            "Run `wsl --install` and install Codex inside the distro with "
            "`npm i -g @openai/codex`.",
            command,
        )

    for distro in candidates:
        if _wsl_command_exists(wsl_exe, command, distro):
            return CodexBackend(
                "wsl",
                f"Codex automation supported through WSL ({distro})",
                command,
                wsl_exe,
                distro,
            )

    if preferred:
        return CodexBackend(
            "unsupported",
            f"WSL distro `{preferred}` is available, but `{command}` was not found "
            "on PATH inside it. "
            "Install Codex inside WSL with `npm i -g @openai/codex`.",
            command,
        )

    return CodexBackend(
        "unsupported",
        "Codex CLI was not found on native Windows or in any configured WSL distro. "
        "Install Codex on Windows, or inside WSL with `npm i -g @openai/codex`.",
        command,
    )


def codex_automation_status(command: str = "codex") -> tuple[bool, str]:
    """Return whether Codex CLI is a reliable automation backend in this environment."""
    backend = resolve_codex_backend(command)
    return backend.mode != "unsupported", backend.detail


def codex_login_argv(command: str = "codex") -> list[str]:
    """Return the argv that should launch the interactive Codex login flow."""
    backend = resolve_codex_backend(command)
    if backend.mode == "unsupported":
        raise RuntimeError(backend.detail)
    if backend.mode == "wsl":
        script = f"exec {shlex.quote(backend.command)} login"
        return _wsl_shell_argv(backend.wsl_exe, backend.wsl_distribution, script)
    return [backend.command, "login"]


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
    backend = resolve_codex_backend(command)
    if backend.mode == "unsupported":
        return False, backend.detail

    try:
        if backend.mode == "wsl":
            code, stdout, stderr = await run_command(
                _wsl_shell_argv(
                    backend.wsl_exe,
                    backend.wsl_distribution,
                    f"exec {shlex.quote(backend.command)} login status",
                ),
                timeout=20.0,
            )
        else:
            code, stdout, stderr = await run_command(
                [backend.command, "login", "status"],
                timeout=20.0,
            )
    except RuntimeError as e:
        return False, str(e)
    text = (stdout or stderr).strip()
    return code == 0 and "Logged in" in text, text


def codex_login_status_sync(command: str = "codex") -> tuple[bool, str]:
    """Synchronous version of Codex login-status checks."""
    backend = resolve_codex_backend(command)
    if backend.mode == "unsupported":
        return False, backend.detail

    argv = [backend.command, "login", "status"]
    if backend.mode == "wsl":
        argv = _wsl_shell_argv(
            backend.wsl_exe,
            backend.wsl_distribution,
            f"exec {shlex.quote(backend.command)} login status",
        )

    proc = subprocess.run(
        argv,
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
    backend = resolve_codex_backend(command)
    if backend.mode == "unsupported":
        raise RuntimeError(
            "error: Codex CLI is not ready.\n"
            f"  Fix: {backend.detail}\n"
            "  Then run: codex login"
        )

    argv: list[str]
    effective_cwd: Path | None = cwd
    if backend.mode == "wsl":
        wsl_cwd = _windows_path_to_wsl(cwd, backend.wsl_exe, backend.wsl_distribution)
        exec_args = [
            backend.command,
            "exec",
            "--disable",
            "plugins",
            "--disable",
            "shell_snapshot",
            "--skip-git-repo-check",
            "--json",
            "-C",
            wsl_cwd,
            "-s",
            sandbox,
        ]
        if ephemeral:
            exec_args.append("--ephemeral")
        if model:
            exec_args.extend(["-m", model])
        exec_args.append("-")
        script = " ".join(shlex.quote(arg) for arg in exec_args)
        argv = _wsl_shell_argv(backend.wsl_exe, backend.wsl_distribution, f"exec {script}")
        effective_cwd = None
    else:
        argv = [
            backend.command,
            "exec",
            "--disable",
            "plugins",
            "--disable",
            "shell_snapshot",
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
        cwd=effective_cwd,
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
