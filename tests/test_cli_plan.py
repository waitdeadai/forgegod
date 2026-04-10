from __future__ import annotations

import json

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.models import PRD, Story

runner = CliRunner()


def test_plan_command_uses_ascii_output(monkeypatch, tmp_path):
    class FakePlanner:
        def __init__(self, config, router):
            self.config = config
            self.router = router

        async def decompose(self, task):
            return PRD(
                project="tarot",
                description=task,
                stories=[
                    Story(
                        id="S001",
                        title="Create app shell",
                        description="Scaffold the app from zero",
                        acceptance_criteria=["App shell exists"],
                    )
                ],
            )

    class FakeRouter:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    monkeypatch.setattr("forgegod.cli._print_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr("forgegod.planner.Planner", FakePlanner)
    monkeypatch.setattr("forgegod.router.ModelRouter", lambda config: FakeRouter())

    output = tmp_path / ".forgegod" / "prd.json"
    result = runner.invoke(app, ["plan", "Build tarot", "--output", str(output)])

    assert result.exit_code == 0, result.stdout
    assert "stories ->" in result.stdout
    assert "stories →" not in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"] == "tarot"
