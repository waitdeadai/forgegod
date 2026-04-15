"""Harness eval runner for deterministic ForgeGod behavior checks.

This is intentionally separate from `forgegod benchmark`:
- `benchmark` compares coding ability on scaffold tasks
- `evals` checks harness behavior, UX, permissions, and completion discipline
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field
from rich.console import Console
from typer.testing import CliRunner

from forgegod import __version__
from forgegod.config import (
    ForgeGodConfig,
    ModelsConfig,
    recommend_model_defaults,
    resolve_openai_surface,
)
from forgegod.native_auth import codex_automation_status, codex_login_status_sync
from forgegod.testing.mock_openai_service import SCENARIOS, start_mock_openai_server

console = Console()


class EvalExpectation(BaseModel):
    """Assertions that define success for a harness eval case."""

    exit_code: int | None = None
    request_count: int | None = None
    output_contains: list[str] = Field(default_factory=list)
    output_not_contains: list[str] = Field(default_factory=list)
    files_exist: list[str] = Field(default_factory=list)
    files_absent: list[str] = Field(default_factory=list)
    file_contains: dict[str, str] = Field(default_factory=dict)
    directories_empty: list[str] = Field(default_factory=list)
    first_request_tools_include: list[str] = Field(default_factory=list)
    prd_story_status: str | None = None
    prd_story_files_touched: list[str] = Field(default_factory=list)
    prd_story_error_contains: list[str] = Field(default_factory=list)


class EvalCase(BaseModel):
    """One deterministic harness eval scenario."""

    id: str
    description: str
    scenario: str
    surface: str = "run"  # run | chat | loop
    setup: str = "none"  # none | hello | git | git_src
    permission_mode: str = "workspace-write"
    approval_mode: str = "deny"
    sandbox_mode: str = "standard"
    sandbox_backend: str = "none"  # none | success | unavailable
    review: bool = False
    terse: bool = False
    loop_workers: int = 1
    loop_max_iterations: int = 2
    story_id: str = "T001"
    story_title: str = "Harness eval story"
    story_description: str = "Execute the deterministic harness eval story."
    story_acceptance_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    stdin_input: str = ""
    chat_inputs: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    harness_profile: str = "adversarial"
    preferred_provider: str = "auto"
    openai_surface: str = "auto"
    detected_providers: list[str] = Field(default_factory=lambda: ["openai"])
    codex_automation_supported: bool = False
    expectations: EvalExpectation = Field(default_factory=EvalExpectation)


class EvalManifest(BaseModel):
    """Collection of deterministic eval cases."""

    name: str
    description: str = ""
    cases: list[EvalCase] = Field(default_factory=list)


class EvalCheckResult(BaseModel):
    """One graded assertion."""

    name: str
    passed: bool
    detail: str = ""


class EvalCaseResult(BaseModel):
    """Result of one eval case."""

    id: str
    description: str
    passed: bool
    score: float = 0.0
    exit_code: int = 1
    request_count: int = 0
    output_preview: str = ""
    checks: list[EvalCheckResult] = Field(default_factory=list)
    trace_grades: list["EvalTraceGrade"] = Field(default_factory=list)
    trace_path: str = ""
    error: str = ""


class EvalReport(BaseModel):
    """Full eval report."""

    timestamp: str
    forgegod_version: str
    manifest_name: str
    manifest_path: str = ""
    total_cases: int = 0
    passed_cases: int = 0
    score: float = 0.0
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    trace_grade_scores: dict[str, float] = Field(default_factory=dict)
    results: list[EvalCaseResult] = Field(default_factory=list)


class EvalTraceGrade(BaseModel):
    """One local trace grader result."""

    name: str
    score: float = 0.0
    detail: str = ""


class EvalMatrixRow(BaseModel):
    """One profile/surface row in a harness eval matrix."""

    id: str
    profile: str
    preferred_provider: str
    requested_openai_surface: str
    effective_openai_surface: str
    detected_providers: list[str] = Field(default_factory=list)
    codex_automation_supported: bool = False
    models: dict[str, str] = Field(default_factory=dict)
    passed_cases: int = 0
    total_cases: int = 0
    score: float = 0.0
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    trace_grade_scores: dict[str, float] = Field(default_factory=dict)
    passed: bool = False
    report_path: str = ""
    traces_dir: str = ""


class EvalMatrixReport(BaseModel):
    """Multi-row harness eval matrix report."""

    timestamp: str
    forgegod_version: str
    matrix_name: str
    total_rows: int = 0
    passed_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    score: float = 0.0
    rows: list[EvalMatrixRow] = Field(default_factory=list)


class EvalLiveProbeResult(BaseModel):
    """One live provider probe inside a matrix row."""

    name: str
    role: str
    expected: str
    observed: str = ""
    provider: str = ""
    model: str = ""
    passed: bool = False
    detail: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


class EvalLiveMatrixRow(BaseModel):
    """One live OpenAI API/Codex probe row."""

    id: str
    profile: str
    preferred_provider: str
    requested_openai_surface: str
    effective_openai_surface: str
    detected_providers: list[str] = Field(default_factory=list)
    codex_login_ready: bool = False
    codex_automation_supported: bool = False
    requested_surface_ready: bool = False
    status: str = "skipped"  # passed | failed | skipped
    detail: str = ""
    models: dict[str, str] = Field(default_factory=dict)
    score: float = 0.0
    total_cost_usd: float = 0.0
    call_count: int = 0
    probe_results: list[EvalLiveProbeResult] = Field(default_factory=list)


class EvalLiveMatrixReport(BaseModel):
    """Live OpenAI surface probe matrix report."""

    timestamp: str
    forgegod_version: str
    matrix_name: str
    detected_providers: list[str] = Field(default_factory=list)
    codex_login_ready: bool = False
    codex_automation_supported: bool = False
    total_rows: int = 0
    passed_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    score: float = 0.0
    rows: list[EvalLiveMatrixRow] = Field(default_factory=list)


class EvalLiveComparisonRow(BaseModel):
    """One ranked runnable row from the live OpenAI comparison matrix."""

    rank: int = 0
    id: str
    profile: str
    requested_openai_surface: str
    effective_openai_surface: str
    status: str = "skipped"
    score: float = 0.0
    total_cost_usd: float = 0.0
    call_count: int = 0
    passed_probes: int = 0
    total_probes: int = 0
    score_delta_vs_recommended: float = 0.0
    cost_delta_vs_recommended: float = 0.0
    call_delta_vs_recommended: int = 0
    detail: str = ""


class EvalLiveComparisonReport(BaseModel):
    """Comparison report built from runnable live OpenAI rows."""

    timestamp: str
    forgegod_version: str
    matrix_name: str
    source_matrix_name: str
    detected_providers: list[str] = Field(default_factory=list)
    total_rows: int = 0
    runnable_rows: int = 0
    passed_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    recommended_row_id: str = ""
    recommendation_reason: str = ""
    rows: list[EvalLiveComparisonRow] = Field(default_factory=list)


class LiveSurfaceUnavailableError(RuntimeError):
    """Raised when a live provider surface is present but temporarily unavailable."""


_BUILTIN_MANIFEST = {
    "name": "forgegod-harness-evals-v2",
    "description": (
        "Deterministic harness evals for chat UX, completion gates, "
        "permission handling, loop/worktree behavior, and strict sandbox paths."
    ),
    "cases": [
        {
            "id": "chat_natural_language_roundtrip",
            "description": "Root `forgegod` chat handles a natural-language file question.",
            "scenario": "cli_read_file_roundtrip",
            "surface": "chat",
            "setup": "hello",
            "permission_mode": "read-only",
            "tags": ["chat", "ux", "natural-language"],
            "dimensions": ["ux", "verification"],
            "expectations": {
                "exit_code": 0,
                "request_count": 2,
                "output_contains": [
                    "Talk to ForgeGod in natural language",
                    "The file says hello forgegod.",
                    "Session closed.",
                ],
                "file_contains": {"hello.txt": "hello forgegod"},
                "first_request_tools_include": ["read_file", "repo_map", "git_status"],
            },
        },
        {
            "id": "chat_terse_roundtrip",
            "description": "Root `forgegod --terse` keeps chat UX intact.",
            "scenario": "cli_read_file_roundtrip",
            "surface": "chat",
            "setup": "hello",
            "permission_mode": "read-only",
            "terse": True,
            "tags": ["chat", "terse", "ux"],
            "dimensions": ["ux"],
            "expectations": {
                "exit_code": 0,
                "request_count": 2,
                "output_contains": [
                    "Caveman mode enabled",
                    "The file says hello forgegod.",
                ],
                "file_contains": {"hello.txt": "hello forgegod"},
                "first_request_tools_include": ["read_file", "repo_map", "git_status"],
            },
        },
        {
            "id": "run_completion_gate_roundtrip",
            "description": "Run mode writes code, verifies, and completes (bash waives git_diff).",
            "scenario": "cli_completion_gate_roundtrip",
            "surface": "run",
            "setup": "git_src",
            "permission_mode": "workspace-write",
            "tags": ["run", "completion-gate", "verification"],
            "dimensions": ["workflow", "verification"],
            "expectations": {
                "exit_code": 0,
                "request_count": 3,
                "output_contains": ["Files modified: src/app.py"],
                "files_exist": ["src/app.py"],
                "file_contains": {"src/app.py": "print('forgegod')"},
            },
        },
        {
            "id": "run_prompt_approval_allowed",
            "description": "Run mode can prompt and continue after explicit approval.",
            "scenario": "cli_write_file_allowed",
            "surface": "run",
            "setup": "git",
            "permission_mode": "read-only",
            "approval_mode": "prompt",
            "stdin_input": "y\n",
            "tags": ["run", "approval", "permissions"],
            "dimensions": ["safety", "workflow"],
            "expectations": {
                "exit_code": 0,
                "request_count": 3,
                "output_contains": ["Approval required", "Created notes.txt successfully."],
                "files_exist": ["notes.txt"],
                "file_contains": {"notes.txt": "hello forgegod"},
            },
        },
        {
            "id": "run_permission_denied",
            "description": "Run mode surfaces denied writes cleanly in read-only mode.",
            "scenario": "cli_write_file_denied",
            "surface": "run",
            "setup": "none",
            "permission_mode": "read-only",
            "tags": ["run", "permissions", "safety"],
            "dimensions": ["safety"],
            "expectations": {
                "exit_code": 1,
                "request_count": 1,
                "output_contains": ["ForgeGod blocked tool 'write_file'"],
                "files_absent": ["blocked.txt"],
            },
        },
        {
            "id": "loop_story_success",
            "description": "Loop mode completes one PRD story and records the result.",
            "scenario": "cli_loop_story_success",
            "surface": "loop",
            "setup": "git_src",
            "permission_mode": "workspace-write",
            "loop_workers": 1,
            "loop_max_iterations": 2,
            "story_id": "T001",
            "story_title": "Create the app entrypoint",
            "story_description": "Implement src/app.py for the loop parity harness.",
            "tags": ["loop", "prd", "verification"],
            "dimensions": ["workflow", "verification"],
            "expectations": {
                "exit_code": 0,
                "request_count": 3,
                "output_contains": ["Completed: 1 | Failed: 0"],
                "files_exist": ["src/app.py"],
                "file_contains": {"src/app.py": "print('forgegod loop')"},
                "prd_story_status": "done",
                "prd_story_files_touched": ["src/app.py"],
            },
        },
        {
            "id": "loop_story_blocked",
            "description": "Loop mode marks a story blocked when permissions deny a write.",
            "scenario": "cli_loop_story_denied",
            "surface": "loop",
            "setup": "git",
            "permission_mode": "read-only",
            "loop_workers": 1,
            "loop_max_iterations": 1,
            "story_id": "T002",
            "story_title": "Blocked write story",
            "story_description": "Attempt a forbidden write from the loop parity harness.",
            "tags": ["loop", "permissions", "safety"],
            "dimensions": ["safety", "workflow"],
            "expectations": {
                "exit_code": 0,
                "request_count": 1,
                "output_contains": ["Completed: 0 | Failed: 1"],
                "files_absent": ["blocked.txt"],
                "prd_story_status": "blocked",
                "prd_story_error_contains": ["ForgeGod blocked tool 'write_file'"],
            },
        },
        {
            "id": "loop_parallel_worktree_success",
            "description": "Parallel loop mode completes through the isolated worktree path.",
            "scenario": "cli_loop_story_success",
            "surface": "loop",
            "setup": "git_src",
            "permission_mode": "workspace-write",
            "loop_workers": 2,
            "loop_max_iterations": 2,
            "story_id": "T003",
            "story_title": "Create the isolated app entrypoint",
            "story_description": "Implement src/app.py through the parallel worktree path.",
            "tags": ["loop", "worktree", "parallel"],
            "dimensions": ["workflow", "verification"],
            "expectations": {
                "exit_code": 0,
                "request_count": 3,
                "output_contains": ["Completed: 1 | Failed: 0"],
                "files_exist": ["src/app.py"],
                "file_contains": {"src/app.py": "print('forgegod loop')"},
                "directories_empty": [".forgegod/worktrees"],
                "prd_story_status": "done",
                "prd_story_files_touched": ["src/app.py"],
            },
        },
        {
            "id": "strict_sandbox_interface_roundtrip",
            "description": (
                "Run mode exercises the strict sandbox interface through a "
                "deterministic backend stub."
            ),
            "scenario": "cli_strict_bash_roundtrip",
            "surface": "run",
            "setup": "none",
            "permission_mode": "read-only",
            "sandbox_mode": "strict",
            "sandbox_backend": "success",
            "tags": ["run", "strict", "sandbox"],
            "dimensions": ["safety", "workflow"],
            "expectations": {
                "exit_code": 0,
                "request_count": 2,
                "output_contains": ["Strict sandbox reported Python 3.13.5."],
            },
        },
        {
            "id": "strict_sandbox_backend_blocked",
            "description": "Run mode surfaces strict sandbox backend failures cleanly.",
            "scenario": "cli_strict_backend_blocked",
            "surface": "run",
            "setup": "none",
            "permission_mode": "read-only",
            "sandbox_mode": "strict",
            "sandbox_backend": "unavailable",
            "tags": ["run", "strict", "safety"],
            "dimensions": ["safety"],
            "expectations": {
                "exit_code": 0,
                "request_count": 2,
                "output_contains": ["backend is unavailable"],
            },
        },
    ],
}


def load_eval_manifest(path: Path | None = None) -> EvalManifest:
    """Load a harness eval manifest from JSON, or fall back to the built-in set."""
    if path is None:
        return EvalManifest.model_validate(_BUILTIN_MANIFEST)
    data = json.loads(path.read_text(encoding="utf-8"))
    return EvalManifest.model_validate(data)


class HarnessEvalRunner:
    """Run deterministic harness evals against ForgeGod CLI surfaces."""

    def __init__(self, config: ForgeGodConfig):
        self.config = config.model_copy(deep=True)
        self.runner = CliRunner()

    def run_manifest(
        self,
        manifest: EvalManifest,
        *,
        selected_case_ids: set[str] | None = None,
        selected_tags: set[str] | None = None,
        output_path: Path | None = None,
        traces_dir: Path | None = None,
    ) -> EvalReport:
        """Run all matching cases and return a report."""
        cases = self._select_cases(
            manifest.cases,
            selected_case_ids=selected_case_ids,
            selected_tags=selected_tags,
        )
        if not cases:
            raise ValueError("No eval cases matched the requested filters.")

        results: list[EvalCaseResult] = []
        if traces_dir is not None:
            traces_dir.mkdir(parents=True, exist_ok=True)

        console.print(
            f"[bold cyan]Running harness evals[/bold cyan] "
            f"({len(cases)} cases from {manifest.name})"
        )
        for idx, case in enumerate(cases, start=1):
            console.print(f"  [{idx}/{len(cases)}] {case.id} - {case.description}")
            result = self.run_case(case, traces_dir=traces_dir)
            status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
            console.print(
                f"    {status} | score={result.score:.2f} | "
                f"requests={result.request_count}"
            )
            results.append(result)

        passed_cases = sum(1 for result in results if result.passed)
        score = round(sum(result.score for result in results) / len(results), 3)
        report = EvalReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            forgegod_version=__version__,
            manifest_name=manifest.name,
            total_cases=len(results),
            passed_cases=passed_cases,
            score=score,
            dimension_scores=self._build_dimension_scores(cases, results),
            trace_grade_scores=self._build_trace_grade_scores(results),
            results=results,
        )
        if output_path is not None:
            report.manifest_path = str(output_path)
            self.save_report(report, output_path)
        return report

    def run_openai_surface_matrix(
        self,
        manifest: EvalManifest,
        *,
        selected_case_ids: set[str] | None = None,
        selected_tags: set[str] | None = None,
        output_path: Path | None = None,
        traces_dir: Path | None = None,
    ) -> EvalMatrixReport:
        """Run the harness eval corpus across OpenAI profile/surface rows."""
        rows: list[EvalMatrixRow] = []
        if traces_dir is not None:
            traces_dir.mkdir(parents=True, exist_ok=True)

        console.print("[bold cyan]Running OpenAI surface eval matrix[/bold cyan]")
        for row_spec in _OPENAI_SURFACE_MATRIX:
            row_cases = [
                case.model_copy(
                    update={
                        "harness_profile": row_spec["profile"],
                        "preferred_provider": row_spec["preferred_provider"],
                        "openai_surface": row_spec["openai_surface"],
                        "detected_providers": row_spec["detected_providers"],
                        "codex_automation_supported": row_spec["codex_automation_supported"],
                    }
                )
                for case in manifest.cases
            ]
            row_manifest = EvalManifest(
                name=f"{manifest.name}:{row_spec['id']}",
                description=manifest.description,
                cases=row_cases,
            )
            row_report_path = (
                output_path.parent / f"{row_spec['id']}.report.json"
                if output_path is not None
                else None
            )
            row_traces_dir = traces_dir / row_spec["id"] if traces_dir is not None else None
            report = self.run_manifest(
                row_manifest,
                selected_case_ids=selected_case_ids,
                selected_tags=selected_tags,
                output_path=row_report_path,
                traces_dir=row_traces_dir,
            )
            effective_surface = resolve_openai_surface(
                row_spec["openai_surface"],
                row_spec["detected_providers"],
                codex_automation_supported=row_spec["codex_automation_supported"],
            )
            models = recommend_model_defaults(
                row_spec["detected_providers"],
                ollama_available=False,
                codex_automation_supported=row_spec["codex_automation_supported"],
                profile=row_spec["profile"],
                preferred_provider=row_spec["preferred_provider"],
                openai_surface=row_spec["openai_surface"],
            ).model_dump()
            rows.append(
                EvalMatrixRow(
                    id=row_spec["id"],
                    profile=row_spec["profile"],
                    preferred_provider=row_spec["preferred_provider"],
                    requested_openai_surface=row_spec["openai_surface"],
                    effective_openai_surface=effective_surface,
                    detected_providers=list(row_spec["detected_providers"]),
                    codex_automation_supported=row_spec["codex_automation_supported"],
                    models=models,
                    passed_cases=report.passed_cases,
                    total_cases=report.total_cases,
                    score=report.score,
                    dimension_scores=report.dimension_scores,
                    trace_grade_scores=report.trace_grade_scores,
                    passed=report.passed_cases == report.total_cases,
                    report_path=str(row_report_path) if row_report_path else "",
                    traces_dir=str(row_traces_dir) if row_traces_dir else "",
                )
            )

        matrix_report = EvalMatrixReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            forgegod_version=__version__,
            matrix_name="openai-surfaces-v1",
            total_rows=len(rows),
            passed_rows=sum(1 for row in rows if row.passed),
            failed_rows=sum(1 for row in rows if not row.passed),
            skipped_rows=0,
            score=round(sum(row.score for row in rows) / len(rows), 3) if rows else 0.0,
            rows=rows,
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(matrix_report.model_dump_json(indent=2), encoding="utf-8")
        return matrix_report

    def run_openai_live_surface_matrix(
        self,
        *,
        output_path: Path | None = None,
    ) -> EvalLiveMatrixReport:
        """Run small live probes against actual OpenAI API/Codex auth surfaces."""
        detected_providers, codex_login_ready, codex_supported = (
            self._detect_live_openai_providers()
        )
        rows: list[EvalLiveMatrixRow] = []

        console.print("[bold cyan]Running live OpenAI surface probe matrix[/bold cyan]")
        for row_spec in _OPENAI_SURFACE_MATRIX:
            requested_surface = row_spec["openai_surface"]
            effective_surface = resolve_openai_surface(
                requested_surface,
                detected_providers,
                codex_automation_supported=codex_supported,
            )
            models = recommend_model_defaults(
                detected_providers,
                ollama_available=False,
                codex_automation_supported=codex_supported,
                profile=row_spec["profile"],
                preferred_provider=row_spec["preferred_provider"],
                openai_surface=requested_surface,
            ).model_dump()

            row = EvalLiveMatrixRow(
                id=row_spec["id"],
                profile=row_spec["profile"],
                preferred_provider=row_spec["preferred_provider"],
                requested_openai_surface=requested_surface,
                effective_openai_surface=effective_surface,
                detected_providers=list(detected_providers),
                codex_login_ready=codex_login_ready,
                codex_automation_supported=codex_supported,
                requested_surface_ready=self._is_requested_openai_surface_ready(
                    requested_surface,
                    detected_providers,
                    codex_login_ready=codex_login_ready,
                    codex_automation_supported=codex_supported,
                ),
                models=models,
            )

            if not row.requested_surface_ready:
                row.status = "skipped"
                row.detail = self._build_live_surface_skip_detail(
                    requested_surface,
                    effective_surface,
                    detected_providers,
                    codex_login_ready=codex_login_ready,
                    codex_automation_supported=codex_supported,
                )
                rows.append(row)
                continue

            try:
                probe_results, total_cost_usd, call_count = self._run_live_openai_probes(
                    models,
                    profile=row_spec["profile"],
                    requested_surface=requested_surface,
                    effective_surface=effective_surface,
                )
            except LiveSurfaceUnavailableError as exc:
                row.status = "skipped"
                row.detail = f"Skipped: {exc}"
                rows.append(row)
                continue
            except Exception as exc:
                row.status = "failed"
                row.detail = self._summarize_live_probe_error(str(exc))
                rows.append(row)
                continue
            row.probe_results = probe_results
            row.total_cost_usd = total_cost_usd
            row.call_count = call_count
            row.score = round(
                sum(1.0 if probe.passed else 0.0 for probe in probe_results)
                / max(len(probe_results), 1),
                3,
            )
            row.status = "passed" if all(probe.passed for probe in probe_results) else "failed"
            row.detail = self._build_live_row_detail(
                requested_surface,
                effective_surface,
                probe_results,
            )
            rows.append(row)

        runnable_rows = [row for row in rows if row.status != "skipped"]
        report = EvalLiveMatrixReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            forgegod_version=__version__,
            matrix_name="openai-live-v1",
            detected_providers=list(detected_providers),
            codex_login_ready=codex_login_ready,
            codex_automation_supported=codex_supported,
            total_rows=len(rows),
            passed_rows=sum(1 for row in rows if row.status == "passed"),
            failed_rows=sum(1 for row in rows if row.status == "failed"),
            skipped_rows=sum(1 for row in rows if row.status == "skipped"),
            score=(
                round(sum(row.score for row in runnable_rows) / len(runnable_rows), 3)
                if runnable_rows
                else 0.0
            ),
            rows=rows,
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report

    def run_openai_live_surface_comparison(
        self,
        *,
        output_path: Path | None = None,
    ) -> EvalLiveComparisonReport:
        """Rank runnable live OpenAI rows and recommend the best current harness."""
        live_report = self.run_openai_live_surface_matrix()
        runnable_rows = [
            row for row in live_report.rows if row.status in {"passed", "failed"}
        ]
        ranked_rows = sorted(runnable_rows, key=self._live_comparison_sort_key, reverse=True)

        recommended = ranked_rows[0] if ranked_rows else None
        comparison_rows: list[EvalLiveComparisonRow] = []
        for index, row in enumerate(ranked_rows, start=1):
            passed_probes = sum(1 for probe in row.probe_results if probe.passed)
            total_probes = len(row.probe_results)
            comparison_rows.append(
                EvalLiveComparisonRow(
                    rank=index,
                    id=row.id,
                    profile=row.profile,
                    requested_openai_surface=row.requested_openai_surface,
                    effective_openai_surface=row.effective_openai_surface,
                    status=row.status,
                    score=row.score,
                    total_cost_usd=row.total_cost_usd,
                    call_count=row.call_count,
                    passed_probes=passed_probes,
                    total_probes=total_probes,
                    score_delta_vs_recommended=round(
                        row.score - (recommended.score if recommended else row.score), 3
                    ),
                    cost_delta_vs_recommended=round(
                        row.total_cost_usd
                        - (recommended.total_cost_usd if recommended else row.total_cost_usd),
                        6,
                    ),
                    call_delta_vs_recommended=row.call_count
                    - (recommended.call_count if recommended else row.call_count),
                    detail=row.detail,
                )
            )

        report = EvalLiveComparisonReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            forgegod_version=__version__,
            matrix_name="openai-live-compare-v1",
            source_matrix_name=live_report.matrix_name,
            detected_providers=list(live_report.detected_providers),
            total_rows=live_report.total_rows,
            runnable_rows=len(runnable_rows),
            passed_rows=live_report.passed_rows,
            failed_rows=live_report.failed_rows,
            skipped_rows=live_report.skipped_rows,
            recommended_row_id=recommended.id if recommended else "",
            recommendation_reason=self._build_live_comparison_reason(recommended),
            rows=comparison_rows,
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report

    def run_minimax_live_comparison(
        self,
        *,
        output_path: Path | None = None,
    ) -> EvalLiveComparisonReport:
        """Run MiniMax vs OpenAI adversarial comparison probes.

        If MINIMAX_API_KEY is set, probes MiniMax M2 with lightweight coding tasks
        and compares against OpenAI (adversarial reviewer/planner role) to validate
        the MiniMax provider is correctly wired in the router.
        """
        has_minimax = bool(os.environ.get("MINIMAX_API_KEY"))
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))

        comparison_rows: list[EvalLiveComparisonRow] = []
        minimax_probe_results: list[EvalLiveProbeResult] = []
        openai_probe_results: list[EvalLiveProbeResult] = []
        minimax_cost = 0.0
        openai_cost = 0.0
        minimax_calls = 0
        openai_calls = 0

        if has_minimax:
            try:
                (
                    minimax_probe_results,
                    minimax_cost,
                    minimax_calls,
                ) = self._run_live_minimax_probes()
            except Exception as exc:
                console.print(f"[red]MiniMax probe failed: {exc}[/red]")
                has_minimax = False

        if has_openai:
            try:
                cfg = self.config.model_copy(deep=True)
                cfg.models = ModelsConfig(
                    planner="openai:gpt-5.4",
                    coder="openai:gpt-5.4-mini",
                    reviewer="openai:gpt-5.4",
                    sentinel="openai:gpt-5.4",
                    escalation="openai:gpt-5.4",
                    researcher="openai:gpt-5.4-mini",
                )
                openai_probe_results, openai_cost, openai_calls = self._run_live_openai_probes(
                    models=cfg.models.model_dump(),
                    profile="single-model",
                    requested_surface="api-only",
                    effective_surface="api-only",
                )
            except Exception as exc:
                console.print(f"[red]OpenAI probe failed: {exc}[/red]")
                has_openai = False

        minimax_row = EvalLiveComparisonRow(
            rank=1,
            id="minimax_m2_alone",
            profile="single-model",
            requested_openai_surface="minimax",
            effective_openai_surface="minimax",
            status="passed" if has_minimax else "skipped",
            score=(
                round(
                    sum(1.0 for p in minimax_probe_results if p.passed)
                    / max(len(minimax_probe_results), 1),
                    3,
                )
                if minimax_probe_results else 0.0
            ),
            total_cost_usd=minimax_cost,
            call_count=minimax_calls,
            passed_probes=sum(1 for p in minimax_probe_results if p.passed),
            total_probes=len(minimax_probe_results),
            detail="MiniMax M2 standalone" if has_minimax else "Skipped: MINIMAX_API_KEY not set",
        )

        openai_row = EvalLiveComparisonRow(
            rank=2,
            id="openai_adversarial",
            profile="adversarial",
            requested_openai_surface="api-only",
            effective_openai_surface="api-only",
            status="passed" if has_openai else "skipped",
            score=(
                round(
                    sum(1.0 for p in openai_probe_results if p.passed)
                    / max(len(openai_probe_results), 1),
                    3,
                )
                if openai_probe_results else 0.0
            ),
            total_cost_usd=openai_cost,
            call_count=openai_calls,
            passed_probes=sum(1 for p in openai_probe_results if p.passed),
            total_probes=len(openai_probe_results),
            detail=(
                "OpenAI adversarial (planner/coder)"
                if has_openai
                else "Skipped: OPENAI_API_KEY not set"
            ),
        )

        if has_minimax and has_openai:
            comparison_rows = sorted(
                [minimax_row, openai_row],
                key=lambda r: r.score,
                reverse=True,
            )
            for idx, row in enumerate(comparison_rows, start=1):
                row.rank = idx
            recommended = comparison_rows[0]
        else:
            comparison_rows = [r for r in [minimax_row, openai_row] if r.status != "skipped"]
            recommended = comparison_rows[0] if comparison_rows else None

        report = EvalLiveComparisonReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            forgegod_version=__version__,
            matrix_name="minimax-live-compare-v1",
            source_matrix_name="minimax-live-v1",
            detected_providers=["minimax"] if has_minimax else [],
            total_rows=2,
            runnable_rows=len(comparison_rows),
            passed_rows=sum(1 for r in comparison_rows if r.status == "passed"),
            failed_rows=sum(1 for r in comparison_rows if r.status == "failed"),
            skipped_rows=2 - len(comparison_rows),
            recommended_row_id=recommended.id if recommended else "",
            recommendation_reason=(
                "MiniMax M2 is primary when available, OpenAI as adversarial reviewer."
                if recommended and recommended.id == "minimax_m2_alone"
                else "OpenAI is primary when MiniMax is not available."
            ),
            rows=comparison_rows,
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report

    def _run_live_minimax_probes(
        self,
    ) -> tuple[list[EvalLiveProbeResult], float, int]:
        """Run lightweight probes against MiniMax M2 API."""
        from forgegod.router import ModelRouter

        config = self.config.model_copy(deep=True)
        config.models = ModelsConfig(
            planner="minimax:minimax-m2",
            coder="minimax:minimax-m2",
            reviewer="minimax:minimax-m2",
            sentinel="minimax:minimax-m2",
            escalation="minimax:minimax-m2",
            researcher="minimax:minimax-m2",
        )

        async def _run() -> tuple[list[EvalLiveProbeResult], float, int]:
            router = ModelRouter(config)
            probe_results: list[EvalLiveProbeResult] = []
            try:
                with self._quiet_logger("forgegod.router", level=logging.ERROR):
                    for probe in _MINIMAX_LIVE_PROBES:
                        before_calls = router.call_count
                        try:
                            response, usage = await router.call(
                                probe["prompt"],
                                role=probe["role"],
                                system=probe["system"],
                                json_mode=False,
                                max_tokens=32,
                                temperature=0.0,
                            )
                        except Exception as exc:
                            raise RuntimeError(
                                f"MiniMax probe '{probe['name']}' failed: {exc}"
                            ) from exc
                        if response.lstrip().startswith("[ERROR:"):
                            raise RuntimeError(f"MiniMax probe returned error: {response}")
                        spec = ""
                        if router.call_count > before_calls and router._call_log:
                            spec = router._call_log[-1].get("spec", "")
                        provider, _, model = spec.partition(":")
                        observed = " ".join(response.split())[:160]
                        passed = probe["expected"] in response
                        probe_results.append(
                            EvalLiveProbeResult(
                                name=probe["name"],
                                role=probe["role"],
                                expected=probe["expected"],
                                observed=observed,
                                provider=provider,
                                model=model,
                                passed=passed,
                                detail="minimax:minimax-m2",
                                usage=usage.model_dump(),
                            )
                        )
                return probe_results, router.total_cost, router.call_count
            finally:
                await router.close()

        return asyncio.run(_run())

    def run_case(
        self,
        case: EvalCase,
        *,
        traces_dir: Path | None = None,
    ) -> EvalCaseResult:
        """Run one eval case against the real CLI application."""
        if case.scenario not in SCENARIOS:
            return EvalCaseResult(
                id=case.id,
                description=case.description,
                passed=False,
                error=f"Unknown mock scenario: {case.scenario}",
            )

        workspace = Path(tempfile.mkdtemp(prefix=f"forgegod_eval_{case.id}_"))
        started = None
        trace_path = ""
        try:
            self._prepare_workspace(workspace, case.setup)
            started = start_mock_openai_server(case.scenario)
            self._write_project_config(
                workspace,
                started.base_url,
                case=case,
                permission_mode=case.permission_mode,
                approval_mode=case.approval_mode,
                sandbox_mode=case.sandbox_mode,
            )
            if case.surface == "loop":
                self._write_prd(workspace, case)
            exit_code, output = self._invoke_case(workspace, case)

            if traces_dir is not None:
                trace_file = traces_dir / f"{case.id}.requests.json"
                trace_file.write_text(
                    json.dumps(started.server.requests, indent=2),
                    encoding="utf-8",
                )
                trace_path = str(trace_file)

            checks = self._grade_case(
                workspace=workspace,
                case=case,
                output=output,
                exit_code=exit_code,
                requests=started.server.requests,
            )
            trace_grades = self._run_trace_graders(
                workspace=workspace,
                case=case,
                output=output,
                requests=started.server.requests,
            )
            passed_checks = sum(1 for check in checks if check.passed)
            total_checks = len(checks) or 1
            score = round(passed_checks / total_checks, 3)
            return EvalCaseResult(
                id=case.id,
                description=case.description,
                passed=all(check.passed for check in checks),
                score=score,
                exit_code=exit_code,
                request_count=len(started.server.requests),
                output_preview=output[:500],
                checks=checks,
                trace_grades=trace_grades,
                trace_path=trace_path,
            )
        except Exception as exc:
            return EvalCaseResult(
                id=case.id,
                description=case.description,
                passed=False,
                error=str(exc),
                trace_path=trace_path,
            )
        finally:
            if started is not None:
                started.stop()
            shutil.rmtree(workspace, ignore_errors=True)

    @staticmethod
    def save_report(report: EvalReport, path: Path) -> None:
        """Persist a JSON report."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def _build_dimension_scores(
        cases: list[EvalCase],
        results: list[EvalCaseResult],
    ) -> dict[str, float]:
        """Split harness scores by dimension for release decisions."""
        by_id = {result.id: result for result in results}
        grouped: dict[str, list[float]] = {}
        for case in cases:
            result = by_id.get(case.id)
            if result is None:
                continue
            for dimension in case.dimensions or ["uncategorized"]:
                grouped.setdefault(dimension, []).append(result.score)
        return {
            dimension: round(sum(scores) / len(scores), 3)
            for dimension, scores in sorted(grouped.items())
            if scores
        }

    @staticmethod
    def _build_trace_grade_scores(
        results: list[EvalCaseResult],
    ) -> dict[str, float]:
        """Aggregate local trace grader scores across applicable cases."""
        grouped: dict[str, list[float]] = {}
        for result in results:
            for grade in result.trace_grades:
                grouped.setdefault(grade.name, []).append(grade.score)
        return {
            name: round(sum(scores) / len(scores), 3)
            for name, scores in sorted(grouped.items())
            if scores
        }

    @staticmethod
    def _detect_live_openai_providers() -> tuple[list[str], bool, bool]:
        """Detect which real OpenAI auth surfaces are usable right now."""
        providers: list[str] = []
        api_ready = bool(os.environ.get("OPENAI_API_KEY"))
        codex_logged_in, _ = codex_login_status_sync()
        codex_supported, _ = codex_automation_status()
        codex_ready = codex_logged_in and codex_supported
        if api_ready:
            providers.append("openai")
        if codex_ready:
            providers.append("openai-codex")
        return providers, codex_logged_in, codex_supported

    @staticmethod
    def _is_requested_openai_surface_ready(
        requested_surface: str,
        detected_providers: list[str],
        *,
        codex_login_ready: bool,
        codex_automation_supported: bool,
    ) -> bool:
        provider_set = set(detected_providers)
        api_ready = "openai" in provider_set
        codex_ready = (
            "openai-codex" in provider_set
            and codex_login_ready
            and codex_automation_supported
        )
        if requested_surface == "auto":
            return api_ready or codex_ready
        if requested_surface == "api-only":
            return api_ready
        if requested_surface == "codex-only":
            return codex_ready
        if requested_surface == "api+codex":
            return api_ready and codex_ready
        return False

    @staticmethod
    def _build_live_surface_skip_detail(
        requested_surface: str,
        effective_surface: str,
        detected_providers: list[str],
        *,
        codex_login_ready: bool,
        codex_automation_supported: bool,
    ) -> str:
        provider_bits = ", ".join(detected_providers) or "none"
        if requested_surface == "api-only":
            return f"Skipped: OPENAI_API_KEY is not ready. Detected providers: {provider_bits}."
        if requested_surface == "codex-only":
            if not codex_login_ready:
                return "Skipped: Codex subscription is not logged in."
            if not codex_automation_supported:
                return (
                    "Skipped: Codex is logged in but automation is not "
                    "supported in this environment."
                )
            return (
                "Skipped: codex-only is not ready. "
                f"Effective surface would be {effective_surface}."
            )
        if requested_surface == "api+codex":
            missing: list[str] = []
            if "openai" not in detected_providers:
                missing.append("OpenAI API")
            if "openai-codex" not in detected_providers:
                if not codex_login_ready:
                    missing.append("Codex login")
                elif not codex_automation_supported:
                    missing.append("Codex automation")
            missing_text = ", ".join(missing) or "required OpenAI surfaces"
            return (
                f"Skipped: api+codex is not fully ready ({missing_text}). "
                f"Effective fallback would be {effective_surface}."
            )
        return "Skipped: no real OpenAI auth surface is ready."

    @staticmethod
    def _build_live_row_detail(
        requested_surface: str,
        effective_surface: str,
        probe_results: list[EvalLiveProbeResult],
    ) -> str:
        passing = sum(1 for probe in probe_results if probe.passed)
        total = len(probe_results)
        if requested_surface != effective_surface and requested_surface != "auto":
            return (
                f"Executed with fallback surface {effective_surface}; "
                f"{passing}/{total} probes passed."
            )
        return f"{passing}/{total} live probes passed."

    def _run_live_openai_probes(
        self,
        models: dict[str, str],
        *,
        profile: str,
        requested_surface: str,
        effective_surface: str,
    ) -> tuple[list[EvalLiveProbeResult], float, int]:
        """Run low-cost live probes against coder/reviewer roles."""
        from forgegod.router import ModelRouter

        config = self.config.model_copy(deep=True)
        config.models = type(config.models).model_validate(models)
        config.harness.profile = profile
        config.harness.preferred_provider = "openai"
        config.harness.openai_surface = requested_surface

        async def _run() -> tuple[list[EvalLiveProbeResult], float, int]:
            router = ModelRouter(config)
            probe_results: list[EvalLiveProbeResult] = []
            try:
                with self._quiet_logger("forgegod.router", level=logging.ERROR):
                    for probe in _OPENAI_LIVE_PROBES:
                        before_calls = router.call_count
                        try:
                            response, usage = await router.call(
                                probe["prompt"],
                                role=probe["role"],
                                system=probe["system"],
                                json_mode=False,
                                max_tokens=32,
                                temperature=0.0,
                            )
                        except Exception as exc:
                            raw_detail = str(exc)
                            detail = self._summarize_live_probe_error(raw_detail)
                            if self._is_temporarily_unavailable_live_surface_error(raw_detail):
                                raise LiveSurfaceUnavailableError(detail) from exc
                            raise RuntimeError(detail) from exc
                        if response.lstrip().startswith("[ERROR:"):
                            detail = self._summarize_live_probe_error(response)
                            if self._is_temporarily_unavailable_live_surface_error(response):
                                raise LiveSurfaceUnavailableError(detail)
                            raise RuntimeError(detail)
                        spec = ""
                        if router.call_count > before_calls and router._call_log:
                            spec = router._call_log[-1].get("spec", "")
                        provider, _, model = spec.partition(":")
                        observed = " ".join(response.split())[:160]
                        passed = probe["expected"] in response
                        probe_results.append(
                            EvalLiveProbeResult(
                                name=probe["name"],
                                role=probe["role"],
                                expected=probe["expected"],
                                observed=observed,
                                provider=provider,
                                model=model,
                                passed=passed,
                                detail=f"surface={effective_surface}",
                                usage=usage.model_dump(),
                            )
                        )
                return probe_results, router.total_cost, router.call_count
            finally:
                await router.close()

        return asyncio.run(_run())

    @staticmethod
    def _summarize_live_probe_error(detail: str) -> str:
        """Collapse noisy provider stderr into one actionable line."""
        text = " ".join((detail or "").split())
        if not text:
            return "live probe failed without stderr"
        usage_limit_match = re.search(
            r"You've hit your usage limit\..*?(purchase more credits|try again at [^.]+)\.?",
            text,
            flags=re.IGNORECASE,
        )
        if usage_limit_match:
            return usage_limit_match.group(0).strip()
        interesting_markers = [
            "You've hit your usage limit.",
            "Usage limit exceeded.",
            "insufficient_quota",
            "Rate limit exceeded",
            "authentication failed",
            "invalid_api_key",
            "Codex CLI returned a non-zero status.",
        ]
        for marker in interesting_markers:
            index = text.find(marker)
            if index >= 0:
                return text[index : index + 240].strip()
        return text[:240].strip()

    @staticmethod
    def _is_temporarily_unavailable_live_surface_error(detail: str) -> bool:
        """Return whether a live surface is present but temporarily unavailable."""
        lowered = (detail or "").lower()
        markers = (
            "usage limit",
            "purchase more credits",
            "insufficient_quota",
            "rate limit exceeded",
            "try again at",
            "upgrade to pro",
            "capacity",
            "temporarily unavailable",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _live_comparison_sort_key(
        row: EvalLiveMatrixRow,
    ) -> tuple[int, float, int, int, float, int]:
        """Prefer passing rows, then better scores, stronger splits, then lower cost."""
        profile_priority = 1 if row.profile == "adversarial" else 0
        surface_priority = {
            "api+codex": 3,
            "api-only": 2,
            "codex-only": 1,
            "auto": 0,
        }.get(row.requested_openai_surface, 0)
        return (
            1 if row.status == "passed" else 0,
            row.score,
            profile_priority,
            surface_priority,
            -row.total_cost_usd,
            -row.call_count,
        )

    @staticmethod
    def _build_live_comparison_reason(recommended: EvalLiveMatrixRow | None) -> str:
        """Explain why ForgeGod recommends the top live OpenAI row."""
        if recommended is None:
            return (
                "No runnable live OpenAI rows were available. Link OpenAI API and/or "
                "Codex automation, then rerun the comparison."
            )
        reasons = [f"highest live score ({recommended.score:.3f})"]
        if recommended.profile == "adversarial":
            reasons.append("prefers split builder/reviewer roles on ties")
        if recommended.requested_openai_surface == "api+codex":
            reasons.append("keeps API builder roles split from Codex review")
        elif recommended.requested_openai_surface == "api-only":
            reasons.append("keeps routing entirely on API-backed OpenAI models")
        elif recommended.requested_openai_surface == "codex-only":
            reasons.append("keeps every role on the Codex subscription surface")
        if recommended.total_cost_usd == 0:
            reasons.append("no billable API cost observed in probes")
        return "; ".join(reasons)

    @staticmethod
    def _select_cases(
        cases: list[EvalCase],
        *,
        selected_case_ids: set[str] | None,
        selected_tags: set[str] | None,
    ) -> list[EvalCase]:
        selected: list[EvalCase] = []
        for case in cases:
            if selected_case_ids and case.id not in selected_case_ids:
                continue
            if selected_tags and not selected_tags.intersection(case.tags):
                continue
            selected.append(case)
        return selected

    def _prepare_workspace(self, workspace: Path, setup: str) -> None:
        if setup == "none":
            return
        if setup == "hello":
            (workspace / "hello.txt").write_text("hello forgegod\n", encoding="utf-8")
            return
        if setup == "git":
            self._init_git_repo(workspace)
            return
        if setup == "git_src":
            self._init_git_repo(workspace)
            (workspace / "src").mkdir(exist_ok=True)
            return
        raise ValueError(f"Unknown workspace setup kind: {setup}")

    @staticmethod
    def _write_prd(workspace: Path, case: EvalCase) -> None:
        project_dir = workspace / ".forgegod"
        project_dir.mkdir(parents=True, exist_ok=True)
        prd_path = project_dir / "prd.json"
        prd_path.write_text(
            json.dumps(
                {
                    "project": "ForgeGod Harness Evals",
                    "description": "Deterministic workflow evals for the harness.",
                    "stories": [
                        {
                            "id": case.story_id,
                            "title": case.story_title,
                            "description": case.story_description,
                            "status": "todo",
                            "priority": 1,
                            "acceptance_criteria": case.story_acceptance_criteria,
                            "depends_on": [],
                            "files_touched": [],
                            "iterations": 0,
                            "max_iterations": 5,
                            "error_log": [],
                            "completed_at": "",
                        }
                    ],
                    "guardrails": [],
                    "learnings": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _init_git_repo(workspace: Path) -> None:
        commands = [
            ["git", "init"],
            ["git", "config", "user.email", "forgegod@example.com"],
            ["git", "config", "user.name", "ForgeGod"],
        ]
        for cmd in commands:
            subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                check=True,
                text=True,
            )
        (workspace / "README.md").write_text("forgegod\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(workspace),
            capture_output=True,
            check=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(workspace),
            capture_output=True,
            check=True,
            text=True,
        )

    def _write_project_config(
        self,
        workspace: Path,
        base_url: str,
        *,
        case: EvalCase,
        permission_mode: str,
        approval_mode: str,
        sandbox_mode: str,
    ) -> None:
        config = self.config.model_copy(deep=True)
        config.models = recommend_model_defaults(
            case.detected_providers,
            ollama_available=False,
            codex_automation_supported=case.codex_automation_supported,
            profile=case.harness_profile,
            preferred_provider=case.preferred_provider,
            openai_surface=case.openai_surface,
        )
        config.harness.profile = case.harness_profile
        config.harness.preferred_provider = case.preferred_provider
        config.harness.openai_surface = case.openai_surface
        config.openai.base_url = base_url
        config.review.enabled = False
        config.review.always_review_run = False
        config.memory.enabled = False
        config.memory.extraction_enabled = False
        config.security.permission_mode = permission_mode
        config.security.approval_mode = approval_mode
        config.security.sandbox_mode = sandbox_mode
        config.loop.cooldown_seconds = 0.0
        config.loop.story_max_retries = 1
        config.project_dir = workspace / ".forgegod"
        config.project_dir.mkdir(parents=True, exist_ok=True)

        (config.project_dir / "config.toml").write_text(
            toml.dumps(
                config.model_dump(
                    mode="json",
                    exclude={"global_dir", "project_dir"},
                )
            ),
            encoding="utf-8",
        )

    def _invoke_case(self, workspace: Path, case: EvalCase) -> tuple[int, str]:
        from forgegod import cli as cli_module
        from forgegod import router as router_module
        from forgegod import sandbox as sandbox_module
        from forgegod.tools import shell as shell_module

        previous_openai_key = os.environ.get("OPENAI_API_KEY")
        args = self._build_args(case)
        with self._working_directory(workspace):
            captured_lines: list[str] = []
            original_print = cli_module.console.print
            original_sandbox = shell_module.run_in_real_sandbox
            original_codex_call = router_module.ModelRouter._call_openai_codex

            def capture_print(*renderables, **kwargs):
                for renderable in renderables:
                    body = getattr(renderable, "renderable", renderable)
                    text = str(body)
                    if text:
                        captured_lines.append(text)
                return original_print(*renderables, **kwargs)

            try:
                cli_module.console.print = capture_print
                os.environ["OPENAI_API_KEY"] = "mock-token"

                async def fake_codex_call(
                    router_self,
                    model,
                    prompt,
                    system,
                    json_mode,
                    max_tokens,
                    temperature,
                    tools,
                ):
                    return await router_module.ModelRouter._call_openai(
                        router_self,
                        model,
                        prompt,
                        system,
                        json_mode,
                        max_tokens,
                        temperature,
                        tools,
                    )

                router_module.ModelRouter._call_openai_codex = fake_codex_call
                if case.sandbox_backend == "success":
                    async def fake_sandbox(**_kwargs):
                        return sandbox_module.SandboxExecutionResult(
                            backend="docker",
                            returncode=0,
                            stdout="Python 3.13.5\n",
                            stderr="",
                        )

                    shell_module.run_in_real_sandbox = fake_sandbox
                elif case.sandbox_backend == "unavailable":
                    async def fake_sandbox(**_kwargs):
                        raise sandbox_module.SandboxUnavailableError(
                            "Strict sandbox backend is unavailable."
                        )

                    shell_module.run_in_real_sandbox = fake_sandbox

                if case.surface == "chat":
                    original_is_interactive = cli_module._cli_is_interactive
                    original_input = cli_module.console.input
                    prompts = iter(case.chat_inputs or [SCENARIOS[case.scenario].task, "/exit"])
                    cli_module._cli_is_interactive = lambda: True
                    cli_module.console.input = lambda *_args, **_kwargs: next(prompts)
                    try:
                        result = self.runner.invoke(cli_module.app, args, catch_exceptions=False)
                    finally:
                        cli_module._cli_is_interactive = original_is_interactive
                        cli_module.console.input = original_input
                elif case.surface == "loop":
                    result = self.runner.invoke(
                        cli_module.app,
                        args,
                        input=case.stdin_input,
                        catch_exceptions=False,
                    )
                else:
                    result = self.runner.invoke(
                        cli_module.app,
                        args,
                        input=case.stdin_input,
                        catch_exceptions=False,
                    )
            finally:
                cli_module.console.print = original_print
                shell_module.run_in_real_sandbox = original_sandbox
                router_module.ModelRouter._call_openai_codex = original_codex_call
                if previous_openai_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous_openai_key
        combined_output = "\n".join(part for part in [result.stdout, *captured_lines] if part)
        return result.exit_code, combined_output

    @staticmethod
    def _build_args(case: EvalCase) -> list[str]:
        args: list[str] = []
        if case.terse:
            args.append("--terse")
        if case.surface != "loop" and case.review:
            args.append("--review")
        elif case.surface != "loop":
            args.append("--no-review")
        if case.permission_mode:
            args.extend(["--permission-mode", case.permission_mode])
        if case.approval_mode != "deny":
            args.extend(["--approval-mode", case.approval_mode])

        if case.surface == "run":
            args.insert(0, "run")
            args.append(SCENARIOS[case.scenario].task)
        elif case.surface == "loop":
            args[0:0] = [
                "loop",
                "--prd",
                str(Path(".forgegod") / "prd.json"),
                "--workers",
                str(case.loop_workers),
                "--max",
                str(case.loop_max_iterations),
            ]
        return args

    def _grade_case(
        self,
        *,
        workspace: Path,
        case: EvalCase,
        output: str,
        exit_code: int,
        requests: list[dict[str, Any]],
    ) -> list[EvalCheckResult]:
        checks: list[EvalCheckResult] = []
        expected = case.expectations

        if expected.exit_code is not None:
            checks.append(
                EvalCheckResult(
                    name="exit_code",
                    passed=exit_code == expected.exit_code,
                    detail=f"expected {expected.exit_code}, got {exit_code}",
                )
            )
        if expected.request_count is not None:
            checks.append(
                EvalCheckResult(
                    name="request_count",
                    passed=len(requests) == expected.request_count,
                    detail=f"expected {expected.request_count}, got {len(requests)}",
                )
            )
        for snippet in expected.output_contains:
            checks.append(
                EvalCheckResult(
                    name=f"output_contains:{snippet[:40]}",
                    passed=snippet in output,
                    detail=snippet,
                )
            )
        for snippet in expected.output_not_contains:
            checks.append(
                EvalCheckResult(
                    name=f"output_not_contains:{snippet[:40]}",
                    passed=snippet not in output,
                    detail=snippet,
                )
            )
        for rel_path in expected.files_exist:
            checks.append(
                EvalCheckResult(
                    name=f"files_exist:{rel_path}",
                    passed=(workspace / rel_path).exists(),
                    detail=rel_path,
                )
            )
        for rel_path in expected.files_absent:
            checks.append(
                EvalCheckResult(
                    name=f"files_absent:{rel_path}",
                    passed=not (workspace / rel_path).exists(),
                    detail=rel_path,
                )
            )
        for rel_path, snippet in expected.file_contains.items():
            fpath = workspace / rel_path
            content = fpath.read_text(encoding="utf-8") if fpath.exists() else ""
            checks.append(
                EvalCheckResult(
                    name=f"file_contains:{rel_path}",
                    passed=snippet in content,
                    detail=f"{rel_path} contains {snippet!r}",
                )
            )
        for rel_path in expected.directories_empty:
            dpath = workspace / rel_path
            passed = not dpath.exists() or not any(dpath.iterdir())
            checks.append(
                EvalCheckResult(
                    name=f"directories_empty:{rel_path}",
                    passed=passed,
                    detail=rel_path,
                )
            )
        if expected.first_request_tools_include:
            advertised = []
            if requests:
                advertised = [
                    tool.get("function", {}).get("name", "")
                    for tool in requests[0].get("tools", [])
                ]
            for tool_name in expected.first_request_tools_include:
                checks.append(
                    EvalCheckResult(
                        name=f"first_request_tools_include:{tool_name}",
                        passed=tool_name in advertised,
                        detail=", ".join(advertised),
                    )
                )
        if (
            expected.prd_story_status is not None
            or expected.prd_story_files_touched
            or expected.prd_story_error_contains
        ):
            prd_path = workspace / ".forgegod" / "prd.json"
            story = {}
            if prd_path.exists():
                payload = json.loads(prd_path.read_text(encoding="utf-8"))
                for candidate in payload.get("stories", []):
                    if candidate.get("id") == case.story_id:
                        story = candidate
                        break
            if expected.prd_story_status is not None:
                checks.append(
                    EvalCheckResult(
                        name="prd_story_status",
                        passed=story.get("status") == expected.prd_story_status,
                        detail=f"expected {expected.prd_story_status}, got {story.get('status')}",
                    )
                )
            if expected.prd_story_files_touched:
                actual = story.get("files_touched", [])
                checks.append(
                    EvalCheckResult(
                        name="prd_story_files_touched",
                        passed=actual == expected.prd_story_files_touched,
                        detail=f"expected {expected.prd_story_files_touched}, got {actual}",
                    )
                )
            if expected.prd_story_error_contains:
                error_log = story.get("error_log", [])
                for snippet in expected.prd_story_error_contains:
                    checks.append(
                        EvalCheckResult(
                            name=f"prd_story_error_contains:{snippet[:40]}",
                            passed=any(snippet in entry for entry in error_log),
                            detail=snippet,
                        )
                    )
        return checks

    def _run_trace_graders(
        self,
        *,
        workspace: Path,
        case: EvalCase,
        output: str,
        requests: list[dict[str, Any]],
    ) -> list[EvalTraceGrade]:
        """Run deterministic local trace graders over one eval case."""
        grades: list[EvalTraceGrade] = []
        grades.append(
            self._grade_transport_noise_absent(case=case, output=output)
        )

        completion_grade = self._grade_completion_discipline(case=case, requests=requests)
        if completion_grade is not None:
            grades.append(completion_grade)

        permission_grade = self._grade_permission_visibility(
            workspace=workspace,
            case=case,
            output=output,
            requests=requests,
        )
        if permission_grade is not None:
            grades.append(permission_grade)

        strict_grade = self._grade_strict_surface(case=case, output=output)
        if strict_grade is not None:
            grades.append(strict_grade)

        loop_grade = self._grade_loop_summary(workspace=workspace, case=case, output=output)
        if loop_grade is not None:
            grades.append(loop_grade)

        return grades

    @staticmethod
    def _iter_tool_names(requests: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for request in requests:
            for tool in request.get("tools", []):
                names.append(tool.get("function", {}).get("name", ""))
        return names

    @staticmethod
    def _grade_transport_noise_absent(*, case: EvalCase, output: str) -> EvalTraceGrade:
        """Ensure user-facing surfaces are not dominated by transport chatter."""
        noisy_markers = [
            "POST /v1/",
            "HTTP/1.1",
            "status_code",
            "response_headers",
            "\"choices\":",
        ]
        score = 1.0 if not any(marker in output for marker in noisy_markers) else 0.0
        return EvalTraceGrade(
            name="transport_noise_absent",
            score=score,
            detail=f"surface={case.surface}",
        )

    def _grade_completion_discipline(
        self,
        *,
        case: EvalCase,
        requests: list[dict[str, Any]],
    ) -> EvalTraceGrade | None:
        """Grade whether write-heavy verification flows show disciplined traces."""
        if "verification" not in case.dimensions:
            return None
        tool_names = self._iter_tool_names(requests)
        if "write_file" not in tool_names:
            return None
        saw_bash = "bash" in tool_names
        saw_diff = "git_diff" in tool_names
        score = 1.0 if saw_diff and (saw_bash or case.surface == "chat") else 0.0
        return EvalTraceGrade(
            name="completion_discipline",
            score=score,
            detail=f"bash={saw_bash}, git_diff={saw_diff}",
        )

    def _grade_permission_visibility(
        self,
        *,
        workspace: Path,
        case: EvalCase,
        output: str,
        requests: list[dict[str, Any]],
    ) -> EvalTraceGrade | None:
        """Grade whether approval/denial surfaces are visible and safe."""
        if case.permission_mode != "read-only" and case.approval_mode != "prompt":
            return None
        tool_names = self._iter_tool_names(requests)
        attempted_write = "write_file" in tool_names
        if not attempted_write and case.approval_mode != "prompt":
            return None

        if case.approval_mode == "prompt":
            score = 1.0 if "Approval required" in output else 0.0
            detail = "prompt approval surfaced"
        else:
            blocked = "ForgeGod blocked tool 'write_file'" in output
            leaked_write = (workspace / "blocked.txt").exists()
            score = 1.0 if blocked and not leaked_write else 0.0
            detail = f"blocked={blocked}, leaked_write={leaked_write}"
        return EvalTraceGrade(
            name="permission_visibility",
            score=score,
            detail=detail,
        )

    @staticmethod
    def _grade_strict_surface(*, case: EvalCase, output: str) -> EvalTraceGrade | None:
        """Grade strict-sandbox messaging on success/failure paths."""
        if case.sandbox_mode != "strict":
            return None
        if case.sandbox_backend == "success":
            score = 1.0 if "Strict sandbox reported" in output else 0.0
            detail = "strict backend success surfaced"
        else:
            score = 1.0 if "backend is unavailable" in output else 0.0
            detail = "strict backend failure surfaced"
        return EvalTraceGrade(
            name="strict_surface_transparency",
            score=score,
            detail=detail,
        )

    @staticmethod
    def _grade_loop_summary(
        *,
        workspace: Path,
        case: EvalCase,
        output: str,
    ) -> EvalTraceGrade | None:
        """Grade whether loop cases surface a coherent story outcome."""
        if case.surface != "loop":
            return None
        prd_path = workspace / ".forgegod" / "prd.json"
        story_status = ""
        if prd_path.exists():
            payload = json.loads(prd_path.read_text(encoding="utf-8"))
            for story in payload.get("stories", []):
                if story.get("id") == case.story_id:
                    story_status = story.get("status", "")
                    break
        output_has_summary = "Completed:" in output and "Failed:" in output
        score = 1.0 if output_has_summary and story_status in {"done", "blocked"} else 0.0
        return EvalTraceGrade(
            name="loop_outcome_summary",
            score=score,
            detail=f"status={story_status}, summary={output_has_summary}",
        )

    @staticmethod
    @contextmanager
    def _working_directory(path: Path):
        previous = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(previous)

    @staticmethod
    @contextmanager
    def _quiet_logger(name: str, level: int = logging.ERROR):
        logger = logging.getLogger(name)
        previous_level = logger.level
        previous_disabled = logger.disabled
        logger.setLevel(level)
        logger.disabled = True
        try:
            yield
        finally:
            logger.disabled = previous_disabled
            logger.setLevel(previous_level)


_OPENAI_SURFACE_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "id": "adversarial_auto",
        "profile": "adversarial",
        "preferred_provider": "openai",
        "openai_surface": "auto",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "adversarial_api_only",
        "profile": "adversarial",
        "preferred_provider": "openai",
        "openai_surface": "api-only",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "adversarial_codex_only",
        "profile": "adversarial",
        "preferred_provider": "openai",
        "openai_surface": "codex-only",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "adversarial_api_codex",
        "profile": "adversarial",
        "preferred_provider": "openai",
        "openai_surface": "api+codex",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "single_model_auto",
        "profile": "single-model",
        "preferred_provider": "openai",
        "openai_surface": "auto",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "single_model_api_only",
        "profile": "single-model",
        "preferred_provider": "openai",
        "openai_surface": "api-only",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "single_model_codex_only",
        "profile": "single-model",
        "preferred_provider": "openai",
        "openai_surface": "codex-only",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
    {
        "id": "single_model_api_codex",
        "profile": "single-model",
        "preferred_provider": "openai",
        "openai_surface": "api+codex",
        "detected_providers": ["openai", "openai-codex"],
        "codex_automation_supported": True,
    },
)


_OPENAI_LIVE_PROBES: tuple[dict[str, str], ...] = (
    {
        "name": "coder_exact_marker",
        "role": "coder",
        "system": (
            "Reply with only the exact marker requested by the user. "
            "Do not add markdown, punctuation, or explanation."
        ),
        "prompt": "Return exactly this marker: FORGEGOD_CODER_OK",
        "expected": "FORGEGOD_CODER_OK",
    },
    {
        "name": "reviewer_exact_marker",
        "role": "reviewer",
        "system": (
            "Reply with only the exact marker requested by the user. "
            "Do not add markdown, punctuation, or explanation."
        ),
        "prompt": "Return exactly this marker: FORGEGOD_REVIEWER_OK",
        "expected": "FORGEGOD_REVIEWER_OK",
    },
)


_MINIMAX_LIVE_PROBES: tuple[dict[str, str], ...] = (
    {
        "name": "minimax_coder_marker",
        "role": "coder",
        "system": (
            "Reply with only the exact marker requested by the user. "
            "Do not add markdown, punctuation, or explanation."
        ),
        "prompt": "Return exactly this marker: FORGEGOD_MINIMAX_OK",
        "expected": "FORGEGOD_MINIMAX_OK",
    },
    {
        "name": "minimax_reasoning_marker",
        "role": "planner",
        "system": (
            "You are a reasoning assistant. Return only the exact marker requested."
        ),
        "prompt": "Return exactly this marker: FORGEGOD_REASONING_OK",
        "expected": "FORGEGOD_REASONING_OK",
    },
)
