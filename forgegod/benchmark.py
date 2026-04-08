"""ForgeGod Benchmark Engine — model comparison with multi-dimensional scoring.

Design based on SOTA research (2026):
- 12 tasks across 4 difficulty tiers (Snorkel pattern)
- 2 attempts per task with self-repair scoring (Aider pattern)
- Composite scoring: correctness 40%, quality 25%, efficiency 20%, cost 10%, self-repair 5%
- Isolated execution in temp directories
"""

from __future__ import annotations

import ast
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

from forgegod.config import ForgeGodConfig
from forgegod.i18n import t

logger = logging.getLogger("forgegod.benchmark")
console = Console()

# Path to scaffold project bundled with forgegod
_SCAFFOLD_DIR = Path(__file__).parent / "benchmark_scaffold"


# ── Models ──


class BenchmarkTask(BaseModel):
    """A single benchmark task."""

    id: str
    name: str
    prompt: str
    tier: int  # 1=trivial, 2=easy, 3=medium, 4=hard
    setup_files: dict[str, str] = Field(default_factory=dict)
    validation_cmd: str = "pytest tests/ -x -q"
    reference_complexity: int = 50


class BenchmarkResult(BaseModel):
    """Result of running one task with one model."""

    task_id: str
    model: str
    tier: int
    attempt_1_pass: bool = False
    attempt_2_pass: bool = False
    quality_score: float = 0.0
    elapsed_s: float = 0.0
    cost_usd: float = 0.0
    tokens_used: int = 0
    tool_calls: int = 0
    error: str = ""


class BenchmarkReport(BaseModel):
    """Full benchmark report."""

    timestamp: str = ""
    forgegod_version: str = ""
    results: list[BenchmarkResult] = Field(default_factory=list)
    composite_scores: dict[str, float] = Field(default_factory=dict)


# ── Built-in Tasks ──

