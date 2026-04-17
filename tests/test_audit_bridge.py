from __future__ import annotations

import json
import subprocess

from forgegod.audit import AuditState, ensure_audit_ready, load_audit_state, summarize_audit_state
from forgegod.config import ForgeGodConfig


def test_load_audit_state_reads_json_and_specialist_artifacts(tmp_path):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    (project_dir / "AUDIT.json").write_text(
        json.dumps(
            {
                "audit_agent": {
                    "ready_to_plan": False,
                    "blockers": ["missing tests"],
                    "high_risk_modules": ["src/auth.py"],
                    "recommended_start_points": ["src/utils.py"],
                }
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "SECURITY_AUDIT.json").write_text(
        json.dumps(
            {
                "specialist_audit": {
                    "kind": "security",
                    "ready": False,
                    "blockers": ["hardcoded secret"],
                    "relevant_modules": ["src/auth.py"],
                }
            }
        ),
        encoding="utf-8",
    )

    config = ForgeGodConfig()
    config.project_dir = project_dir

    state = load_audit_state(config, project_root=tmp_path)

    assert state.exists is True
    assert state.ready_to_plan is False
    assert state.blockers == ["missing tests"]
    assert state.specialist_summaries["security"]["blockers"] == ["hardcoded secret"]
    assert summarize_audit_state(state).startswith("BLOCKED")


def test_ensure_audit_ready_auto_runs_when_status_is_stale(tmp_path, monkeypatch):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    config = ForgeGodConfig()
    config.project_dir = project_dir

    calls: list[str] = []

    def fake_resolve(_config):
        return ["audit"]

    def fake_invoke(_config, surface, **kwargs):
        calls.append(surface)
        if surface == "status":
            return subprocess.CompletedProcess(["audit", "status"], 1, "", "stale")
        (project_dir / "AUDIT.json").write_text(
            json.dumps(
                {
                    "audit_agent": {
                        "ready_to_plan": True,
                        "blockers": [],
                        "high_risk_modules": ["src/payment.py"],
                        "recommended_start_points": ["src/utils.py"],
                    }
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(["audit", "run"], 0, "ok", "")

    monkeypatch.setattr("forgegod.audit.resolve_audit_command", fake_resolve)
    monkeypatch.setattr("forgegod.audit.invoke_audit_surface", fake_invoke)

    state = ensure_audit_ready(config, reason="loop", project_root=tmp_path)

    assert calls == ["status", "run"]
    assert state.exists is True
    assert state.ready_to_plan is True
    assert state.high_risk_modules == ["src/payment.py"]


def test_ensure_audit_ready_reports_missing_command_without_cached_artifacts(tmp_path, monkeypatch):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"

    monkeypatch.setattr("forgegod.audit.resolve_audit_command", lambda _config: None)

    state = ensure_audit_ready(config, reason="manual", project_root=tmp_path)

    assert isinstance(state, AuditState)
    assert state.exists is False
    assert "audit-agent is not available" in state.message
