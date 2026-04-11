from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.evals import HarnessEvalRunner, load_eval_manifest

runner = CliRunner()


def _normalize_cli_text(value: str) -> str:
    without_ansi = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value)
    return " ".join(without_ansi.replace("\r", " ").replace("\n", " ").split())


def test_load_builtin_harness_eval_manifest():
    manifest = load_eval_manifest()

    assert manifest.name == "forgegod-harness-evals-v2"
    assert len(manifest.cases) >= 10
    assert any(case.surface == "chat" for case in manifest.cases)
    assert any(case.surface == "loop" for case in manifest.cases)
    assert any(case.terse for case in manifest.cases)
    assert any(case.sandbox_mode == "strict" for case in manifest.cases)
    assert any(case.dimensions for case in manifest.cases)


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
    assert report.dimension_scores["safety"] == 1.0
    assert report.dimension_scores["ux"] == 1.0
    assert report.trace_grade_scores["transport_noise_absent"] == 1.0
    assert report.trace_grade_scores["loop_outcome_summary"] == 1.0
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
    normalized = _normalize_cli_text(result.stdout)
    assert "Harness evals complete" in normalized
    assert "Trace graders:" in normalized
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["total_cases"] == 1
    assert payload["passed_cases"] == 1
    assert payload["trace_grade_scores"]["transport_noise_absent"] == 1.0


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


def test_evals_cli_lists_matrices():
    result = runner.invoke(app, ["evals", "--list-matrices"])

    assert result.exit_code == 0
    assert "Harness eval matrices" in result.stdout
    assert "openai-surfaces" in result.stdout


def test_harness_eval_runner_runs_openai_surface_matrix(tmp_path):
    config = ForgeGodConfig()
    eval_runner = HarnessEvalRunner(config)
    manifest = load_eval_manifest()

    report = eval_runner.run_openai_surface_matrix(
        manifest,
        selected_tags={"chat"},
        output_path=tmp_path / "matrix.json",
        traces_dir=tmp_path / "traces",
    )

    assert report.total_rows == 8
    assert report.passed_rows == 8
    assert report.score == 1.0
    assert (tmp_path / "matrix.json").exists()
    row_ids = {row.id for row in report.rows}
    assert "adversarial_api_codex" in row_ids
    assert "single_model_codex_only" in row_ids
    codex_only = next(row for row in report.rows if row.id == "single_model_codex_only")
    assert codex_only.effective_openai_surface == "codex-only"
    assert codex_only.models["planner"].startswith("openai-codex:")
    assert codex_only.trace_grade_scores["transport_noise_absent"] == 1.0
    api_only = next(row for row in report.rows if row.id == "adversarial_api_only")
    assert api_only.effective_openai_surface == "api-only"
    assert api_only.models["reviewer"].startswith("openai:")


def test_evals_cli_runs_openai_surface_matrix(tmp_path):
    result = runner.invoke(
        app,
        [
            "evals",
            "--matrix",
            "openai-surfaces",
            "--tag",
            "chat",
            "--output",
            str(tmp_path / "matrix.json"),
            "--traces-dir",
            str(tmp_path / "traces"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    normalized = _normalize_cli_text(result.stdout)
    assert "Harness eval matrix complete" in normalized
    assert "Trace grader summary" in normalized
    payload = json.loads((tmp_path / "matrix.json").read_text(encoding="utf-8"))
    assert payload["matrix_name"] == "openai-surfaces-v1"
    assert payload["total_rows"] == 8
    assert payload["passed_rows"] == 8
