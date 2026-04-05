"""Security — prompt injection defense for autonomous coding agent.

Provides:
1. File content sanitization (flag injection patterns in code comments/docs)
2. Generated code validation (block credential access, suspicious imports)
3. AST-based code analysis (detect obfuscated dangerous calls)
4. Supply chain validation (flag suspicious package imports)
5. Canary token system (detect if system prompt leaks into tool calls)

Based on 2026 OWASP LLM Top 10 and research on coding agent vulnerabilities.
"""

from __future__ import annotations

import ast
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

    Runs regex patterns + AST analysis + import validation.
    Returns list of warnings (empty = safe).
    """
    warnings = []
    # Layer 1: Regex patterns (fast, catches literal dangerous code)
    for pattern in _DANGEROUS_CODE_PATTERNS:
        if pattern.search(code):
            warnings.append(
                f"[SECURITY] Suspicious code pattern: {pattern.pattern[:50]}"
            )
    # Layer 2: AST analysis (catches obfuscated dangerous calls)
    warnings.extend(_ast_validate(code))
    # Layer 3: Supply chain validation (catches suspicious imports)
    warnings.extend(_validate_imports(code))
    return warnings


# ── AST-based code validation ───────────────────────────────────────────

_DANGEROUS_METHODS = {"system", "popen", "exec", "eval", "execl", "execlp", "execve"}
_SENSITIVE_PATHS = {".env", "id_rsa", "id_ed25519", ".pem", "credentials", "secrets"}

# Known abandoned/malicious packages (supply chain defense)
_SUSPICIOUS_PACKAGES = {
    "python-jose",    # abandoned, use PyJWT
    "python-jwt",     # abandoned, use PyJWT
    "jeIlyfish",      # typosquat of jellyfish
    "python3-dateutil",  # typosquat of python-dateutil
    "colors",         # common typosquat target
    "request",        # typosquat of requests
}


def _ast_validate(code: str) -> list[str]:
    """Parse code AST to detect dangerous patterns regex can't catch.

    Catches:
    - getattr(os, 'system')('...') obfuscation
    - Attribute calls to dangerous methods
    - open() on sensitive file paths
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # Can't parse — fall back to regex only

    warnings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # Detect: os.system(), subprocess.popen(), etc.
        if isinstance(func, ast.Attribute) and func.attr in _DANGEROUS_METHODS:
            warnings.append(
                f"[SECURITY] Dangerous call: .{func.attr}()"
            )

        # Detect: getattr(os, 'system') — obfuscated dangerous calls
        if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
            if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                if node.args[1].value in _DANGEROUS_METHODS:
                    val = node.args[1].value
                    warnings.append(
                        f"[SECURITY] Obfuscated dangerous call: "
                        f"getattr(..., '{val}')"
                    )

        # Detect: open() on sensitive file paths
        if isinstance(func, ast.Name) and func.id == "open" and node.args:
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                path = node.args[0].value
                for sensitive in _SENSITIVE_PATHS:
                    if sensitive in path:
                        warnings.append(
                            f"[SECURITY] Sensitive file access: open('{path}')"
                        )
                        break

    return warnings


def _validate_imports(code: str) -> list[str]:
    """Check imported packages against known-suspicious list."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    warnings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _SUSPICIOUS_PACKAGES:
                    warnings.append(
                        f"[SECURITY] Suspicious import: {root} (known abandoned/typosquat)"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in _SUSPICIOUS_PACKAGES:
                warnings.append(
                    f"[SECURITY] Suspicious import: {root} (known abandoned/typosquat)"
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

    def rotate(self):
        """Rotate canary token — call between sessions to detect ongoing leaks."""
        self._token = f"FGCANARY-{secrets.token_hex(8)}"
