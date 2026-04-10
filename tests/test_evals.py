from __future__ import annotations

import json

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.evals import HarnessEvalRunner, load_eval_manifest

runner = CliRunner()


def test_load_builtin_harness_eval_manifest():
    manifest = load_eval_manifest()

    assert manifest.name == "forgegod-harness-evals-v2"
    assert len(manifest.cases) >= 10
    assert any(case.surface == "chat" for case in manifest.cases)
    assert any(case.surface == "loop" for case in manifest.cases)
    assert any(case.terse for case in manifest.cases)
    assert any(case.sandbox_mode == "strict" for case in manifest.cases)


def test_harness_eval_runner_executes_builtin_cases(tmp_path):
    config = ForgeGodConfig()
    eval_runner = HarnessEvalRunner(config)
    manifest = load_eval_manifest()

    report = eval_runner.run_manifest(
        manifest,
        output_path=tmp_path / "report.json",
        traces_dir=tmp_path / "traces",
    )

    assert report.total_cases == len(manifest.cases)
    assert report.passed_cases == report.total_cases
    assert report.score == 1.0
    assert (tmp_path / "report.json").exists()
    for case in manifest.cases:
        assert (tmp_path / "traces" / f"{case.id}.requests.json").exists()


def test_evals_cli_lists_cases():
    result = runner.invoke(app, ["evals", "--list"])

    assert result.exit_code == 0
    assert "Harness eval cases" in result.stdout
    assert "chat_natural_language_roundtrip" in result.stdout


def test_evals_cli_runs_selected_case(tmp_path):
    result = runner.invoke(
        app,
        [
            "evals",
            "--case",
            "chat_natural_language_roundtrip",
            "--output",
            str(tmp_path / "report.json"),
            "--traces-dir",
            str(tmp_path / "traces"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Harness evals complete" in result.stdout
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["total_cases"] == 1
    assert payload["passed_cases"] == 1


def test_evals_cli_runs_parallel_worktree_case(tmp_path):
    result = runner.invoke(
        app,
        [
            "evals",
            "--case",
            "loop_parallel_worktree_success",
            "--output",
            str(tmp_path / "report.json"),
            "--traces-dir",
            str(tmp_path / "traces"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["total_cases"] == 1
    assert payload["passed_cases"] == 1
    assert payload["results"][0]["id"] == "loop_parallel_worktree_success"