BENCHMARK_TASKS: list[BenchmarkTask] = [
    # Tier 1 — Trivial (pure function generation)
    BenchmarkTask(
        id="t1_palindrome",
        name="Palindrome checker",
        prompt=(
            "Create a file `palindrome.py` with a function `is_palindrome(s: str) -> bool` "
            "that returns True if the string is a palindrome (case-insensitive, ignoring spaces "
            "and punctuation). Then create `tests/test_palindrome.py` with at least 5 test cases "
            "including edge cases (empty string, single char, mixed case, punctuation)."
        ),
        tier=1,
        validation_cmd="pytest tests/test_palindrome.py -x -q",
        reference_complexity=20,
    ),
    BenchmarkTask(
        id="t1_fizzbuzz",
        name="FizzBuzz",
        prompt=(
            "Create a file `fizzbuzz.py` with a function `fizzbuzz(n: int) -> list[str]` that "
            "returns a list of strings from 1 to n where multiples of 3 are 'Fizz', multiples "
            "of 5 are 'Buzz', multiples of both are 'FizzBuzz', "
            "and others are the number as a string. "
            "Then create `tests/test_fizzbuzz.py` with tests for n=15, n=1, n=0, and n=100."
        ),
        tier=1,
        validation_cmd="pytest tests/test_fizzbuzz.py -x -q",
        reference_complexity=15,
    ),
    BenchmarkTask(
        id="t1_linked_list",
        name="Reverse linked list",
        prompt=(
            "Create a file `linked_list.py` with a `Node` class (val, next) and a function "
            "`reverse_list(head: Node | None) -> Node | None` that reverses a singly linked list "
            "in-place. Then create `tests/test_linked_list.py` with tests for empty list, "
            "single node, 3 nodes, and 5 nodes."
        ),
        tier=1,
        validation_cmd="pytest tests/test_linked_list.py -x -q",
        reference_complexity=25,
    ),
    # Tier 2 — Easy (existing project modification)
    BenchmarkTask(
        id="t2_health",
        name="Add /health endpoint",
        prompt=(
            "Add a `/health` endpoint to `server.py` that returns "
            '`{"status": "ok", "uptime_seconds": <float>}` where uptime_seconds is the time '
            "since the server module was imported. Add tests in `tests/test_health.py` that "
            "verify the endpoint returns 200 with the correct JSON structure."
        ),
        tier=2,
        validation_cmd="pytest tests/test_health.py -x -q",
        reference_complexity=30,
    ),
    BenchmarkTask(
        id="t2_tests_utils",
        name="Add tests for utils module",
        prompt=(
            "Read `utils.py` and write comprehensive tests in `tests/test_utils_extended.py`. "
            "Cover: process_data with mode='filter' and flag=True, mode='transform' with dicts, "
            "mode='aggregate' with empty list, mode='validate' with invalid emails, "
            "format_output with empty data and unknown format. At least 10 new test functions."
        ),
        tier=2,
        validation_cmd="pytest tests/test_utils_extended.py -x -q",
        reference_complexity=40,
    ),
    BenchmarkTask(
        id="t2_validation",
        name="Add input validation",
        prompt=(
            "Add input validation to the `process_data` function in `utils.py`: "
            "raise `TypeError` if `data` is not a list, raise `ValueError` if `mode` is not "
            "one of 'filter', 'transform', 'aggregate', 'validate'. "
            "Add tests in `tests/test_validation.py` that verify "
            "the correct exceptions are raised. "
            "Existing tests in `tests/test_utils.py` must still pass."
        ),
        tier=2,
        validation_cmd="pytest tests/ -x -q",
        reference_complexity=35,
    ),
    # Tier 3 — Medium (multi-file changes)
    BenchmarkTask(
        id="t3_refactor",
        name="Refactor utils into modules",
        prompt=(
            "Refactor `utils.py` into a package: create `utils/` directory with "
            "`__init__.py` (re-exports), `filters.py` (filter + validate modes), "
            "`transforms.py` (transform mode), `aggregators.py` (aggregate mode), "
            "and `formatters.py` (format_output). All existing tests in `tests/test_utils.py` "
            "must still pass without modification."
        ),
        tier=3,
        validation_cmd="pytest tests/test_utils.py -x -q",
        reference_complexity=80,
    ),
    BenchmarkTask(
        id="t3_auth",
        name="Add auth middleware",
        prompt=(
            "Add API key authentication middleware to `server.py`. Create `auth.py` with: "
            "a function `verify_api_key(key: str) -> bool` that checks against a hardcoded "
            "list `['test-key-1', 'test-key-2']`, and a FastAPI dependency `require_api_key` "
            "that reads the `X-API-Key` header and returns 401 if invalid. "
            "Protect the root endpoint with this dependency. Keep /health unprotected. "
            "Add tests in `tests/test_auth.py` for valid key, invalid key, missing key."
        ),
        tier=3,
        validation_cmd="pytest tests/test_auth.py -x -q",
        reference_complexity=60,
    ),
    BenchmarkTask(
        id="t3_crud",
        name="Build CRUD API with tests",
        prompt=(
            "Add a simple in-memory CRUD API to `server.py` for 'items' (id, name, price). "
            "Endpoints: POST /items (create), GET /items (list all), GET /items/{id} (get one), "
            "PUT /items/{id} (update), DELETE /items/{id} (delete). "
            "Use a module-level dict as storage. "
            "Return 404 for missing items. Add comprehensive tests in `tests/test_crud.py` "
            "covering all endpoints, 404 cases, and validation."
        ),
        tier=3,
        validation_cmd="pytest tests/test_crud.py -x -q",
        reference_complexity=90,
    ),
    # Tier 4 — Hard (complex multi-step)
    BenchmarkTask(
        id="t4_bugfix",
        name="Fix bug from failing tests",
        prompt=(
            "The following test is FAILING. Read it carefully, find the bug in `utils.py`, "
            "and fix it. Do NOT modify the test — only fix the source code.\n\n"
            "```python\n"
            "# tests/test_bug.py\n"
            "from utils import process_data\n\n"
            "def test_filter_with_extra_include_negative():\n"
            '    data = [{"value": 5}, {"value": -3}, {"value": 0}, {"value": -1}]\n'
            '    result = process_data(data, "filter", extra={"include_negative": True})\n'
            "    # Should include positive AND negative when include_negative=True\n"
            "    assert result == [5, -3, -1]\n"
            "```"
        ),
        tier=4,
        setup_files={
            "tests/test_bug.py": (
                "from utils import process_data\n\n"
                "def test_filter_with_extra_include_negative():\n"
                '    data = [{"value": 5}, {"value": -3}, {"value": 0}, {"value": -1}]\n'
                '    result = process_data(data, "filter", extra={"include_negative": True})\n'
                "    assert result == [5, -3, -1]\n"
            ),
        },
        validation_cmd="pytest tests/test_bug.py tests/test_utils.py -x -q",
        reference_complexity=50,
    ),
    BenchmarkTask(
        id="t4_rate_limit",
        name="Rate limiting + caching",
        prompt=(
            "Add rate limiting and response caching to `server.py`:\n"
            "1. Create `middleware.py` with a rate limiter: max 10 requests per minute per "
            "client IP. Return 429 with `{\"error\": \"rate_limited\"}` when exceeded.\n"
            "2. Add a simple in-memory cache decorator `@cache_response(ttl=60)` that caches "
            "GET endpoint responses by path for `ttl` seconds.\n"
            "3. Apply rate limiting to all endpoints. Apply caching to GET /items.\n"
            "4. Add tests in `tests/test_middleware.py` for: "
            "rate limit triggers after 10 requests, "
            "cache returns same response within TTL, cache expires after TTL."
        ),
        tier=4,
        validation_cmd="pytest tests/test_middleware.py -x -q",
        reference_complexity=120,
    ),
    BenchmarkTask(
        id="t4_multifile_refactor",
        name="Multi-file refactor preserving tests",
        prompt=(
            "Perform a major refactor of the project:\n"
            "1. Split `server.py` into `server.py` (app + routes) "
            "and `models.py` (Pydantic models)\n"
            "2. Add a `config.py` with a `Settings` class "
            "(APP_NAME, VERSION, DEBUG) using environment "
            "variables with defaults\n"
            "3. Update server.py to use Settings for the app title and version\n"
            "4. Add a `/version` endpoint returning `{\"version\": Settings.VERSION}`\n"
            "5. All existing tests must still pass. Add `tests/test_config.py` for Settings."
        ),
        tier=4,
        validation_cmd="pytest tests/ -x -q",
        reference_complexity=100,
    ),
]


