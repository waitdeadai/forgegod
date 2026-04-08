from __future__ import annotations

import os
from pathlib import Path

import pytest
import toml
from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.sandbox import diagnose_strict_sandbox
from forgegod.testing.mock_openai_service import start_mock_openai_server

runner = CliRunner()


def _write_config(workspace: Path, base_url: str) -> None:
    config = ForgeGodConfig()
    config.models.coder = "openai:gpt-4o-mini"
    config.models.reviewer = "openai:gpt-4o-mini"
    config.models.sentinel = "openai:gpt-4o-mini"
    config.models.escalation = "openai:gpt-4o-mini"
    config.openai.base_url = base_url
    config.review.always_review_run = False
    config.review.enabled = False
    config.memory.enabled = False
    config.memory.extraction_enabled = False
    config.security.sandbox_mode = "strict"

    project_dir = workspace / ".forgegod"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "config.toml").write_text(
        toml.dumps(
            config.model_dump(
                mode="json",
                exclude={"global_dir", "project_dir"},
            )
        ),
        encoding="utf-8",
    )


@pytest.mark.skipif(
    os.environ.get("FORGEGOD_RUN_DOCKER_STRICT_TESTS") != "1",
    reason="Set FORGEGOD_RUN_DOCKER_STRICT_TESTS=1 to run real Docker strict-sandbox integration.",
)
def test_cli_strict_bash_roundtrip_with_real_docker_backend(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.security.sandbox_mode = "strict"
    readiness = diagnose_strict_sandbox(config.security)
    if not readiness.ready:
        pytest.skip(f"Strict sandbox not ready for integration test: {readiness.detail}")

    workspace = tmp_path / "strict-real-backend"
    workspace.mkdir()

    started = start_mock_openai_server("cli_strict_bash_roundtrip")
    try:
        _write_config(workspace, started.base_url)
        monkeypatch.chdir(workspace)
        monkeypatch.setenv("OPENAI_API_KEY", "mock-token")
        result = runner.invoke(
            app,
            [
                "run",
                "--no-review",
                "--permission-mode",
                "read-only",
                "Run python --version and report it.",
            ],
        )
    finally:
        started.stop()

    assert result.exit_code == 0, result.stdout
    assert "Strict sandbox reported Python 3.13.5." in result.stdout
    assert len(started.server.requests) == 2

    second_messages = started.server.requests[1]["messages"]
    tool_messages = [msg for msg in second_messages if msg.get("role") == "tool"]
    assert tool_messages
    assert "Python 3.13.5" in tool_messages[-1]["content"]
