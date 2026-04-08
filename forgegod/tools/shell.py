"""ForgeGod shell tool with layered runtime hardening.

The goal here is to make shell execution safer and more predictable:
1. Dangerous command denylist for all non-permissive modes
2. Secret redaction on tool output
3. Output truncation and timeout enforcement
4. Workspace-scoped cwd plus isolated HOME/cache/config env
5. Restricted shell syntax in standard/strict modes
6. Single-process execution plus command policy in strict mode
7. Real container sandbox execution in strict mode when available
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path

from forgegod.sandbox import SandboxUnavailableError, run_in_real_sandbox
from forgegod.tools import get_project_dir, get_tool_config, get_workspace_root, register_tool

# Dangerous patterns blocked in standard/strict modes.
DANGEROUS_PATTERNS = [
    (r"rm\s+(-[rf]+\s+)?/(?!tmp)", "Recursive delete from root"),
    (r"rm\s+-[rf]*\s+~", "Delete home directory"),
    (r"curl.*\|\s*(sh|bash|zsh)", "Pipe remote script to shell"),
    (r"wget.*\|\s*(sh|bash|zsh)", "Pipe remote script to shell"),
    (r"chmod\s+777", "World-writable permissions"),
    (r":\(\)\s*\{", "Fork bomb"),
    (r"mkfs\.", "Format filesystem"),
    (r"dd\s+if=.*of=/dev/", "Direct device write"),
    (r">\s*/dev/sd", "Direct device overwrite"),
    (r"npm\s+publish(?!\s+--dry)", "Accidental npm publish"),
    (r"pip\s+install\s+(?!-e\s)(?!--editable)(?!-r\s)(?!pytest)(?!ruff)", "Unvetted pip install"),
    (r"git\s+push.*--force\s+(origin\s+)?(main|master)", "Force push to main"),
    (r"eval\s*\(", "Dynamic eval"),
    (r"\bsudo\b", "Elevated privileges"),
]

SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED:openai_key]"),
    (r"sk-ant-[a-zA-Z0-9_-]{20,}", "[REDACTED:anthropic_key]"),
    (r"sk-or-[a-zA-Z0-9_-]{20,}", "[REDACTED:openrouter_key]"),
    (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED:github_pat]"),
    (r"gho_[a-zA-Z0-9]{36}", "[REDACTED:github_oauth]"),
    (r"github_pat_[a-zA-Z0-9_]{22,}", "[REDACTED:github_pat_v2]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED:aws_key]"),
    (r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}", "[REDACTED:jwt]"),
    (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "[REDACTED:private_key]"),
    (r"xox[bsp]-[a-zA-Z0-9-]+", "[REDACTED:slack_token]"),
    (r"AIza[a-zA-Z0-9_-]{35}", "[REDACTED:google_api_key]"),
]

RESTRICTED_SHELL_SYNTAX = [
    ("&&", "Command chaining"),
    ("||", "Conditional command chaining"),
    (";", "Multiple commands"),
    ("|", "Pipes"),
    (">", "Output redirection"),
    ("<", "Input redirection"),
    ("`", "Command substitution"),
    ("$(", "Command substitution"),
]

STRICT_ALLOWED_EXECUTABLES = {
    "python", "python.exe", "python3",
    "pytest", "ruff", "git", "rg",
    "ls", "dir", "cat", "type", "find", "findstr",
    "npm", "npx", "pnpm", "yarn", "bun",
    "uv", "poetry", "cargo", "go", "deno", "node",
    "make", "just",
}

STRICT_DISALLOWED_FLAGS = {
    "python": {"-c"},
    "python.exe": {"-c"},
    "python3": {"-c"},
    "node": {"-e", "--eval"},
    "deno": {"eval"},
}

STRICT_DISALLOWED_SUBCOMMANDS = {
    "git": {
        "add", "am", "apply", "bisect", "checkout", "cherry-pick", "clean",
        "clone", "commit", "fetch", "merge", "mv", "pull", "push", "rebase",
        "reset", "restore", "revert", "rm", "stash", "switch", "tag",
    },
    "npm": {
        "add", "cache", "ci", "install", "link", "login", "logout",
        "publish", "remove", "uninstall", "update",
    },
    "npx": {"npm"},
    "pnpm": {"add", "install", "link", "publish", "remove", "unlink", "update"},
    "yarn": {"add", "install", "link", "publish", "remove", "unlink", "upgrade"},
    "bun": {"add", "install", "publish", "remove", "update"},
    "uv": {"add", "init", "lock", "pip", "publish", "remove", "sync", "venv"},
    "poetry": {
        "add", "build", "cache", "config", "install", "lock", "publish",
        "remove", "self", "source", "update",
    },
    "cargo": {
        "add", "build", "clean", "doc", "fetch", "fix", "init", "install",
        "new", "package", "publish", "remove", "update",
    },
    "go": {"env", "fmt", "generate", "get", "install", "mod", "run", "work"},
    "deno": {"cache", "compile", "eval", "fmt", "info", "install", "upgrade"},
}

STRICT_PYTHON_BLOCKLIST = {
    ("-m", "pip"),
    ("-m", "ensurepip"),
    ("-m", "venv"),
}


def check_dangerous(command: str) -> str | None:
    """Return a block reason for obviously dangerous commands."""
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


def redact_secrets(text: str) -> str:
    """Redact common API keys and tokens from output."""
    for pattern, replacement in SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def _restricted_syntax_reason(command: str) -> str | None:
    """Block multi-command shell features in standard/strict modes."""
    for token, reason in RESTRICTED_SHELL_SYNTAX:
        if token in command:
            return reason
    return None


def _split_command(command: str) -> tuple[list[str] | None, str | None]:
    """Tokenize a command without invoking a shell parser."""
    try:
        argv = shlex.split(command, posix=(os.name != "nt"))
    except ValueError as e:
        return None, f"Invalid shell quoting: {e}"
    if not argv:
        return None, "Empty command"
    return argv, None


def _is_path_like(arg: str) -> bool:
    if arg in {".", ".."}:
        return True
    if arg.startswith("-"):
        return False
    if any(ch in arg for ch in ("*", "?")):
        return False
    return Path(arg).is_absolute() or "/" in arg or "\\" in arg


def _validate_arg_paths(argv: list[str], workspace_root: Path) -> str | None:
    """Reject arguments that resolve outside the active workspace."""
    for arg in argv[1:]:
        if not _is_path_like(arg):
            continue
        raw = Path(arg)
        candidate = raw if raw.is_absolute() else (workspace_root / raw)
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            continue
        try:
            resolved.relative_to(workspace_root)
        except ValueError:
            return f"Path escapes workspace root: {arg}"
    return None


def _first_non_flag(argv: list[str]) -> str:
    for arg in argv[1:]:
        if not arg.startswith("-"):
            return arg.lower()
    return ""


def _strict_policy_error(argv: list[str], workspace_root: Path) -> str | None:
    """Validate a strict-mode command before execution."""
    exe = Path(argv[0]).name.lower()
    if exe not in STRICT_ALLOWED_EXECUTABLES:
        return f"Executable not allowed in strict mode: {exe}"

    for flag in STRICT_DISALLOWED_FLAGS.get(exe, set()):
        if flag in argv[1:]:
            return f"Flag not allowed in strict mode: {exe} {flag}"

    if exe in {"python", "python.exe", "python3"}:
        for a, b in STRICT_PYTHON_BLOCKLIST:
            for i in range(len(argv) - 1):
                if argv[i] == a and argv[i + 1].lower() == b:
                    return f"Python module not allowed in strict mode: {b}"

    blocked_subcommands = STRICT_DISALLOWED_SUBCOMMANDS.get(exe, set())
    subcommand = _first_non_flag(argv)
    if subcommand in blocked_subcommands:
        return f"Subcommand not allowed in strict mode: {exe} {subcommand}"

    path_error = _validate_arg_paths(argv, workspace_root)
    if path_error:
        return path_error

    return None


def _sandbox_env(workspace_root: Path) -> dict[str, str]:
    """Build a per-repo process environment with isolated user/cache dirs."""
    sandbox_root = get_project_dir() / "sandbox"
    home_dir = sandbox_root / "home"
    tmp_dir = sandbox_root / "tmp"
    xdg_config = sandbox_root / "xdg-config"
    xdg_cache = sandbox_root / "xdg-cache"
    xdg_data = sandbox_root / "xdg-data"
    pycache_dir = sandbox_root / "pycache"

    for path in (home_dir, tmp_dir, xdg_config, xdg_cache, xdg_data, pycache_dir):
        path.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.update({
        "HOME": str(home_dir),
        "USERPROFILE": str(home_dir),
        "TMP": str(tmp_dir),
        "TEMP": str(tmp_dir),
        "TMPDIR": str(tmp_dir),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "XDG_DATA_HOME": str(xdg_data),
        "PYTHONPYCACHEPREFIX": str(pycache_dir),
        "PIP_CACHE_DIR": str(xdg_cache / "pip"),
        "PIP_CONFIG_FILE": str(xdg_config / "pip" / "pip.conf"),
        "POETRY_CACHE_DIR": str(xdg_cache / "pypoetry"),
        "UV_CACHE_DIR": str(xdg_cache / "uv"),
        "CARGO_HOME": str(xdg_data / "cargo"),
        "RUSTUP_HOME": str(xdg_data / "rustup"),
        "GOCACHE": str(xdg_cache / "go-build"),
        "GOMODCACHE": str(xdg_cache / "go-mod"),
        "DENO_DIR": str(xdg_cache / "deno"),
        "YARN_CACHE_FOLDER": str(xdg_cache / "yarn"),
        "npm_config_cache": str(xdg_cache / "npm"),
        "npm_config_userconfig": str(xdg_config / "npm" / "npmrc"),
        "BUN_INSTALL_CACHE_DIR": str(xdg_cache / "bun"),
        "GIT_CONFIG_GLOBAL": str(xdg_config / "git" / "config"),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "FORGEGOD_SANDBOX_ROOT": str(sandbox_root),
        "FORGEGOD_WORKSPACE_ROOT": str(workspace_root),
    })
    return env


def _blocked_message(reason: str, command: str) -> str:
    return (
        f"BLOCKED: {reason}\n"
        f"Command: {command}\n"
        "This command was blocked by ForgeGod's shell safety policy.\n"
        "If you need to run it, execute it directly in your terminal."
    )


async def bash(command: str, timeout: int = 120) -> str:
    """Execute a shell command with runtime hardening."""
    config = get_tool_config()
    security = getattr(config, "security", None) if config else None
    sandbox_mode = getattr(security, "sandbox_mode", "standard")
    redact_output = getattr(security, "redact_secrets", True)
    audit_commands = getattr(security, "audit_commands", False)

    workspace_root = get_workspace_root().resolve() if config else Path.cwd()
    cwd = str(workspace_root)
    env = _sandbox_env(workspace_root) if config else None

    if sandbox_mode != "permissive":
        danger = check_dangerous(command)
        if danger:
            return _blocked_message(danger, command)

    if sandbox_mode in {"standard", "strict"}:
        syntax_reason = _restricted_syntax_reason(command)
        if syntax_reason:
            return _blocked_message(
                f"{syntax_reason} is not allowed in {sandbox_mode} mode",
                command,
            )

    try:
        backend_name = "host"
        if sandbox_mode == "strict":
            argv, split_error = _split_command(command)
            if split_error:
                return _blocked_message(split_error, command)
            assert argv is not None

            policy_error = _strict_policy_error(argv, workspace_root)
            if policy_error:
                return _blocked_message(policy_error, command)

            if not config:
                return _blocked_message(
                    "Strict mode requires repo tool context for sandbox execution",
                    command,
                )

            try:
                result = await run_in_real_sandbox(
                    argv=argv,
                    workspace_root=workspace_root,
                    sandbox_root=get_project_dir() / "sandbox",
                    timeout=timeout,
                    security=security,
                )
            except SandboxUnavailableError as e:
                return _blocked_message(str(e), command)

            stdout = result.stdout.encode("utf-8", errors="replace")
            stderr = result.stderr.encode("utf-8", errors="replace")
            returncode = result.returncode
            backend_name = result.backend
        else:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            returncode = proc.returncode

        output_parts: list[str] = []
        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            output_parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")
        output = "\n".join(output_parts).strip()

        if redact_output:
            output = redact_secrets(output)

        if len(output) > 10_000:
            output = output[:5_000] + "\n\n[... truncated ...]\n\n" + output[-2_000:]

        if audit_commands and config:
            log_dir = get_project_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            audit_line = (
                f"{datetime.now(timezone.utc).isoformat()}\t"
                f"{returncode}\t{sandbox_mode}\t{backend_name}\t{command}\n"
            )
            with open(log_dir / "commands.log", "a", encoding="utf-8") as audit_file:
                audit_file.write(audit_line)

        exit_info = f"[exit code: {returncode}]"
        return f"{output}\n{exit_info}" if output else exit_info

    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error executing command: {e}"


register_tool(
    name="bash",
    description=(
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "Non-permissive modes block dangerous commands; strict mode also uses "
        "single-process execution with an isolated environment."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
        },
        "required": ["command"],
    },
    handler=bash,
)
