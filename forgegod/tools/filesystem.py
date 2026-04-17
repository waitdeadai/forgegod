"""ForgeGod filesystem tools — read, write, edit, glob, grep, repo_map.

Security: all file operations apply secret redaction on output to prevent
API keys from leaking into LLM context. Write operations validate paths.
"""

from __future__ import annotations

import ast
import asyncio
import os
import re
from pathlib import Path

import aiofiles

from forgegod.security import validate_generated_code
from forgegod.tools import (
    blocked_path_reason,
    get_tool_config,
    get_workspace_root,
    register_tool,
    resolve_tool_path,
)

# ── Sensitive file patterns (warn but don't block reads) ──
SENSITIVE_PATTERNS = {
    ".env", ".env.local", ".env.production", ".env.staging",
    "credentials.json", "service-account.json", "secrets.yaml",
    "id_rsa", "id_ed25519", ".npmrc", ".pypirc",
}


def _check_sensitive_path(path: str) -> str | None:
    """Warn if a path looks like it contains secrets."""
    name = Path(path).name
    if name in SENSITIVE_PATTERNS:
        return f"WARNING: {name} may contain secrets. Contents will be redacted."
    return None


def _redact_file_secrets(content: str) -> str:
    """Redact obvious secrets from file content before sending to LLM."""
    from forgegod.tools.shell import redact_secrets

    config = get_tool_config()
    security = getattr(config, "security", None) if config else None
    if security and not getattr(security, "redact_secrets", True):
        return content
    return redact_secrets(content)


def _display_path(path: Path) -> str:
    """Render a path relative to the active workspace when possible."""
    config = get_tool_config()
    if not config:
        return str(path)

    root = get_workspace_root().resolve()
    try:
        return str(path.resolve(strict=False).relative_to(root))
    except ValueError:
        return str(path)


def _validate_write_target(
    path: str, *, must_exist: bool = False
) -> tuple[Path | None, str | None]:
    """Resolve a file path and enforce workspace/blocked path rules."""
    resolved, error = resolve_tool_path(path, must_exist=must_exist)
    if error:
        return None, error
    assert resolved is not None

    blocked = blocked_path_reason(resolved)
    if blocked:
        return None, f"Error: Path blocked by security policy: {blocked}"
    return resolved, None


def _security_write_gate(path: Path, content: str) -> tuple[str, bool]:
    """Return a security notice and whether the write must be blocked."""
    if path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx", ".sh", ".rb", ".go", ".rs"}:
        return "", False

    warnings = validate_generated_code(content)
    if not warnings:
        return "", False

    config = get_tool_config()
    security = getattr(config, "security", None) if config else None
    sandbox_mode = getattr(security, "sandbox_mode", "standard")

    prefix = "BLOCKED" if sandbox_mode == "strict" else "Warning"
    notice = f"{prefix}: Security validation flagged generated code:\n"
    notice += "\n".join(f"- {warning}" for warning in warnings[:10]) + "\n"
    return notice, sandbox_mode == "strict"


async def read_file(path: str, offset: int = 0, limit: int = 500) -> str:
    """Read file contents with optional line range. True async I/O."""
    p, error = _validate_write_target(path, must_exist=True)
    if error:
        return error
    assert p is not None
    if not p.is_file():
        return f"Error: Not a file: {path}"
    try:
        warning = _check_sensitive_path(str(p))
        raw = await asyncio.to_thread(
            p.read_text,
            encoding="utf-8",
            errors="replace",
        )
        lines = raw.splitlines()
        total = len(lines)
        selected = lines[offset : offset + limit]
        numbered = [f"{i + offset + 1}\t{line}" for i, line in enumerate(selected)]
        display = _display_path(p)
        header = f"[{display}] Lines {offset + 1}-{min(offset + limit, total)} of {total}"
        result = header + "\n" + "\n".join(numbered)
        # Redact secrets from output before sending to LLM context
        result = _redact_file_secrets(result)
        if warning:
            result = warning + "\n" + result
        return result
    except Exception as e:
        return f"Error reading {path}: {e}"


