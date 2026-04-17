from __future__ import annotations

import json

from typer.testing import CliRunner

from forgegod.cli import app

runner = CliRunner()


def test_bridge_chat_returns_json_and_persists_session(tmp_path, monkeypatch):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    captured: dict[str, object] = {}

    def fake_run_task_entrypoint(task: str, **kwargs):
        captured["task"] = task
        payload = {
            "story_id": "",
            "success": True,
            "exit_code": 0,
            "output": "ForgeGod handled it.",
            "files_modified": ["src/app.py"],
            "verification_commands": ["python -m pytest -q"],
            "review_verdict": "approve",
            "review_reasoning": "",
            "error": "",
            "total_usage": {},
        }
        kwargs["json_out"].write_text(json.dumps(payload), encoding="utf-8")
        return 0

    monkeypatch.setattr("forgegod.cli._run_task_entrypoint", fake_run_task_entrypoint)

    result = runner.invoke(
        app,
        [
            "bridge",
            "chat",
            "--runtime",
            "hermes",
            "--session-id",
            "thread-1",
            "--format",
            "json",
            "Add a /health endpoint",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["session_id"] == "thread-1"
    assert payload["response"] == "ForgeGod handled it."
    session_path = project_dir / "integrations" / "chat_sessions" / "thread-1.json"
    saved = json.loads(session_path.read_text(encoding="utf-8"))
    assert saved["platform"] == "hermes"
    assert saved["turns"][0]["role"] == "user"
    assert saved["turns"][1]["role"] == "assistant"
    assert "Latest user request" in captured["task"]


def test_bridge_chat_reuses_recent_context(tmp_path, monkeypatch):
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    first = {
        "story_id": "",
        "success": True,
        "exit_code": 0,
        "output": "First reply.",
        "files_modified": [],
        "verification_commands": [],
        "review_verdict": "approve",
        "review_reasoning": "",
        "error": "",
        "total_usage": {},
    }
    second = {
        "story_id": "",
        "success": True,
        "exit_code": 0,
        "output": "Second reply.",
        "files_modified": [],
        "verification_commands": [],
        "review_verdict": "approve",
        "review_reasoning": "",
        "error": "",
        "total_usage": {},
    }
    calls: list[str] = []

    def fake_run_task_entrypoint(task: str, **kwargs):
        calls.append(task)
        payload = first if len(calls) == 1 else second
        kwargs["json_out"].write_text(json.dumps(payload), encoding="utf-8")
        return 0

    monkeypatch.setattr("forgegod.cli._run_task_entrypoint", fake_run_task_entrypoint)

    runner.invoke(app, ["bridge", "chat", "--session-id", "chat-ctx", "First ask"])
    runner.invoke(app, ["bridge", "chat", "--session-id", "chat-ctx", "Follow up"])

    assert "Recent conversation context" in calls[1]
    assert "First ask" in calls[1]
    assert "First reply." in calls[1]


def test_export_integration_assets(tmp_path):
    hermes_dir = tmp_path / "hermes-skill"
    openclaw_dir = tmp_path / "openclaw-skill"
    backend_file = tmp_path / "openclaw-backend.json"

    hermes_result = runner.invoke(
        app,
        ["integrations", "export-hermes-skill", "--output", str(hermes_dir)],
    )
    openclaw_result = runner.invoke(
        app,
        ["integrations", "export-openclaw-skill", "--output", str(openclaw_dir)],
    )
    backend_result = runner.invoke(
        app,
        ["integrations", "export-openclaw-backend", "--output", str(backend_file)],
    )

    assert hermes_result.exit_code == 0, hermes_result.stdout
    assert openclaw_result.exit_code == 0, openclaw_result.stdout
    assert backend_result.exit_code == 0, backend_result.stdout
    assert (hermes_dir / "forgegod-bridge" / "SKILL.md").exists()
    assert (openclaw_dir / "forgegod-bridge" / "SKILL.md").exists()
    backend_payload = json.loads(backend_file.read_text(encoding="utf-8"))
    backend = backend_payload["agents"]["defaults"]["cliBackends"]["forgegod-cli"]
    assert backend["command"] == "forgegod"
    assert backend["sessionArg"] == "--session-id"
