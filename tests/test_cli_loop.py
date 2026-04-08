from __future__ import annotations

import json

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.models import LoopState

runner = CliRunner()


def test_loop_blocks_prompt_approval_with_parallel_workers(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    prd_path = config.project_dir / "prd.json"
    prd_path.write_text(json.dumps({"project": "ForgeGod", "stories": []}), encoding="utf-8")

    monkeypatch.setattr("forgegod.config.load_config", lambda: config)

    result = runner.invoke(
        app,
        [
            "loop",
            "--prd",
            str(prd_path),
            "--workers",
            "2",
            "--approval-mode",
            "prompt",
            "--dry-run",
        ],
    )

    assert result.exit_code == 1
    assert "Prompt approval mode is only supported with --workers 1." in result.stdout


def test_loop_passes_prompt_approver_in_single_worker(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir()
    prd_path = config.project_dir / "prd.json"
    prd_path.write_text(json.dumps({"project": "ForgeGod", "stories": []}), encoding="utf-8")

    sentinel_approver = object()
    captured: dict[str, object] = {}

    class FakeRouter:
        def __init__(self):
            captured["router"] = self
            self.closed = False

        async def close(self):
            self.closed = True
            return None

    class FakeLoop:
        state = LoopState()

        @classmethod
        def from_prd_file(cls, _prd_path, _config, **kwargs):
            captured["tool_approver"] = kwargs.get("tool_approver")
            return cls()

        async def run(self, dry_run: bool = False):
            return self.state

        async def stop(self):
            return None

    monkeypatch.setattr("forgegod.config.load_config", lambda: config)
    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.cli._build_tool_approver", lambda: sentinel_approver)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda _config: FakeRouter())
    monkeypatch.setattr("forgegod.loop.RalphLoop", FakeLoop)

    result = runner.invoke(
        app,
        [
            "loop",
            "--prd",
            str(prd_path),
            "--workers",
            "1",
            "--approval-mode",
            "prompt",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["tool_approver"] is sentinel_approver
    assert captured["router"].closed is True