async def write_file(path: str, content: str) -> str:
    """Write content to a file (creates parent dirs). True async + atomic write."""
    p, error = _validate_write_target(path)
    if error:
        return error
    assert p is not None
    tmp = p.with_suffix(p.suffix + ".forgegod.tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: async write to temp file, then rename
        async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
            await f.write(content)
        display = _display_path(p)
        notice, blocked = _security_write_gate(p, content)
        if blocked:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return notice.strip()
        tmp.replace(p)
        return f"{notice}Written {len(content)} bytes to {display}".strip()
    except Exception as e:
        # Clean up temp file on error
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return f"Error writing {path}: {e}"


async def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Replace old_string with new_string in a file.

    Uses multi-pass fuzzy matching (inspired by OpenDev's 9-pass pattern)
    when exact match fails — LLM-generated edits are frequently imperfect
    due to whitespace, indentation, or minor formatting differences.
    """
    p, error = _validate_write_target(path, must_exist=True)
    if error:
        return error
    assert p is not None
    try:
        content = p.read_text(encoding="utf-8")
        display = _display_path(p)

        # Pass 1: Exact match (preferred)
        if old_string in content:
            count = content.count(old_string)
            if count > 1:
                return f"Error: old_string found {count} times in {path} — must be unique"
            updated = content.replace(old_string, new_string, 1)
            notice, blocked = _security_write_gate(p, updated)
            if blocked:
                return notice.strip()
            p.write_text(updated, encoding="utf-8")
            return f"{notice}Edited {display}: replaced 1 occurrence".strip()

        # Pass 2: Whitespace-normalized match
        normalized_content = _normalize_whitespace(content)
        normalized_old = _normalize_whitespace(old_string)
        if normalized_old in normalized_content:
            # Find original span by matching line-by-line
            match_result = _find_fuzzy_span(content, old_string)
            if match_result:
                start, end = match_result
                updated = content[:start] + new_string + content[end:]
                notice, blocked = _security_write_gate(p, updated)
                if blocked:
                    return notice.strip()
                p.write_text(updated, encoding="utf-8")
                return (
                    f"{notice}Edited {display}: replaced 1 occurrence "
                    "(fuzzy whitespace match)"
                ).strip()

        # Pass 3: Strip trailing whitespace from both sides
        stripped_lines = [ln.rstrip() for ln in content.splitlines()]
        stripped_old = [ln.rstrip() for ln in old_string.splitlines()]
        stripped_content = "\n".join(stripped_lines)
        stripped_old_str = "\n".join(stripped_old)
        if stripped_old_str in stripped_content:
            match_result = _find_fuzzy_span(content, old_string)
            if match_result:
                start, end = match_result
                updated = content[:start] + new_string + content[end:]
                notice, blocked = _security_write_gate(p, updated)
                if blocked:
                    return notice.strip()
                p.write_text(updated, encoding="utf-8")
                return (
                    f"{notice}Edited {display}: replaced 1 occurrence "
                    "(fuzzy trailing-ws match)"
                ).strip()

        file_lines = len(content.splitlines())
        preview = old_string[:50] if len(old_string) > 50 else old_string
        return (
            f"Error: old_string not found in {path}. "
            f"File has {file_lines} lines. Searching for: '{preview}...'. "
            f"Hint: use read_file first to inspect the file contents."
        )
    except Exception as e:
        return f"Error editing {path}: {e}"


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for fuzzy matching."""
    lines = text.splitlines()
    return "\n".join(line.strip() for line in lines)


def _find_fuzzy_span(content: str, target: str) -> tuple[int, int] | None:
    """Find the span in content that best matches target, tolerating whitespace differences.

    Returns (start_idx, end_idx) or None.
    """
    target_lines = [ln.rstrip() for ln in target.splitlines()]
    content_lines = content.splitlines(keepends=True)

    if not target_lines:
        return None

    # Slide window over content lines looking for best match
    for i in range(len(content_lines) - len(target_lines) + 1):
        matched = True
        for j, tl in enumerate(target_lines):
            if content_lines[i + j].rstrip("\n\r").rstrip() != tl:
                matched = False
                break
        if matched:
            start = sum(len(content_lines[k]) for k in range(i))
            end = sum(len(content_lines[k]) for k in range(i, i + len(target_lines)))
            return (start, end)

    return None


async def glob_files(
    pattern: str, path: str = ".", max_results: int = 500,
) -> str:
    """Find files matching a glob pattern."""
    base, error = _validate_write_target(path, must_exist=True)
    if error:
        return error
    assert base is not None
    if not base.exists():
        return f"Error: Directory not found: {path}"
    try:
        matches = sorted(_display_path(p) for p in base.rglob(pattern))[:max_results]
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        return f"Found {len(matches)} files:\n" + "\n".join(matches)
    except Exception as e:
        return f"Error globbing: {e}"


async def grep_files(
    pattern: str, path: str = ".", file_type: str = "",
    max_results: int = 100, offset: int = 0,
) -> str:
    """Search file contents with regex pattern."""
    base, error = _validate_write_target(path, must_exist=True)
    if error:
        return error
    assert base is not None
    if not base.exists():
        return f"Error: Directory not found: {path}"

    ext_filter = f"*.{file_type}" if file_type else "*"
    results: list[str] = []
    skipped = 0
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regex: {e}"

    try:
        for filepath in base.rglob(ext_filter):
            if not filepath.is_file():
                continue
            if filepath.stat().st_size > 1_000_000:
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        if skipped < offset:
                            skipped += 1
                            continue
                        results.append(f"{_display_path(filepath)}:{i}: {line.rstrip()[:200]}")
                        if len(results) >= max_results:
                            header = f"Found {len(results)}+ matches (truncated):"
                            return header + "\n" + "\n".join(results)
            except (OSError, UnicodeDecodeError):
                continue

        if not results:
            return f"No matches for '{pattern}' in {path}"
        return f"Found {len(results)} matches:\n" + "\n".join(results)
    except Exception as e:
        return f"Error grepping: {e}"


async def repo_map(path: str = ".", max_files: int = 500) -> str:
    """Generate a codebase map: file tree + Python class/function signatures.

    This is critical for agent orientation — gives a high-level view of
    the codebase structure so the agent knows where to look. Inspired by
    Aider's repo map (one of the biggest SWE-bench score drivers).
    """
    base, error = _validate_write_target(path, must_exist=True)
    if error:
        return error
    assert base is not None
    if not base.exists():
        return f"Error: Directory not found: {path}"

    SKIP_DIRS = {
        ".git", "__pycache__", "node_modules", ".forgegod", ".venv",
        "venv", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
        ".next", ".nuxt", "coverage", ".eggs",
    }
    SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".png", ".jpg", ".gif", ".ico"}

    lines: list[str] = []
    file_count = 0

    for root, dirs, files in os.walk(base):
        # Skip hidden/build directories
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS and not d.startswith(".")]

        rel_root = Path(root).relative_to(base)
        depth = len(rel_root.parts)

        for fname in sorted(files):
            if file_count >= max_files:
                lines.append(f"\n... truncated at {max_files} files")
                return "\n".join(lines)

            fpath = Path(root) / fname
            if fpath.suffix in SKIP_EXTS:
                continue

            rel_path = fpath.relative_to(base)
            indent = "  " * depth

            # Get file metadata
            try:
                stat = fpath.stat()
                size_bytes = stat.st_size
                mtime = stat.st_mtime
                # Human-readable size
                if size_bytes < 1024:
                    size_str = f"{size_bytes}B"
                elif size_bytes < 1024 ** 2:
                    size_str = f"{size_bytes / 1024:.1f}KB"
                elif size_bytes < 1024 ** 3:
                    size_str = f"{size_bytes / (1024 ** 2):.1f}MB"
                else:
                    size_str = f"{size_bytes / (1024 ** 3):.1f}GB"
                # Human-readable date
                from datetime import datetime
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                size_str = "?"
                mtime_str = "?"

            # For Python files: extract class/function signatures
            if fpath.suffix == ".py":
                sigs = _extract_python_signatures(fpath)
                if sigs:
                    lines.append(f"{indent}{rel_path} ({size_str}, {mtime_str})")
                    for sig in sigs:
                        lines.append(f"{indent}  {sig}")
                else:
                    lines.append(f"{indent}{rel_path} ({size_str}, {mtime_str})")
            else:
                lines.append(f"{indent}{rel_path} ({size_str}, {mtime_str})")

            file_count += 1

    if not lines:
        return f"No files found in {path}"
    return f"Repo map ({file_count} files):\n" + "\n".join(lines)