# ── Benchmark Runner ──


class BenchmarkRunner:
    """Runs benchmark tasks against models, scores results."""

    def __init__(self, config: ForgeGodConfig, models: list[str]):
        self.config = config
        self.models = models
        self._results: list[BenchmarkResult] = []

    async def run_all(
        self,
        tier_filter: set[int] | None = None,
        runs_per_task: int = 1,
    ) -> list[BenchmarkResult]:
        """Run all benchmark tasks against all models."""
        tasks = BENCHMARK_TASKS
        if tier_filter:
            tasks = [t for t in tasks if t.tier in tier_filter]

        total = len(tasks) * len(self.models) * runs_per_task
        current = 0

        for model_str in self.models:
            console.print(f"\n[bold cyan]{t('bench_model', model=model_str)}[/bold cyan]")
            for task in tasks:
                for run_idx in range(runs_per_task):
                    current += 1
                    task_label = t(
                        "bench_task",
                        n=str(current),
                        total=str(total),
                        name=task.name,
                    )
                    console.print(
                        f"  [{current}/{total}] {task_label}"
                    )
                    result = await self.run_task(task, model_str)
                    self._results.append(result)

        return self._results

    async def run_task(self, task: BenchmarkTask, model_str: str) -> BenchmarkResult:
        """Run a single task with a single model. Returns BenchmarkResult."""
        result = BenchmarkResult(
            task_id=task.id,
            model=model_str,
            tier=task.tier,
        )

        workdir = Path(tempfile.mkdtemp(prefix=f"forgegod_bench_{task.id}_"))
        try:
            # Copy scaffold
            self._setup_workdir(workdir, task)

            # Attempt 1
            start = time.time()
            attempt1 = await self._run_agent(workdir, task.prompt, model_str)
            elapsed_1 = time.time() - start

            result.elapsed_s = round(elapsed_1, 2)
            result.tokens_used = attempt1.get("tokens", 0)
            result.cost_usd = attempt1.get("cost", 0.0)
            result.tool_calls = attempt1.get("tool_calls", 0)

            # Validate attempt 1
            pass_1 = self._validate(workdir, task.validation_cmd)
            result.attempt_1_pass = pass_1

            if not pass_1:
                # Attempt 2 — show errors, let agent self-repair
                console.print(f"    {t('bench_attempt', n='2')}")
                error_output = self._get_test_errors(workdir, task.validation_cmd)
                repair_prompt = (
                    f"The previous attempt FAILED. Here are the test errors:\n\n"
                    f"```\n{error_output[:2000]}\n```\n\n"
                    f"Fix the code so all tests pass. Original task: {task.prompt}"
                )
                start2 = time.time()
                attempt2 = await self._run_agent(workdir, repair_prompt, model_str)
                elapsed_2 = time.time() - start2

                result.elapsed_s = round(elapsed_1 + elapsed_2, 2)
                result.tokens_used += attempt2.get("tokens", 0)
                result.cost_usd += attempt2.get("cost", 0.0)
                result.tool_calls += attempt2.get("tool_calls", 0)

                result.attempt_2_pass = self._validate(workdir, task.validation_cmd)

            # Quality scoring
            result.quality_score = self._score_quality(workdir, task)

            passed = result.attempt_1_pass or result.attempt_2_pass
            status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            repair = ""
            if not result.attempt_1_pass and result.attempt_2_pass:
                repair = " [yellow](self-repaired)[/yellow]"
            console.print(
                f"    {status}{repair} | "
                f"quality={result.quality_score:.1f} | "
                f"{result.elapsed_s:.1f}s | "
                f"${result.cost_usd:.4f} | "
                f"{result.tokens_used:,} tokens"
            )

        except Exception as e:
            result.error = str(e)
            logger.warning(f"Benchmark task {task.id} failed: {e}")
            console.print(f"    [red]ERROR: {e}[/red]")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        return result

    def _setup_workdir(self, workdir: Path, task: BenchmarkTask) -> None:
        """Copy scaffold files and task-specific setup files into workdir."""
        # Copy scaffold
        if _SCAFFOLD_DIR.exists():
            for src in _SCAFFOLD_DIR.rglob("*"):
                if src.is_file() and "__pycache__" not in str(src):
                    rel = src.relative_to(_SCAFFOLD_DIR)
                    dst = workdir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        # Write task-specific setup files
        for path, content in task.setup_files.items():
            fpath = workdir / path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")

        # Initialize git so agent tools work
        subprocess.run(
            ["git", "init"], cwd=workdir, capture_output=True, check=False
        )
        subprocess.run(
            ["git", "add", "."], cwd=workdir, capture_output=True, check=False
        )
        subprocess.run(
            ["git", "commit", "-m", "scaffold"],
            cwd=workdir,
            capture_output=True,
            check=False,
            env={
                **__import__("os").environ,
                "GIT_AUTHOR_NAME": "bench",
                "GIT_COMMITTER_NAME": "bench",
                "GIT_AUTHOR_EMAIL": "b@b",
                "GIT_COMMITTER_EMAIL": "b@b",
            },
        )

    async def _run_agent(
        self, workdir: Path, prompt: str, model_str: str
    ) -> dict[str, Any]:
        """Run a ForgeGod agent on the task. Returns usage dict."""
        from forgegod.agent import Agent
        from forgegod.budget import BudgetTracker
        from forgegod.router import ModelRouter

        # Build config pointing at workdir
        bench_config = self.config.model_copy(deep=True)
        bench_config.project_dir = workdir / ".forgegod"
        bench_config.project_dir.mkdir(parents=True, exist_ok=True)
        bench_config.models.coder = model_str

        router = ModelRouter(bench_config)
        budget = BudgetTracker(bench_config)
        try:
            agent = Agent(
                config=bench_config,
                router=router,
                budget=budget,
                role="coder",
                max_turns=50,
            )
            result = await agent.run(prompt)
            return {
                "tokens": (
                    result.total_usage.input_tokens
                    + result.total_usage.output_tokens
                ),
                "cost": result.total_usage.cost_usd,
                "tool_calls": result.tool_calls_count,
                "success": result.success,
                "output": result.output,
            }
        finally:
            await router.close()
            budget.close()

    def _validate(self, workdir: Path, cmd: str) -> bool:
        """Run validation command in workdir. Returns True if exit code 0."""
        try:
            proc = subprocess.run(
                shlex.split(cmd, posix=(os.name != "nt")),
                cwd=workdir,
                capture_output=True,
                timeout=60,
                check=False,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def _get_test_errors(self, workdir: Path, cmd: str) -> str:
        """Run validation and return error output."""
        try:
            proc = subprocess.run(
                shlex.split(cmd, posix=(os.name != "nt")),
                cwd=workdir,
                capture_output=True,
                timeout=60,
                text=True,
                check=False,
            )
            return proc.stdout + proc.stderr
        except Exception as e:
            return str(e)

    def _score_quality(self, workdir: Path, task: BenchmarkTask) -> float:
        """Score code quality 0-10 based on AST analysis."""
        score = 5.0  # baseline

        py_files = list(workdir.glob("*.py")) + list(workdir.glob("**/*.py"))
        py_files = [f for f in py_files if "__pycache__" not in str(f)]

        total_nodes = 0
        valid_files = 0
        has_docstrings = 0
        has_type_hints = 0

        for f in py_files:
            if f.name.startswith("test_"):
                continue
            try:
                source = f.read_text(encoding="utf-8")
                tree = ast.parse(source)
                total_nodes += len(list(ast.walk(tree)))
                valid_files += 1

                # Check for docstrings
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if (node.body and isinstance(node.body[0], ast.Expr) and
                                isinstance(node.body[0].value, ast.Constant) and
                                isinstance(node.body[0].value.value, str)):
                            has_docstrings += 1

                # Check for type hints
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.returns or any(a.annotation for a in node.args.args):
                            has_type_hints += 1

            except SyntaxError:
                score -= 2.0  # Invalid Python is a heavy penalty

        # Adjust score based on findings
        if valid_files > 0:
            if has_docstrings > 0:
                score += 1.0
            if has_type_hints > 0:
                score += 1.0

            # Complexity check — penalize overly verbose solutions
            if task.reference_complexity > 0 and total_nodes > 0:
                ratio = total_nodes / task.reference_complexity
                if ratio > 3.0:
                    score -= 1.5  # Way too verbose
                elif ratio > 2.0:
                    score -= 0.5
                elif ratio < 0.5:
                    score -= 1.0  # Suspiciously simple

        return max(0.0, min(10.0, round(score, 1)))

    def compute_composite_scores(self) -> dict[str, float]:
        """Compute weighted composite score per model."""
        by_model: dict[str, list[BenchmarkResult]] = {}
        for r in self._results:
            by_model.setdefault(r.model, []).append(r)

        scores: dict[str, float] = {}
        for model, results in by_model.items():
            n = len(results)
            if n == 0:
                scores[model] = 0.0
                continue

            # Correctness (40%) — weighted by tier
            tier_weights = {1: 1, 2: 2, 3: 3, 4: 4}
            correct_weighted = sum(
                tier_weights.get(r.tier, 1) * (1 if r.attempt_1_pass or r.attempt_2_pass else 0)
                for r in results
            )
            max_weighted = sum(tier_weights.get(r.tier, 1) for r in results)
            correctness = (correct_weighted / max_weighted * 10) if max_weighted else 0

            # Quality (25%)
            quality = sum(r.quality_score for r in results) / n

            # Efficiency (20%) — inverse of time, normalized
            max_time = max(r.elapsed_s for r in results) or 1
            efficiency = sum(1 - (r.elapsed_s / max_time) for r in results) / n * 10

            # Cost (10%) — inverse of cost
            max_cost = max(r.cost_usd for r in results) or 0.01
            if max_cost > 0:
                cost_score = (
                    sum(1 - (r.cost_usd / max_cost) for r in results) / n * 10
                )
            else:
                cost_score = 10

            # Self-repair (5%)
            failed_first = [r for r in results if not r.attempt_1_pass]
            if failed_first:
                repair_rate = sum(1 for r in failed_first if r.attempt_2_pass) / len(failed_first)
                self_repair = repair_rate * 10
            else:
                self_repair = 10.0  # All passed first try

            composite = (
                correctness * 0.40 +
                quality * 0.25 +
                efficiency * 0.20 +
                cost_score * 0.10 +
                self_repair * 0.05
            )
            scores[model] = round(composite, 1)

        return scores

    def print_results(self) -> None:
        """Print results as Rich table."""
        composites = self.compute_composite_scores()

        table = Table(title=t("bench_results_title"))
        table.add_column("Model", style="cyan")
        table.add_column(t("bench_composite"), justify="center", style="bold")
        table.add_column(t("bench_correctness"), justify="center")
        table.add_column(t("bench_quality"), justify="center")
        table.add_column(t("bench_speed"), justify="center")
        table.add_column(t("bench_cost"), justify="center")
        table.add_column(t("bench_self_repair"), justify="center")

        by_model: dict[str, list[BenchmarkResult]] = {}
        for r in self._results:
            by_model.setdefault(r.model, []).append(r)

        for model in sorted(composites, key=composites.get, reverse=True):
            results = by_model[model]
            n = len(results)
            passed = sum(1 for r in results if r.attempt_1_pass or r.attempt_2_pass)
            avg_quality = sum(r.quality_score for r in results) / n if n else 0
            avg_speed = sum(r.elapsed_s for r in results) / n if n else 0
            total_cost = sum(r.cost_usd for r in results)
            failed_first = [r for r in results if not r.attempt_1_pass]
            repaired = sum(1 for r in failed_first if r.attempt_2_pass) if failed_first else 0
            repair_str = f"{repaired}/{len(failed_first)}" if failed_first else "n/a"

            table.add_row(
                model,
                f"{composites[model]:.1f}",
                f"{passed}/{n}",
                f"{avg_quality:.1f}",
                f"{avg_speed:.0f}s avg",
                f"${total_cost:.4f}",
                repair_str,
            )

        console.print()
        console.print(table)

    def save_results(self, path: Path) -> None:
        """Save results to JSON."""
        from forgegod import __version__

        report = BenchmarkReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            forgegod_version=__version__,
            results=self._results,
            composite_scores=self.compute_composite_scores(),
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\n{t('bench_saved', path=str(path))}")

    def format_leaderboard_markdown(self) -> str:
        """Generate markdown leaderboard table for README."""
        composites = self.compute_composite_scores()
        by_model: dict[str, list[BenchmarkResult]] = {}
        for r in self._results:
            by_model.setdefault(r.model, []).append(r)

        lines = [
            "## Model Leaderboard",
            "",
            "Run your own: `forgegod benchmark`",
            "",
            "| Model | Composite | Correctness | Quality | Speed | Cost | Self-Repair |",
            "|:------|:---------:|:-----------:|:-------:|:-----:|:----:|:-----------:|",
        ]

        for model in sorted(composites, key=composites.get, reverse=True):
            results = by_model[model]
            n = len(results)
            passed = sum(1 for r in results if r.attempt_1_pass or r.attempt_2_pass)
            avg_quality = sum(r.quality_score for r in results) / n if n else 0
            avg_speed = sum(r.elapsed_s for r in results) / n if n else 0
            total_cost = sum(r.cost_usd for r in results)
            failed_first = [r for r in results if not r.attempt_1_pass]
            repaired = sum(1 for r in failed_first if r.attempt_2_pass) if failed_first else 0
            repair_str = f"{repaired}/{len(failed_first)}" if failed_first else "n/a"

            lines.append(
                f"| {model} | {composites[model]:.1f} | {passed}/{n} | "
                f"{avg_quality:.1f} | {avg_speed:.0f}s avg | ${total_cost:.4f} | {repair_str} |"
            )

        lines.append("")
        lines.append(
            f"*Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
            f"Run `forgegod benchmark --update-readme` to refresh.*"
        )
        return "\n".join(lines)

    def update_readme(self, readme_path: Path) -> bool:
        """Insert or replace leaderboard in README.md. Returns True if updated."""
        if not readme_path.exists():
            return False

        content = readme_path.read_text(encoding="utf-8")
        leaderboard = self.format_leaderboard_markdown()

        # Replace existing leaderboard or insert before ## Architecture / ## How
        start_marker = "## Model Leaderboard"
        if start_marker in content:
            # Find the section and replace it
            start = content.index(start_marker)
            # Find next ## heading after leaderboard
            rest = content[start + len(start_marker):]
            next_heading = rest.find("\n## ")
            if next_heading >= 0:
                end = start + len(start_marker) + next_heading
                content = content[:start] + leaderboard + "\n" + content[end:]
            else:
                content = content[:start] + leaderboard + "\n"
        else:
            # Insert before "## How" or "## Architecture" or at end
            for marker in ["## How", "## Architecture", "## Configuration"]:
                if marker in content:
                    idx = content.index(marker)
                    content = content[:idx] + leaderboard + "\n\n" + content[idx:]
                    break
            else:
                content += "\n\n" + leaderboard + "\n"

        readme_path.write_text(content, encoding="utf-8")
        console.print(t("bench_readme_updated"))
        return True


def detect_available_models(config: ForgeGodConfig) -> list[str]:
    """Auto-detect which models are available."""
    import os

    models: list[str] = []

    def add_model(model: str) -> None:
        if model not in models:
            models.append(model)

    # Check Ollama
    try:
        import httpx

        resp = httpx.get(f"{config.ollama.host}/api/tags", timeout=3)
        if resp.status_code == 200:
            for m in resp.json().get("models", []):
                name = m.get("name", "")
                if name:
                    add_model(f"ollama:{name}")
    except Exception:
        pass

    # Check cloud providers
    if os.environ.get("OPENAI_API_KEY"):
        add_model("openai:gpt-4o-mini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        add_model("anthropic:claude-haiku-4-5-20251001")
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        add_model("gemini:gemini-3-flash")
    if os.environ.get("DEEPSEEK_API_KEY"):
        add_model("deepseek:deepseek-chat")
    if os.environ.get("MOONSHOT_API_KEY"):
        add_model("kimi:kimi-k2.5")
    if os.environ.get("OPENROUTER_API_KEY"):
        add_model("openrouter:meta-llama/llama-3.3-70b-instruct")

    return models
