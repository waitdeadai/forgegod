#!/usr/bin/env python3
"""ForgeGod Stress Test Runner — orchestrate, collect, report.

Usage:
    python scripts/run_stress_tests.py                        # full suite
    python scripts/run_stress_tests.py --component memory     # single component
    python scripts/run_stress_tests.py --output results.json  # save JSON
    python scripts/run_stress_tests.py --markdown             # print Markdown tables
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COMPONENTS = ["router", "memory", "budget", "security", "tools"]
ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = ROOT / "tests" / "stress" / ".stress_results.json"


def get_system_info() -> dict:
    import os
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu_cores": os.cpu_count() or 0,
        "architecture": platform.machine(),
    }


def run_tests(component: str | None = None) -> int:
    """Run stress tests via pytest. Returns exit code."""
    cmd = [sys.executable, "-m", "pytest", "tests/stress/", "-v", "--tb=short", "-m", "stress"]
    if component:
        cmd = [
            sys.executable, "-m", "pytest",
            f"tests/stress/test_stress_{component}.py",
            "-v", "--tb=short", "-m", "stress",
        ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


def load_results() -> dict:
    """Load metrics from the JSON file written by conftest."""
    if not RESULTS_FILE.exists():
        return {}
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))


def build_report(metrics: dict, exit_code: int) -> dict:
    """Build full report JSON."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "forgegod_version": "0.1.0",
        "system": get_system_info(),
        "components": metrics,
        "summary": {
            "exit_code": exit_code,
            "status": "all_passed" if exit_code == 0 else "some_failed",
        },
    }


def print_summary(report: dict):
    """Print human-readable summary to stdout."""
    print("\n" + "=" * 60)
    print("  ForgeGod Stress Test Report")
    print("=" * 60)
    print(f"  Date:    {report['timestamp'][:19]}")
    print(f"  System:  {report['system']['os']} / Python {report['system']['python']}")
    print(f"  Status:  {report['summary']['status']}")
    print("=" * 60)

    for comp, metrics in report.get("components", {}).items():
        print(f"\n  [{comp.upper()}]")
        for key, val in metrics.items():
            print(f"    {key}: {val}")

    print("\n" + "=" * 60)


def print_markdown(report: dict):
    """Print Markdown tables suitable for BENCHMARKS.md."""
    print("# ForgeGod Stress Test Results\n")
    print(f"**Date:** {report['timestamp'][:10]}")
    print(f"**System:** {report['system']['os']} / Python {report['system']['python']}")
    print(f"**CPU:** {report['system']['cpu_cores']} cores")
    print(f"**Status:** {report['summary']['status']}\n")

    for comp, metrics in report.get("components", {}).items():
        print(f"## {comp.title()}\n")
        print("| Metric | Value |")
        print("|:-------|------:|")
        for key, val in metrics.items():
            print(f"| {key} | {val} |")
        print()


def main():
    parser = argparse.ArgumentParser(description="ForgeGod Stress Test Runner")
    parser.add_argument("--component", choices=COMPONENTS, help="Run single component")
    parser.add_argument("--output", type=str, help="Save JSON report to file")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown tables")
    args = parser.parse_args()

    # Clean previous results
    if RESULTS_FILE.exists():
        RESULTS_FILE.unlink()

    # Run tests
    exit_code = run_tests(args.component)

    # Load metrics
    metrics = load_results()
    report = build_report(metrics, exit_code)

    # Output
    print_summary(report)

    if args.markdown:
        print()
        print_markdown(report)

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(f"\nJSON report saved to: {args.output}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
