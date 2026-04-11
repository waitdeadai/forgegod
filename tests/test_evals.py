from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.evals import (
    EvalLiveComparisonReport,
    EvalLiveComparisonRow,
    EvalLiveMatrixReport,
    EvalLiveMatrixRow,
    EvalLiveProbeResult,
    HarnessEvalRunner,
    load_eval_manifest,
)

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
    assert "openai-live" in result.stdout
    assert "openai-live-compare" in result.stdout


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


def test_harness_eval_runner_runs_openai_live_surface_matrix(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    eval_runner = HarnessEvalRunner(config)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        "forgegod.evals.codex_login_status_sync",
        lambda: (True, "Logged in using ChatGPT"),
    )
    monkeypatch.setattr(
        "forgegod.evals.codex_automation_status",
        lambda: (True, "Supported"),
    )

    def fake_run_live(self, models, *, profile, requested_surface, effective_surface):
        return (
            [
                EvalLiveProbeResult(
                    name="coder_exact_marker",
                    role="coder",
                    expected="FORGEGOD_CODER_OK",
                    observed="FORGEGOD_CODER_OK",
                    provider=models["coder"].split(":", 1)[0],
                    model=models["coder"].split(":", 1)[1],
                    passed=True,
                    detail=f"surface={effective_surface}",
                    usage={"input_tokens": 10, "output_tokens": 2},
                ),
                EvalLiveProbeResult(
                    name="reviewer_exact_marker",
                    role="reviewer",
                    expected="FORGEGOD_REVIEWER_OK",
                    observed="FORGEGOD_REVIEWER_OK",
                    provider=models["reviewer"].split(":", 1)[0],
                    model=models["reviewer"].split(":", 1)[1],
                    passed=True,
                    detail=f"surface={effective_surface}",
                    usage={"input_tokens": 10, "output_tokens": 2},
                ),
            ],
            0.001,
            2,
        )

    monkeypatch.setattr(HarnessEvalRunner, "_run_live_openai_probes", fake_run_live)

    report = eval_runner.run_openai_live_surface_matrix(
        output_path=tmp_path / "live-matrix.json"
    )

    assert report.matrix_name == "openai-live-v1"
    assert report.total_rows == 8
    assert report.passed_rows == 8
    assert report.failed_rows == 0
    assert report.skipped_rows == 0
    assert report.score == 1.0
    assert (tmp_path / "live-matrix.json").exists()
    hybrid = next(row for row in report.rows if row.id == "adversarial_api_codex")
    assert hybrid.requested_openai_surface == "api+codex"
    assert hybrid.status == "passed"
    assert hybrid.probe_results[1].provider == "openai-codex"


def test_harness_eval_runner_skips_live_openai_rows_when_surfaces_missing(monkeypatch):
    config = ForgeGodConfig()
    eval_runner = HarnessEvalRunner(config)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "forgegod.evals.codex_login_status_sync",
        lambda: (False, "Not logged in"),
    )
    monkeypatch.setattr(
        "forgegod.evals.codex_automation_status",
        lambda: (False, "Use WSL for best Windows experience"),
    )

    report = eval_runner.run_openai_live_surface_matrix()

    assert report.total_rows == 8
    assert report.passed_rows == 0
    assert report.failed_rows == 0
    assert report.skipped_rows == 8
    assert all(row.status == "skipped" for row in report.rows)


