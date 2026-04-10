"""Harness eval runner for deterministic ForgeGod behavior checks.

This is intentionally separate from `forgegod benchmark`:
- `benchmark` compares coding ability on scaffold tasks
- `evals` checks harness behavior, UX, permissions, and completion discipline
"""

from __future__ import annotations

import json
import os
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
from forgegod.config import ForgeGodConfig
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
    first_request_tools_include: list[str] = Field(default_factory=list)


class EvalCase(BaseModel):
    """One deterministic harness eval scenario."""

    id: str
    description: str
    scenario: str
    surface: str = "run"  # run | chat
    setup: str = "none"  # none | hello | git | git_src
    permission_mode: str = "workspace-write"
    approval_mode: str = "deny"
    sandbox_mode: str = "standard"
    review: bool = False
    terse: bool = False
    tags: list[str] = Field(default_factory=list)
    stdin_input: str = ""
    chat_inputs: list[str] = Field(default_factory=list)
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
    results: list[EvalCaseResult] = Field(default_factory=list)


_BUILTIN_MANIFEST = {
    "name": "forgegod-harness-evals-v1",
    "description": (
        "Deterministic harness evals for natural-language chat, terse mode, "
        "completion gates, and permission handling."
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
            "description": "Run mode writes code, verifies, diffs, and only then completes.",
            "scenario": "cli_completion_gate_roundtrip",
            "surface": "run",
            "setup": "git_src",
            "permission_mode": "workspace-write",
            "tags": ["run", "completion-gate", "verification"],
            "expectations": {
                "exit_code": 0,
                "request_count": 4,
                "output_contains": ["Implemented src/app.py and verified the change."],
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
            "expectations": {
                "exit_code": 1,
                "request_count": 1,
                "output_contains": ["ForgeGod blocked tool 'write_file'"],
                "files_absent": ["blocked.txt"],
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
            results=results,
        )
        if output_path is not None:
            report.manifest_path = str(output_path)
            self.save_report(report, output_path)
        return report

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
                permission_mode=case.permission_mode,
                approval_mode=case.approval_mode,
                sandbox_mode=case.sandbox_mode,
            )
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
        permission_mode: str,
        approval_mode: str,
        sandbox_mode: str,
    ) -> None:
        config = self.config.model_copy(deep=True)
        config.models.coder = "openai:gpt-4o-mini"
        config.models.reviewer = "openai:gpt-4o-mini"
        config.models.sentinel = "openai:gpt-4o-mini"
        config.models.escalation = "openai:gpt-4o-mini"
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

        previous_openai_key = os.environ.get("OPENAI_API_KEY")
        args = self._build_args(case)
        with self._working_directory(workspace):
            captured_lines: list[str] = []
            original_print = cli_module.console.print

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
                else:
                    result = self.runner.invoke(
                        cli_module.app,
                        args,
                        input=case.stdin_input,
                        catch_exceptions=False,
                    )
            finally:
                cli_module.console.print = original_print
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
        if case.review:
            args.append("--review")
        else:
            args.append("--no-review")
        if case.permission_mode:
            args.extend(["--permission-mode", case.permission_mode])
        if case.approval_mode != "deny":
            args.extend(["--approval-mode", case.approval_mode])

        if case.surface == "run":
            args.insert(0, "run")
            args.append(SCENARIOS[case.scenario].task)
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
        return checks

    @staticmethod
    @contextmanager
    def _working_directory(path: Path):
        previous = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(previous)
