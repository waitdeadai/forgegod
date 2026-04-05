"""Security — prompt injection defense for autonomous coding agent.

Provides:
1. File content sanitization (flag injection patterns in code comments/docs)
2. Generated code validation (block credential access, suspicious imports)
3. Canary token system (detect if system prompt leaks into tool calls)

Based on 2026 OWASP LLM Top 10 and research on coding agent vulnerabilities.
"""

from __future__ import annotations

import logging
import re
import secrets

logger = logging.getLogger(__name__)

# ── Injection patterns in file content ────────────────────────────────────
# These patterns in code comments or docstrings suggest injection attempts.
_FILE_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|a)\s+", re.IGNORECASE),
    re.compile(r"(new|change)\s+(role|mode|personality)", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"(reveal|show|print)\s+(your|the)\s+(prompt|instructions)", re.IGNORECASE),
    re.compile(r"\bDAN\b|\bjailbreak\b", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|endoftext\|>|\[INST\]|\[/INST\]", re.IGNORECASE),
    re.compile(r"from now on|override safety|bypass filter", re.IGNORECASE),
]

# ── Dangerous patterns in generated code ──────────────────────────────────
_DANGEROUS_CODE_PATTERNS = [
    re.compile(r"""open\s*\(\s*['"]\.env['"]"""),
    re.compile(r"""open\s*\(\s*['"].*credentials.*['"]""", re.IGNORECASE),
    re.compile(r"""open\s*\(\s*['"].*\.pem['"]"""),
    re.compile(r"""open\s*\(\s*['"].*id_rsa.*['"]"""),
    re.compile(r"""os\.(system|popen|exec[lv]p?e?)\s*\("""),
    re.compile(r"""subprocess\.(call|run|Popen)\s*\(.*(curl|wget|nc\b)""", re.IGNORECASE),
    re.compile(r"""eval\s*\(\s*(input|raw_input|os\.environ)"""),
    re.compile(
        r"""(requests|httpx|urllib)\.(get|post)\s*\(.*(ngrok|burp|requestbin)""",
        re.IGNORECASE,
    ),
]


def check_file_content(path: str, content: str) -> list[str]:
    """Check file content for injection patterns.

    Returns list of warnings (empty = clean). Does NOT modify content.
    For coding agents, we flag but don't strip — false positives are likely
    in legitimate code comments and documentation.
    """
    warnings = []
    for pattern in _FILE_INJECTION_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            warnings.append(
                f"[SECURITY] Possible injection in {path}: "
                f"pattern '{pattern.pattern[:40]}' matched {len(matches)}x"
            )
    return warnings


def validate_generated_code(code: str) -> list[str]:
    """Validate AI-generated code before writing to disk.

    Returns list of warnings (empty = safe).
    """
    warnings = []
    for pattern in _DANGEROUS_CODE_PATTERNS:
        if pattern.search(code):
            warnings.append(
                f"[SECURITY] Suspicious code pattern: {pattern.pattern[:50]}"
            )
    return warnings


class CanaryToken:
    """Canary token system — detects if system prompt leaks into tool args.

    Usage:
        canary = CanaryToken()
        system_prompt = f"... {canary.marker} ..."
        # Before executing any tool call:
        if canary.check(tool_args_string):
            logger.error("Canary triggered — possible prompt extraction!")
    """

    def __init__(self):
        self._token = f"FGCANARY-{secrets.token_hex(8)}"

    @property
    def marker(self) -> str:
        """Invisible marker to embed in system prompt."""
        return f"<!-- {self._token} -->"

    def check(self, text: str) -> bool:
        """Check if canary token leaked into text."""
        if self._token in text:
            logger.error("Canary token detected in output — possible prompt extraction attack")
            return True
        return False
