"""ForgeGod Doctor — diagnostic health check (Claude Code pattern).

Runs 6 checks and reports PASS/FAIL with actionable fix instructions.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from forgegod.i18n import t

console = Console()


class HealthCheck:
    """Single health check result."""

    def __init__(self, name: str, passed: bool, detail: str = "", fix: str = ""):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.fix = fix


def run_doctor(project_path: Path | None = None) -> list[HealthCheck]:
    """Run all health checks. Returns list of HealthCheck results."""
    checks: list[HealthCheck] = []
    project = Path(project_path or ".").resolve()

    # 1. Python version >= 3.11
    checks.append(_check_python())

    # 2. Config file exists + valid
    checks.append(_check_config(project))

    # 3. Ollama reachable (if configured)
    checks.append(_check_ollama(project))

    # 4. API keys valid
    checks.append(_check_api_keys())

    # 5. Git installed + repo
    checks.append(_check_git(project))

    # 6. Test runner detected
    checks.append(_check_test_runner(project))

    return checks


def print_doctor_results(checks: list[HealthCheck]) -> None:
    """Print health check results as Rich table."""
    table = Table(title=t("doctor_title"))
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")

    issues = 0
    for check in checks:
        if check.passed:
            status = f"[green]{t('doctor_pass')}[/green]"
        else:
            status = f"[red]{t('doctor_fail')}[/red]"
            issues += 1

        detail = check.detail
        if not check.passed and check.fix:
            detail = f"{check.detail}\n  Fix: {check.fix}" if check.detail else f"Fix: {check.fix}"

        table.add_row(check.name, status, detail)

    console.print(table)
    console.print()

    if issues == 0:
        console.print(f"[bold green]{t('doctor_all_ok')}[/bold green]")
    else:
        console.print(f"[yellow]{t('doctor_has_issues', count=str(issues))}[/yellow]")


def _check_python() -> HealthCheck:
    """Check Python version >= 3.11."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        return HealthCheck(t("doctor_python"), True, version_str)
    return HealthCheck(
        t("doctor_python"), False, version_str,
        fix="Install Python 3.11+: https://python.org/downloads/",
    )


def _check_config(project: Path) -> HealthCheck:
    """Check config file exists and is valid TOML."""
    config_path = project / ".forgegod" / "config.toml"
    if not config_path.exists():
        return HealthCheck(
            t("doctor_config"), False, "Not found",
            fix="Run: forgegod init",
        )
    try:
        import toml

        toml.load(config_path)
        return HealthCheck(t("doctor_config"), True, str(config_path))
    except Exception as e:
        return HealthCheck(
            t("doctor_config"), False, f"Invalid: {e}",
            fix="Delete .forgegod/config.toml and run: forgegod init",
        )


def _check_ollama(project: Path) -> HealthCheck:
    """Check if Ollama is reachable."""
    # Check if Ollama is configured
    config_path = project / ".forgegod" / "config.toml"
    uses_ollama = True  # Default assumption

    if config_path.exists():
        try:
            import toml

            config = toml.load(config_path)
            budget_mode = config.get("budget", {}).get("mode", "")
            if budget_mode in ("local-only", "throttle"):
                uses_ollama = True
            # Check if any model uses ollama
            models = config.get("models", {})
            uses_ollama = any("ollama:" in str(v) for v in models.values()) or uses_ollama
        except Exception:
            pass

    if not uses_ollama:
        return HealthCheck(t("doctor_ollama"), True, "Not configured (cloud-only mode)")

    try:
        import httpx

        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return HealthCheck(
                t("doctor_ollama"), True,
                f"Running ({len(models)} models)",
            )
    except Exception:
        pass

    return HealthCheck(
        t("doctor_ollama"), False, "Not reachable",
        fix="Start Ollama: ollama serve",
    )


def _check_api_keys() -> HealthCheck:
    """Check if any API keys are set."""
    keys = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "OPENROUTER_API_KEY": "OpenRouter",
    }

    found = []
    for env_var, name in keys.items():
        if os.environ.get(env_var):
            found.append(name)

    if found:
        return HealthCheck(t("doctor_api_keys"), True, ", ".join(found))

    # Check .env file
    env_path = Path(".forgegod/.env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for env_var, name in keys.items():
            if env_var in content:
                found.append(name)

    if found:
        return HealthCheck(t("doctor_api_keys"), True, f"{', '.join(found)} (from .env)")

    return HealthCheck(
        t("doctor_api_keys"), False, "No API keys found",
        fix="Run: forgegod init (or set OPENAI_API_KEY / ANTHROPIC_API_KEY)",
    )


def _check_git(project: Path) -> HealthCheck:
    """Check git is installed and project has a repo."""
    if not shutil.which("git"):
        return HealthCheck(
            t("doctor_git"), False, "git not found",
            fix="Install git: https://git-scm.com/downloads",
        )

    if (project / ".git").exists():
        return HealthCheck(t("doctor_git"), True, "Repo detected")

    return HealthCheck(
        t("doctor_git"), False, "No git repo",
        fix="Run: git init",
    )


def _check_test_runner(project: Path) -> HealthCheck:
    """Check if a test runner is detected."""
    runners = []

    if shutil.which("pytest"):
        runners.append("pytest")
    if (project / "package.json").exists():
        runners.append("npm test")
    if (project / "go.mod").exists():
        runners.append("go test")
    if (project / "Cargo.toml").exists():
        runners.append("cargo test")

    if runners:
        return HealthCheck(t("doctor_tests"), True, ", ".join(runners))

    return HealthCheck(
        t("doctor_tests"), False, "No test runner found",
        fix="Install: pip install pytest",
    )
