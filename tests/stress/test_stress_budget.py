"""Stress tests for ForgeGod Budget Tracker — throughput, precision, transitions."""

from __future__ import annotations

import pytest

from forgegod.models import BudgetMode, ModelUsage

from .conftest import record_metric, timed

pytestmark = pytest.mark.stress

MODELS = [
    "gpt-4o", "gpt-4o-mini", "o4-mini", "claude-sonnet", "claude-haiku",
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-3-flash",
    "deepseek-chat", "deepseek-reasoner",
    "qwen3.5:9b", "qwen3-coder-next", "llama-3.1-8b",
    "mistral-small", "phi-3.5-mini",
]


class TestRapidCostRecording:
    def test_1000_rapid_writes(self, budget_tracker):
        """1,000 rapid record() calls — measure write throughput."""
        n = 1000

        with timed() as t:
            for i in range(n):
                budget_tracker.record(
                    ModelUsage(
                        input_tokens=100 + i,
                        output_tokens=50 + i,
                        cost_usd=0.001,
                        model="gpt-4o-mini",
                        provider="openai",
                    ),
                    role="coder",
                    task_id=f"stress-{i}",
                )

        wps = n / (t.elapsed / 1000)
        status = budget_tracker.get_status()

        record_metric("budget", "writes_per_sec", round(wps, 0))
        assert status.calls_today == n
        assert abs(status.spent_today_usd - n * 0.001) < 1e-6
        assert wps > 100, f"Expected >100 writes/sec, got {wps:.0f}"


class TestModeTransitionAccuracy:
    def test_transitions_at_thresholds(self, budget_tracker):
        """Verify NORMAL→THROTTLE→HALT transitions at 80%/100% of $5 budget."""
        # Initial: NORMAL
        assert budget_tracker.check_budget() == BudgetMode.NORMAL

        # Spend $3.99 (79.8%) → still NORMAL
        budget_tracker.record(
            ModelUsage(cost_usd=3.99, model="test", provider="test")
        )
        assert budget_tracker.check_budget() == BudgetMode.NORMAL

        # Spend $0.02 more ($4.01 = 80.2%) → THROTTLE
        budget_tracker.record(
            ModelUsage(cost_usd=0.02, model="test", provider="test")
        )
        assert budget_tracker.check_budget() == BudgetMode.THROTTLE

        # Spend $0.98 more ($4.99) → still THROTTLE
        budget_tracker.record(
            ModelUsage(cost_usd=0.98, model="test", provider="test")
        )
        assert budget_tracker.check_budget() == BudgetMode.THROTTLE

        # Spend $0.02 more ($5.01) → HALT
        budget_tracker.record(
            ModelUsage(cost_usd=0.02, model="test", provider="test")
        )
        assert budget_tracker.check_budget() == BudgetMode.HALT

        record_metric("budget", "mode_transition_accuracy_pct", 100)


class TestFloatPrecision:
    def test_10k_tiny_costs(self, budget_tracker):
        """10,000 records of $0.000001 — verify no floating point drift."""
        n = 10_000
        cost_each = 0.000001

        with timed() as t:
            for _ in range(n):
                budget_tracker.record(
                    ModelUsage(cost_usd=cost_each, model="test", provider="test")
                )

        status = budget_tracker.get_status()
        expected = n * cost_each  # $0.01
        drift = abs(status.spent_today_usd - expected)

        record_metric("budget", "precision_10k_drift", drift)
        record_metric("budget", "precision_10k_elapsed_ms", round(t.elapsed, 1))

        # Allow tiny floating point error
        assert drift < 1e-6, f"Float drift too large: {drift}"


class TestModelBreakdownAtScale:
    def test_15_models_100_each(self, budget_tracker):
        """15 models × 100 records — measure breakdown query speed."""
        for model in MODELS:
            for i in range(100):
                budget_tracker.record(
                    ModelUsage(
                        cost_usd=0.01,
                        model=model,
                        provider="test",
                        input_tokens=1000,
                        output_tokens=500,
                    ),
                    role="coder",
                )

        with timed() as t:
            breakdown = budget_tracker.get_model_breakdown()

        assert len(breakdown) == len(MODELS)
        for model in MODELS:
            assert breakdown[model]["calls"] == 100

        record_metric("budget", "breakdown_15_models_ms", round(t.elapsed, 2))
        assert t.elapsed < 500, f"Breakdown query too slow: {t.elapsed:.0f}ms"