def test_evals_cli_runs_openai_live_surface_matrix(tmp_path, monkeypatch):
    fake_report = EvalLiveMatrixReport(
        timestamp="2026-04-11T00:00:00+00:00",
        forgegod_version="0.1.0",
        matrix_name="openai-live-v1",
        detected_providers=["openai"],
        codex_login_ready=False,
        codex_automation_supported=False,
        total_rows=2,
        passed_rows=1,
        failed_rows=0,
        skipped_rows=1,
        score=1.0,
        rows=[
            EvalLiveMatrixRow(
                id="single_model_api_only",
                profile="single-model",
                preferred_provider="openai",
                requested_openai_surface="api-only",
                effective_openai_surface="api-only",
                detected_providers=["openai"],
                requested_surface_ready=True,
                status="passed",
                detail="2/2 live probes passed.",
                models={"coder": "openai:gpt-5.4-mini", "reviewer": "openai:gpt-5.4-mini"},
                score=1.0,
                total_cost_usd=0.0012,
                call_count=2,
                probe_results=[
                    EvalLiveProbeResult(
                        name="coder_exact_marker",
                        role="coder",
                        expected="FORGEGOD_CODER_OK",
                        observed="FORGEGOD_CODER_OK",
                        provider="openai",
                        model="gpt-5.4-mini",
                        passed=True,
                    )
                ],
            ),
            EvalLiveMatrixRow(
                id="adversarial_codex_only",
                profile="adversarial",
                preferred_provider="openai",
                requested_openai_surface="codex-only",
                effective_openai_surface="api-only",
                detected_providers=["openai"],
                requested_surface_ready=False,
                status="skipped",
                detail="Skipped: Codex subscription is not logged in.",
                models={"coder": "openai:gpt-5.4-mini", "reviewer": "openai:gpt-5.4-mini"},
            ),
        ],
    )

    monkeypatch.setattr(
        "forgegod.evals.HarnessEvalRunner.run_openai_live_surface_matrix",
        lambda self, output_path: fake_report,
    )

    result = runner.invoke(
        app,
        [
            "evals",
            "--matrix",
            "openai-live",
            "--output",
            str(tmp_path / "matrix.json"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    normalized = _normalize_cli_text(result.stdout)
    assert "Live OpenAI eval matrix complete" in normalized
    assert "Live probe summary" in normalized


def test_harness_eval_runner_builds_openai_live_comparison(monkeypatch, tmp_path):
    config = ForgeGodConfig()
    eval_runner = HarnessEvalRunner(config)

    fake_live_report = EvalLiveMatrixReport(
        timestamp="2026-04-11T00:00:00+00:00",
        forgegod_version="0.1.0",
        matrix_name="openai-live-v1",
        detected_providers=["openai", "openai-codex"],
        codex_login_ready=True,
        codex_automation_supported=True,
        total_rows=4,
        passed_rows=2,
        failed_rows=1,
        skipped_rows=1,
        score=0.875,
        rows=[
            EvalLiveMatrixRow(
                id="adversarial_api_codex",
                profile="adversarial",
                preferred_provider="openai",
                requested_openai_surface="api+codex",
                effective_openai_surface="api+codex",
                detected_providers=["openai", "openai-codex"],
                requested_surface_ready=True,
                status="passed",
                detail="2/2 live probes passed.",
                score=1.0,
                total_cost_usd=0.0018,
                call_count=2,
                probe_results=[
                    EvalLiveProbeResult(
                        name="coder",
                        role="coder",
                        expected="x",
                        observed="x",
                        passed=True,
                    ),
                    EvalLiveProbeResult(
                        name="reviewer",
                        role="reviewer",
                        expected="y",
                        observed="y",
                        passed=True,
                    ),
                ],
            ),
            EvalLiveMatrixRow(
                id="single_model_api_only",
                profile="single-model",
                preferred_provider="openai",
                requested_openai_surface="api-only",
                effective_openai_surface="api-only",
                detected_providers=["openai", "openai-codex"],
                requested_surface_ready=True,
                status="passed",
                detail="2/2 live probes passed.",
                score=1.0,
                total_cost_usd=0.0012,
                call_count=2,
                probe_results=[
                    EvalLiveProbeResult(
                        name="coder",
                        role="coder",
                        expected="x",
                        observed="x",
                        passed=True,
                    ),
                    EvalLiveProbeResult(
                        name="reviewer",
                        role="reviewer",
                        expected="y",
                        observed="y",
                        passed=True,
                    ),
                ],
            ),
            EvalLiveMatrixRow(
                id="adversarial_codex_only",
                profile="adversarial",
                preferred_provider="openai",
                requested_openai_surface="codex-only",
                effective_openai_surface="codex-only",
                detected_providers=["openai", "openai-codex"],
                requested_surface_ready=True,
                status="failed",
                detail="1/2 live probes passed.",
                score=0.5,
                total_cost_usd=0.0,
                call_count=2,
                probe_results=[
                    EvalLiveProbeResult(
                        name="coder",
                        role="coder",
                        expected="x",
                        observed="x",
                        passed=True,
                    ),
                    EvalLiveProbeResult(
                        name="reviewer",
                        role="reviewer",
                        expected="y",
                        observed="z",
                        passed=False,
                    ),
                ],
            ),
            EvalLiveMatrixRow(
                id="single_model_auto",
                profile="single-model",
                preferred_provider="openai",
                requested_openai_surface="auto",
                effective_openai_surface="api+codex",
                detected_providers=["openai", "openai-codex"],
                requested_surface_ready=False,
                status="skipped",
                detail="Skipped.",
            ),
        ],
    )

    monkeypatch.setattr(
        HarnessEvalRunner,
        "run_openai_live_surface_matrix",
        lambda self: fake_live_report,
    )

    report = eval_runner.run_openai_live_surface_comparison(
        output_path=tmp_path / "live-compare.json"
    )

    assert report.matrix_name == "openai-live-compare-v1"
    assert report.runnable_rows == 3
    assert report.passed_rows == 2
    assert report.failed_rows == 1
    assert report.skipped_rows == 1
    assert report.recommended_row_id == "adversarial_api_codex"
    assert "split builder/reviewer roles" in report.recommendation_reason
    assert (tmp_path / "live-compare.json").exists()
    assert report.rows[0].rank == 1
    assert report.rows[1].score_delta_vs_recommended == 0.0
    assert report.rows[1].cost_delta_vs_recommended < 0


def test_harness_eval_runner_handles_no_runnable_live_comparison(monkeypatch):
    config = ForgeGodConfig()
    eval_runner = HarnessEvalRunner(config)

    fake_live_report = EvalLiveMatrixReport(
        timestamp="2026-04-11T00:00:00+00:00",
        forgegod_version="0.1.0",
        matrix_name="openai-live-v1",
        detected_providers=[],
        codex_login_ready=False,
        codex_automation_supported=False,
        total_rows=2,
        passed_rows=0,
        failed_rows=0,
        skipped_rows=2,
        score=0.0,
        rows=[
            EvalLiveMatrixRow(
                id="adversarial_auto",
                profile="adversarial",
                preferred_provider="openai",
                requested_openai_surface="auto",
                effective_openai_surface="auto",
                detected_providers=[],
                requested_surface_ready=False,
                status="skipped",
                detail="Skipped.",
            )
        ],
    )
    monkeypatch.setattr(
        HarnessEvalRunner,
        "run_openai_live_surface_matrix",
        lambda self: fake_live_report,
    )

    report = eval_runner.run_openai_live_surface_comparison()

    assert report.runnable_rows == 0
    assert report.recommended_row_id == ""
    assert "No runnable live OpenAI rows were available" in report.recommendation_reason


def test_evals_cli_runs_openai_live_compare_matrix(tmp_path, monkeypatch):
    fake_report = EvalLiveComparisonReport(
        timestamp="2026-04-11T00:00:00+00:00",
        forgegod_version="0.1.0",
        matrix_name="openai-live-compare-v1",
        source_matrix_name="openai-live-v1",
        detected_providers=["openai", "openai-codex"],
        total_rows=8,
        runnable_rows=2,
        passed_rows=2,
        failed_rows=0,
        skipped_rows=6,
        recommended_row_id="adversarial_api_codex",
        recommendation_reason=(
            "highest live score (1.000); prefers split builder/reviewer roles on "
            "ties; keeps API builder roles split from Codex review"
        ),
        rows=[
            EvalLiveComparisonRow(
                rank=1,
                id="adversarial_api_codex",
                profile="adversarial",
                requested_openai_surface="api+codex",
                effective_openai_surface="api+codex",
                status="passed",
                score=1.0,
                total_cost_usd=0.0018,
                call_count=2,
                passed_probes=2,
                total_probes=2,
            )
        ],
    )

    monkeypatch.setattr(
        "forgegod.evals.HarnessEvalRunner.run_openai_live_surface_comparison",
        lambda self, output_path: fake_report,
    )

    result = runner.invoke(
        app,
        [
            "evals",
            "--matrix",
            "openai-live-compare",
            "--output",
            str(tmp_path / "compare.json"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    normalized = _normalize_cli_text(result.stdout)
    assert "Live OpenAI comparison complete" in normalized
    assert "Recommended harness row: adversarial_api_codex" in normalized
