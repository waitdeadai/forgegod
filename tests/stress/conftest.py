"""Shared fixtures and metrics collection for ForgeGod stress tests."""

from __future__ import annotations

import json
import os
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.memory import Memory

# ── Global metrics accumulator ──

_STRESS_METRICS: dict[str, Any] = {}


def record_metric(component: str, key: str, value: Any):
    """Record a stress test metric for the final report."""
    _STRESS_METRICS.setdefault(component, {})[key] = value


def adjusted_min_rate(target: float, *, profile: str = "default") -> float:
    """Return a platform-adjusted lower bound for throughput checks."""
    if os.name != "nt":
        return target

    factors = {
        "default": 0.75,
        "filesystem_read": 0.70,
        "filesystem_edit": 0.60,
        "classifier": 0.85,
        "memory_write": 0.80,
    }
    factor = factors.get(profile, factors["default"])
    if sys.version_info >= (3, 13):
        factor *= 0.95
    return target * factor


def adjusted_max_latency(target: float, *, profile: str = "default") -> float:
    """Return a platform-adjusted upper bound for latency checks."""
    if os.name != "nt":
        return target

    factors = {
        "default": 1.25,
        "memory_recall": 2.00,
    }
    factor = factors.get(profile, factors["default"])
    if sys.version_info >= (3, 13):
        factor *= 1.05
    return target * factor


def percentiles(values: list[float]) -> dict[str, float]:
    """Compute p50, p95, p99 from a list of floats (in ms)."""
    if not values:
        return {"p50": 0, "p95": 0, "p99": 0}
    s = sorted(values)
    n = len(s)
    return {
        "p50": s[n // 2],
        "p95": s[int(n * 0.95)],
        "p99": s[int(n * 0.99)],
    }


@contextmanager
def timed():
    """Context manager returning elapsed_ms on .elapsed after exit."""

    class Timer:
        elapsed: float = 0

    t = Timer()
    start = time.perf_counter()
    yield t
    t.elapsed = (time.perf_counter() - start) * 1000  # ms


# ── Fixtures ──


@pytest.fixture
def tmp_config(tmp_path):
    """ForgeGodConfig with temp project dir."""
    project_dir = tmp_path / ".forgegod"
    project_dir.mkdir()
    config = ForgeGodConfig()
    config.project_dir = project_dir
    return config


@pytest.fixture
def memory_instance(tmp_config):
    """Memory with temp DB."""
    return Memory(tmp_config)


@pytest.fixture
def budget_tracker(tmp_config):
    """BudgetTracker with temp DB."""
    return BudgetTracker(tmp_config)


@pytest.fixture
def seeded_rng():
    """Deterministic RNG for reproducible tests."""
    return random.Random(42)


@pytest.fixture
def large_codebase_dir(tmp_path):
    """Factory: creates a temp dir with N synthetic Python files."""

    def _make(n: int):
        base = tmp_path / "codebase"
        base.mkdir(exist_ok=True)
        rng = random.Random(42)
        for i in range(n):
            pkg = base / f"pkg_{i % 10}"
            pkg.mkdir(exist_ok=True)
            code = (
                f'"""Module {i}."""\n\n'
                f"class Handler{i}:\n"
                f'    """Handler for module {i}."""\n\n'
                f"    def process(self, data: str) -> str:\n"
                f'        return data.upper()\n\n'
                f"    def validate(self, value: int) -> bool:\n"
                f"        return value > {rng.randint(0, 100)}\n\n\n"
                f"def helper_{i}(x: int) -> int:\n"
                f"    return x * {rng.randint(2, 9)}\n"
            )
            (pkg / f"mod_{i}.py").write_text(code, encoding="utf-8")
        return str(base)

    return _make


# ── Pytest hooks ──


def pytest_sessionfinish(session, exitstatus):
    """Write collected metrics to JSON file after all tests complete."""
    if _STRESS_METRICS:
        out = Path(session.config.rootdir) / "tests" / "stress" / ".stress_results.json"
        out.write_text(json.dumps(_STRESS_METRICS, indent=2), encoding="utf-8")
