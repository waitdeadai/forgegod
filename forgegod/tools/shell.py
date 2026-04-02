"""ForgeGod shell tool — bash execution with safety guardrails.

Security layers (NemoClaw-inspired):
1. Command denylist — block destructive patterns before execution
2. Secret redaction — strip API keys/tokens from output before LLM context
3. Output truncation — prevent context flooding
4. Timeout enforcement — prevent runaway processes
"""

from __future__ import annotations

import asyncio
import re

from forgegod.tools import register_tool

# ── Dangerous command patterns (blocked by default) ──
# These match commands that could destroy data, exfiltrate secrets, or cause DoS.
# Users can bypass with config: security.sandbox_mode = "permissive"
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

# ── Secret patterns to redact from output ──
# Prevents API keys from leaking into LLM context window
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


def check_dangerous(command: str) -> str | None:
    """Check if a command matches dangerous patterns.

    Returns the reason string if blocked, None if safe.
    """
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


def redact_secrets(text: str) -> str:
    """Redact API keys, tokens, and secrets from text."""
    for pattern, replacement in SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


async def bash(command: str, timeout: int = 120) -> str:
    """Execute a shell command with safety guardrails.

    Security:
    - Dangerous commands are blocked (rm -rf /, curl|sh, sudo, etc.)
    - API keys/tokens in output are automatically redacted
    - Output is truncated to prevent context flooding
    - Timeout prevents runaway processes
    """
    # Layer 1: Command denylist
    danger = check_dangerous(command)
    if danger:
        return (
            f"BLOCKED: {danger}\n"
            f"Command: {command}\n"
            "This command was blocked by ForgeGod's safety guardrails.\n"
            "If you need to run it, execute it directly in your terminal."
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        output_parts: list[str] = []
        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            output_parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")

        output = "\n".join(output_parts).strip()

        # Layer 2: Secret redaction
        output = redact_secrets(output)

        # Layer 3: Output truncation
        if len(output) > 10_000:
            output = output[:5_000] + "\n\n[... truncated ...]\n\n" + output[-2_000:]

        exit_info = f"[exit code: {proc.returncode}]"
        return f"{output}\n{exit_info}" if output else exit_info

    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error executing command: {e}"


register_tool(
    name="bash",
    description=(
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "Dangerous commands (rm -rf /, curl|sh, sudo) are blocked. "
        "API keys in output are automatically redacted."
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
