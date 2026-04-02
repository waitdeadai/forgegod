"""Tests for ForgeGod budget tracker."""

import tempfile
from pathlib import Path

from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.models import BudgetMode, ModelUsage


def _make_tracker():
    config = ForgeGodConfig()
    config.project_dir = Path(tempfile.mkdtemp()) / ".forgegod"
    config.project_dir.mkdir(parents=True)
    return BudgetTracker(config)


def test_initial_status():
    tracker = _make_tracker()
    status = tracker.get_status()
    assert status.spent_today_usd == 0.0
    assert status.calls_today == 0
    assert status.remaining_today_usd == 5.0


def test_record_and_status():
    tracker = _make_tracker()
    usage = ModelUsage(
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.01,
        model="gpt-4o-mini",
        provider="openai",
    )
    tracker.record(usage, role="coder")

    status = tracker.get_status()
    assert status.spent_today_usd == 0.01
    assert status.calls_today == 1


def test_model_breakdown():
    tracker = _make_tracker()
    tracker.record(ModelUsage(cost_usd=0.01, model="gpt-4o-mini", provider="openai"))
    tracker.record(ModelUsage(cost_usd=0.05, model="gpt-4o", provider="openai"))
    tracker.record(ModelUsage(cost_usd=0.02, model="gpt-4o-mini", provider="openai"))

    breakdown = tracker.get_model_breakdown()
    assert "gpt-4o-mini" in breakdown
    assert breakdown["gpt-4o-mini"]["calls"] == 2
    assert breakdown["gpt-4o"]["calls"] == 1


def test_budget_check_normal():
    tracker = _make_tracker()
    mode = tracker.check_budget()
    assert mode == BudgetMode.NORMAL


def test_budget_check_throttle():
    tracker = _make_tracker()
    # Spend 80% of $5 = $4
    tracker.record(ModelUsage(cost_usd=4.0, model="test", provider="test"))
    mode = tracker.check_budget()
    assert mode == BudgetMode.THROTTLE


def test_budget_check_halt():
    tracker = _make_tracker()
    # Spend 100% of $5
    tracker.record(ModelUsage(cost_usd=5.0, model="test", provider="test"))
    mode = tracker.check_budget()
    assert mode == BudgetMode.HALT
