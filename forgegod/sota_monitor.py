"""ForgeGod SOTA Monitor — tracks performance against external benchmarks.

After each story completes, records metrics against known SOTA benchmarks
(SWE-bench Verified, BFCL, etc.) and produces verdicts:
- SOTA: top of competitive range
- ABOVE_BASELINE: better than ForgeGod's historical average
- AT_RISK: below ForgeGod's historical average
- BELOW_BASELINE: significantly below SOTA
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from forgegod.config import ForgeGodConfig, SOTAMonitorConfig

logger = logging.getLogger("forgegod.sota_monitor")


# ── SOTA Benchmark Reference Data ────────────────────────────────────────────

SOTA_BENCHMARKS: dict[str, dict[str, tuple[float, float]]] = {
    "swe_bench_verified": {
        "claude_code": (79.6, 80.9),
        "aider": (85.0, 90.0),
        "forgegod_planner": (75.8, 78.0),
        "forgegod_reviewer": (72.8, 77.8),
        "swe_agent": (65.0, 74.0),
        "devin": (67.0, 67.0),
    },
    "bfcl": {
        "claude_code": (92.0, 95.0),
        "aider": (88.0, 92.0),
        "forgegod": (78.0, 84.0),
        "swe_agent": (72.0, 80.0),
    },
}


class SOTAVerdict(str):
    SOTA = "SOTA"  # Top of competitive range
    ABOVE_BASELINE = "ABOVE_BASELINE"  # Better than ForgeGod historical
    AT_RISK = "AT_RISK"  # Below ForgeGod historical
    BELOW_BASELINE = "BELOW_BASELINE"  # Significantly below SOTA
    UNKNOWN = "UNKNOWN"  # Insufficient data


class StoryMetrics(BaseModel):
    """Metrics recorded for one story after completion."""

    story_id: str = ""
    story_title: str = ""
    passed: bool = False
    elapsed_s: float = 0.0
    cost_usd: float = 0.0
    iterations: int = 0
    tokens_used: int = 0
    tool_calls: int = 0
    effort_gate_passed: bool = False
    reviewer_approved: bool = False
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SOTARun(BaseModel):
    """One complete loop run's SOTA metrics."""

    run_id: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    benchmark: str = "swe_bench_verified"
    stories: list[StoryMetrics] = Field(default_factory=list)
    pass_rate: float = 0.0
    avg_cost_usd: float = 0.0
    avg_elapsed_s: float = 0.0
    estimated_sota_score: float = 0.0  # Synthetic estimate
    verdict: SOTAVerdict = SOTAVerdict.UNKNOWN
    delta_vs_previous: float = 0.0  # percentage points
    delta_vs_sota: float = 0.0  # vs top competitor range


