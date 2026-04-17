from __future__ import annotations

import subprocess
from io import StringIO

import pytest
from rich.console import Console
from typer.testing import CliRunner

from forgegod.audit import AuditState
from forgegod.cli import app
from forgegod.config import ForgeGodConfig

runner = CliRunner()


@pytest.fixture
def printed(monkeypatch):
    buffer = StringIO()
    capture_console = Console(file=buffer, force_terminal=False, width=120)
    monkeypatch.setattr("forgegod.cli.console.print", capture_console.print)
    return buffer


def test_audit_status_uses_cached_state(monkeypatch, tmp_path, printed):
    monkeypatch.setattr(
        "forgegod.cli._load_audit_bridge_config",
        lambda path=None: (tmp_path, ForgeGodConfig()),
    )
    monkeypatch.setattr(
        "forgegod.audit.load_audit_state",
        lambda config, project_root=None: AuditState(
            exists=True,
            ready_to_plan=False,
            blockers=["missing tests"],
            source="AUDIT.json",
            specialist_summaries={"security": {"ready": False, "blockers": ["secret"]}},
        ),
    )

    result = runner.invoke(app, ["audit", "status", "--path", str(tmp_path)])

    assert result.exit_code == 0
    visible = printed.getvalue()
    assert "BLOCKED" in visible
    assert "missing tests" in visible
    assert "security" in visible


def test_audit_run_surfaces_failures(monkeypatch, tmp_path, printed):
    monkeypatch.setattr(
        "forgegod.cli._run_audit_cli_surface",
        lambda surface, path=None, args=None: (
            tmp_path,
            ForgeGodConfig(),
            subprocess.CompletedProcess(["audit", "run"], 1, "", "blocked"),
            AuditState(exists=True, ready_to_plan=False, blockers=["blocked by audit"]),
            "BLOCKED | blockers=1 | high_risk=0 | source=AUDIT.json",
        ),
    )

    result = runner.invoke(app, ["audit", "run", "--path", str(tmp_path)])

    assert result.exit_code == 1
    visible = printed.getvalue()
    assert "BLOCKED" in visible
    assert "blocked by audit" in visible