def _extract_python_signatures(filepath: Path) -> list[str]:
    """Extract top-level class and function signatures from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    sigs: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(
                ast.unparse(b) for b in node.bases
            ) if node.bases else ""
            sigs.append(f"class {node.name}({bases})" if bases else f"class {node.name}")
            # Add method signatures
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
                    args = _format_args(item.args)
                    ret = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                    sigs.append(f"  {prefix}def {item.name}({args}){ret}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            args = _format_args(node.args)
            ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            sigs.append(f"{prefix}def {node.name}({args}){ret}")

    return sigs


def _format_args(args: ast.arguments) -> str:
    """Format function arguments into a concise signature."""
    parts: list[str] = []
    defaults_offset = len(args.args) - len(args.defaults)

    for i, arg in enumerate(args.args):
        if arg.arg == "self" or arg.arg == "cls":
            continue
        annotation = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
        default_idx = i - defaults_offset
        default = " = ..." if default_idx >= 0 and default_idx < len(args.defaults) else ""
        parts.append(f"{arg.arg}{annotation}{default}")

    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwonlyargs:
        for kw in args.kwonlyargs:
            ann = f": {ast.unparse(kw.annotation)}" if kw.annotation else ""
            parts.append(f"{kw.arg}{ann}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return ", ".join(parts)


# ── Register all filesystem tools ──

register_tool(
    name="read_file",
    description="Read the contents of a file with line numbers. Use offset/limit for large files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "offset": {"type": "integer", "description": "Starting line (0-indexed)", "default": 0},
            "limit": {"type": "integer", "description": "Max lines to read", "default": 500},
        },
        "required": ["path"],
    },
    handler=read_file,
)

register_tool(
    name="write_file",
    description="Write content to a file. Creates the file and parent dirs if they don't exist.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
    handler=write_file,
)

register_tool(
    name="edit_file",
    description="Replace a unique string in a file. old_string must appear exactly once.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to edit"},
            "old_string": {
                "type": "string",
                "description": "Exact string to find (must be unique)",
            },
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"],
    },
    handler=edit_file,
)

register_tool(
    name="glob",
    description="Find files matching a glob pattern (e.g., '**/*.py', 'src/*.ts').",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern"},
            "path": {"type": "string", "description": "Directory to search", "default": "."},
            "max_results": {
                "type": "integer", "description": "Max files to return",
                "default": 500,
            },
        },
        "required": ["pattern"],
    },
    handler=glob_files,
)

register_tool(
    name="grep",
    description="Search file contents with a regex pattern. Returns matching lines.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search"},
            "path": {"type": "string", "description": "Directory to search", "default": "."},
            "file_type": {
                "type": "string",
                "description": "File extension filter (e.g., 'py')",
                "default": "",
            },
            "max_results": {
                "type": "integer",
                "description": "Max matches to return",
                "default": 100,
            },
            "offset": {
                "type": "integer",
                "description": "Skip first N matches (pagination)",
                "default": 0,
            },
        },
        "required": ["pattern"],
    },
    handler=grep_files,
)

register_tool(
    name="repo_map",
    description=(
        "Generate a codebase map: file tree + class/function signatures. "
        "Use this FIRST to orient yourself in a new codebase."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Root directory to map", "default": "."},
            "max_files": {"type": "integer", "description": "Max files to include", "default": 200},
        },
    },
    handler=repo_map,
)