class SOTAMonitor:
    """Records story completion metrics and computes SOTA verdicts."""

    def __init__(self, config: ForgeGodConfig | None = None):
        self.config = config or ForgeGodConfig()
        self.cfg: SOTAMonitorConfig = self.config.sota_monitor
        self._current_run: list[StoryMetrics] = []
        self._run_id: str = ""

    def start_run(self, run_id: str | None = None) -> str:
        """Start a new SOTA monitoring run. Returns run_id."""
        self._current_run = []
        self._run_id = (
            run_id
            or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )
        logger.info("SOTAMonitor: started run %s", self._run_id)
        return self._run_id

    def record_story(
        self,
        story_id: str,
        story_title: str = "",
        passed: bool = False,
        elapsed_s: float = 0.0,
        cost_usd: float = 0.0,
        iterations: int = 0,
        tokens_used: int = 0,
        tool_calls: int = 0,
        effort_gate_passed: bool = False,
        reviewer_approved: bool = False,
    ) -> None:
        """Record metrics for one completed story."""
        metric = StoryMetrics(
            story_id=story_id,
            story_title=story_title,
            passed=passed,
            elapsed_s=elapsed_s,
            cost_usd=cost_usd,
            iterations=iterations,
            tokens_used=tokens_used,
            tool_calls=tool_calls,
            effort_gate_passed=effort_gate_passed,
            reviewer_approved=reviewer_approved,
        )
        self._current_run.append(metric)
        logger.debug(
            "SOTAMonitor: recorded story %s — passed=%s cost=%.4f",
            story_id,
            passed,
            cost_usd,
        )

    def compute_run(self, benchmark: str = "swe_bench_verified") -> SOTARun:
        """Compute SOTA verdict for the current run."""
        if not self._current_run:
            return SOTARun(run_id=self._run_id, benchmark=benchmark)

        passed = sum(1 for m in self._current_run if m.passed)
        total = len(self._current_run)
        pass_rate = passed / total if total > 0 else 0.0
        avg_cost = sum(m.cost_usd for m in self._current_run) / total if total > 0 else 0.0
        avg_elapsed = (
            sum(m.elapsed_s for m in self._current_run) / total if total > 0 else 0.0
        )

        # Synthetic SOTA score: pass_rate * quality_weight + efficiency_weight
        # Based on SWE-bench methodology: correctness is primary, then efficiency
        estimated_sota_score = pass_rate * 100.0  # Normalize to 0-100

        # Compute vs previous run
        delta_vs_previous = self._delta_vs_previous_run(benchmark, estimated_sota_score)

        # Compute vs SOTA range
        sota_range = SOTA_BENCHMARKS.get(benchmark, {}).get("forgegod_planner", (0.0, 0.0))
        top_of_range = sota_range[1] if sota_range else 0.0
        delta_vs_sota = estimated_sota_score - top_of_range

        # Determine verdict
        verdict = self._compute_verdict(
            estimated_sota_score, delta_vs_previous, delta_vs_sota, benchmark
        )

        run = SOTARun(
            run_id=self._run_id,
            benchmark=benchmark,
            stories=self._current_run,
            pass_rate=pass_rate,
            avg_cost_usd=avg_cost,
            avg_elapsed_s=avg_elapsed,
            estimated_sota_score=estimated_sota_score,
            verdict=verdict,
            delta_vs_previous=delta_vs_previous,
            delta_vs_sota=delta_vs_sota,
        )

        # Persist to history
        self._append_history(run)

        return run

    def _compute_verdict(
        self,
        score: float,
        delta_prev: float,
        delta_sota: float,
        benchmark: str,
    ) -> SOTAVerdict:
        """Compute SOTA verdict based on score and deltas."""
        benchmarks = SOTA_BENCHMARKS.get(benchmark, {})
        if not benchmarks:
            return SOTAVerdict.UNKNOWN

        forgegod_range = benchmarks.get("forgegod_planner", (0.0, 0.0))
        if not forgegod_range:
            return SOTAVerdict.UNKNOWN

        fg_low, fg_high = forgegod_range
        top_competitor = max((r[1] for r in benchmarks.values()), default=0.0)

        # SOTA: within 5 points of top competitor
        if score >= top_competitor - 5.0:
            return SOTAVerdict.SOTA

        # ABOVE_BASELINE: above ForgeGod's own historical high
        if score >= fg_high:
            return SOTAVerdict.ABOVE_BASELINE

        # AT_RISK: below historical average but not drastically
        if score >= fg_low:
            return SOTAVerdict.AT_RISK

        # BELOW_BASELINE: significantly below historical range
        return SOTAVerdict.BELOW_BASELINE

    def _delta_vs_previous_run(
        self, benchmark: str, current_score: float
    ) -> float:
        """Get percentage-point delta vs the most recent run in history."""
        history_path = self._get_history_path()
        if not history_path.exists():
            return 0.0

        try:
            lines = history_path.read_text().strip().splitlines()
            if not lines:
                return 0.0
            last_run = json.loads(lines[-1])
            prev_score = last_run.get("estimated_sota_score", 0.0)
            return current_score - prev_score
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("SOTAMonitor: failed to read history: %s", e)
            return 0.0

    def _append_history(self, run: SOTARun) -> None:
        """Append run to the JSONL history file."""
        history_path = self._get_history_path()
        if not self.cfg.enabled:
            return

        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with history_path.open("a", encoding="utf-8") as f:
                f.write(run.model_dump_json() + "\n")
        except OSError as e:
            logger.warning("SOTAMonitor: failed to write history: %s", e)

    def _get_history_path(self) -> Path:
        return self.config.project_dir / self.cfg.history_path

    def get_history(
        self, limit: int = 10
    ) -> list[SOTARun]:
        """Read recent runs from history file."""
        history_path = self._get_history_path()
        if not history_path.exists():
            return []

        try:
            lines = history_path.read_text().strip().splitlines()
            runs = []
            for line in lines[-limit:]:
                try:
                    runs.append(SOTARun(**json.loads(line)))
                except json.JSONDecodeError:
                    continue
            return runs
        except OSError:
            return []

    def format_report(self, run: SOTARun) -> str:
        """Format a human-readable SOTA report."""
        verdict_emoji = {
            SOTAVerdict.SOTA: "[green]SOTA[/green]",
            SOTAVerdict.ABOVE_BASELINE: "[cyan]ABOVE_BASELINE[/cyan]",
            SOTAVerdict.AT_RISK: "[yellow]AT_RISK[/yellow]",
            SOTAVerdict.BELOW_BASELINE: "[red]BELOW_BASELINE[/red]",
            SOTAVerdict.UNKNOWN: "[dim]UNKNOWN[/dim]",
        }

        benchmark = run.benchmark
        benchmarks = SOTA_BENCHMARKS.get(benchmark, {})

        lines = [
            f"## SOTA Monitor Report — {run.run_id}",
            f"**Benchmark:** {benchmark}",
            f"**Verdict:** {verdict_emoji.get(run.verdict, run.verdict.value)}",
            "",
            f"- Pass rate: {run.pass_rate:.1%}",
            f"- Avg cost: ${run.avg_cost_usd:.4f}",
            f"- Avg time: {run.avg_elapsed_s:.1f}s",
            f"- Estimated SOTA score: {run.estimated_sota_score:.1f}",
            f"- Delta vs previous run: {run.delta_vs_previous:+.1f}pp",
            f"- Delta vs ForgeGod range: {run.delta_vs_sota:+.1f}pp",
            "",
            "### Competitive Landscape",
        ]

        for competitor, (low, high) in sorted(
            benchmarks.items(), key=lambda x: x[1][1], reverse=True
        ):
            marker = " ← ForgeGod" if competitor == "forgegod_planner" else ""
            lines.append(f"- **{competitor}**: {low:.1f}–{high:.1f}{marker}")

        lines.append("")
        lines.append(f"_Generated: {run.timestamp}_")

        return "\n".join(lines)
