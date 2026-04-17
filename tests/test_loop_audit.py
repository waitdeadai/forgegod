from __future__ import annotations

from forgegod.config import ForgeGodConfig
from forgegod.loop import RalphLoop
from forgegod.models import PRD


def test_loop_check_audit_blocks_when_bridge_reports_not_ready(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()

    loop = RalphLoop(config=config, prd=PRD(project="demo"))

    class DummyState:
        exists = True
        ready_to_plan = False
        blockers = ["missing tests"]
        high_risk_modules = ["src/auth.py"]
        recommended_start_points = ["src/utils.py"]
        specialist_summaries = {"security": {"ready": False, "blockers": ["secret"]}}
        source = "AUDIT.json"
        message = "audit refreshed"

    monkeypatch.setattr("forgegod.loop.ensure_audit_ready", lambda *args, **kwargs: DummyState())

    assert loop._check_audit() is False
    assert loop.state.status.value == "paused"
    assert loop._audit_cache["specialists"]["security"]["blockers"] == ["secret"]


def test_loop_check_audit_allows_missing_bridge(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()

    loop = RalphLoop(config=config, prd=PRD(project="demo"))

    class MissingState:
        exists = False
        ready_to_plan = True
        blockers = []
        high_risk_modules = []
        recommended_start_points = []
        specialist_summaries = {}
        source = "missing"
        message = "audit-agent unavailable"

    monkeypatch.setattr("forgegod.loop.ensure_audit_ready", lambda *args, **kwargs: MissingState())

    assert loop._check_audit() is True
