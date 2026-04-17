"""audit-agent bridge for ForgeGod runtime and CLI surfaces."""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forgegod.config import ForgeGodConfig

logger = logging.getLogger("forgegod.audit")

_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


@dataclass
class AuditState:
    exists: bool = False
    ready_to_plan: bool = True
    blockers: list[str] = field(default_factory=list)
    high_risk_modules: list[str] = field(default_factory=list)
    recommended_start_points: list[str] = field(default_factory=list)
    source: str = "missing"
    message: str = ""
    specialist_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)


def resolve_audit_command(config: ForgeGodConfig) -> list[str] | None:
    """Resolve the audit-agent command prefix for this environment."""
    spec = (config.audit.command or "auto").strip()
    if spec and spec.lower() != "auto":
        return shlex.split(spec)
    if shutil.which("audit"):
        return ["audit"]
    if importlib.util.find_spec("audit_agent.cli.main") is not None:
        return [sys.executable, "-m", "audit_agent.cli.main"]
    return None


def invoke_audit_surface(
    config: ForgeGodConfig,
    surface: str,
    *,
    project_root: Path | None = None,
    args: list[str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Invoke an audit-agent surface from ForgeGod."""
    command_prefix = resolve_audit_command(config)
    if command_prefix is None:
        raise RuntimeError(
            "audit-agent is not available. Install it with `pip install audit-agent` "
            "or configure [audit].command to point at a valid executable."
        )

    repo_root = Path(project_root or config.project_dir.parent).resolve()
    command = [*command_prefix, surface]
    if args:
        command.extend(args)
    command.append(str(repo_root))
    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=config.audit.timeout_s,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"audit-agent {surface} failed with exit code {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()}"
        )
    return result


def ensure_audit_ready(
    config: ForgeGodConfig,
    *,
    reason: str = "manual",
    project_root: Path | None = None,
) -> AuditState:
    """Ensure base audit artifacts exist and are current enough for ForgeGod."""
    repo_root = Path(project_root or config.project_dir.parent).resolve()
    state = load_audit_state(config, project_root=repo_root)
    command_prefix = resolve_audit_command(config)

    if not config.audit.enabled:
        return state

    should_auto_run = (
        (reason == "loop" and config.audit.auto_run_on_loop)
        or (reason == "hive" and config.audit.auto_run_on_hive)
        or reason not in {"loop", "hive"}
    )

    if command_prefix is None:
        if not state.exists:
            state.message = (
                "audit-agent is not available and no cached AUDIT artifact exists. "
                "Install audit-agent or generate .forgegod/AUDIT.md manually."
            )
        return state

    status_result = invoke_audit_surface(config, "status", project_root=repo_root)
    if status_result.returncode == 0:
        current = load_audit_state(config, project_root=repo_root)
        if current.exists:
            current.message = "audit-agent status reports a current AUDIT surface."
            return current
        state.message = "audit-agent status passed but AUDIT artifacts were not found."
        return state

    if should_auto_run:
        run_result = invoke_audit_surface(config, "run", project_root=repo_root)
        refreshed = load_audit_state(config, project_root=repo_root)
        if refreshed.exists:
            refreshed.message = (
                "audit-agent refreshed the repo before ForgeGod execution."
                if run_result.returncode == 0
                else (run_result.stderr or run_result.stdout).strip()
            )
            return refreshed
        state.message = (run_result.stderr or run_result.stdout).strip() or (
            "audit-agent run did not produce AUDIT artifacts."
        )
        return state

    state.message = (status_result.stderr or status_result.stdout).strip() or (
        "audit-agent reported stale or missing AUDIT artifacts."
    )
    return state


def load_audit_state(
    config: ForgeGodConfig,
    *,
    project_root: Path | None = None,
) -> AuditState:
    """Load cached audit-agent artifacts from .forgegod/."""
    repo_root = Path(project_root or config.project_dir.parent).resolve()
    project_dir = repo_root / ".forgegod"
    state = AuditState()

    payload = _load_json_payload(project_dir / "AUDIT.json", "audit_agent")
    source = "AUDIT.json"
    if payload is None:
        payload = _load_markdown_payload(project_dir / "AUDIT.md", "audit_agent")
        source = "AUDIT.md"

    if payload is not None:
        state.exists = True
        state.ready_to_plan = bool(payload.get("ready_to_plan", True))
        state.blockers = list(payload.get("blockers", []))
        state.high_risk_modules = list(payload.get("high_risk_modules", []))
        state.recommended_start_points = list(payload.get("recommended_start_points", []))
        state.source = source

    state.specialist_summaries = {
        "security": _load_specialist_summary(
            project_dir / "SECURITY_AUDIT.json",
            "specialist_audit",
        ),
        "architecture": _load_specialist_summary(
            project_dir / "ARCHITECTURE_AUDIT.json",
            "specialist_audit",
        ),
        "plan-risk": _load_specialist_summary(
            project_dir / "PLAN_RISK_AUDIT.json",
            "specialist_audit",
        ),
    }
    return state


def summarize_audit_state(state: AuditState) -> str:
    """Return a short human-readable audit summary."""
    if not state.exists:
        return "AUDIT missing"
    status = "READY" if state.ready_to_plan else "BLOCKED"
    return (
        f"{status} | blockers={len(state.blockers)} | "
        f"high_risk={len(state.high_risk_modules)} | source={state.source}"
    )


def _load_json_payload(path: Path, key: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    payload = data.get(key)
    return payload if isinstance(payload, dict) else None


def _load_markdown_payload(path: Path, key: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    match = _JSON_BLOCK_RE.search(content)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    payload = data.get(key)
    return payload if isinstance(payload, dict) else None


def _load_specialist_summary(path: Path, key: str) -> dict[str, Any]:
    payload = _load_json_payload(path, key)
    if payload is None:
        return {}
    return {
        "kind": payload.get("kind", ""),
        "ready": bool(payload.get("ready", True)),
        "blockers": list(payload.get("blockers", [])),
        "relevant_modules": list(payload.get("relevant_modules", [])),
    }
