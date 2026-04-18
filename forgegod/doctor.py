"""ForgeGod doctor: diagnostic health check with actionable fixes."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from rich.table import Table

from forgegod.cli_ux import console
from forgegod.config import ForgeGodConfig, minimax_base_urls
from forgegod.i18n import t
from forgegod.sandbox import diagnose_strict_sandbox


class HealthCheck:
    """Single health check result."""

    def __init__(self, name: str, passed: bool, detail: str = "", fix: str = ""):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.fix = fix


async def verify_minimax_live(
    config: ForgeGodConfig,
    *,
    region: str = "auto",
    model: str = "MiniMax-M2.7-highspeed",
) -> tuple[bool, str]:
    """Run a cheap live MiniMax probe against the configured region preset."""
    import openai

    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        return False, "MINIMAX_API_KEY is not set"

    minimax_cfg = config.minimax.model_copy(deep=True)
    if region != "auto":
        minimax_cfg.region = region
        minimax_cfg.base_url = "auto"

    errors: list[str] = []
    for base_url in minimax_base_urls(minimax_cfg):
        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=minimax_cfg.timeout,
        )
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with exactly OK"}],
                max_tokens=8,
                temperature=0,
            )
            text = (response.choices[0].message.content or "").strip()
            return True, f"{model} OK via {base_url} -> {text[:32] or '(empty response)'}"
        except Exception as exc:
            errors.append(f"{base_url}: {exc}")
    return False, " | ".join(errors)


def run_doctor(project_path: Path | None = None) -> list[HealthCheck]:
    """Run all health checks. Returns list of HealthCheck results."""
    checks: list[HealthCheck] = []
    project = Path(project_path or ".").resolve()

    checks.append(_check_python())
    checks.append(_check_config(project))
    checks.append(_check_ollama(project))
    checks.append(_check_api_keys())
    checks.append(_check_git(project))
    checks.append(_check_strict_sandbox(project))
    checks.append(_check_test_runner(project))
    return checks


def print_doctor_results(checks: list[HealthCheck]) -> None:
    """Print health check results as Rich table."""
    table = Table(title=t("doctor_title"))
    table.add_column("Check", style="forge.primary")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="forge.muted")

    issues = 0
    for check in checks:
        if check.passed:
            status = f"[forge.success]{t('doctor_pass')}[/forge.success]"
        else:
            status = f"[forge.error]{t('doctor_fail')}[/forge.error]"
            issues += 1

        detail = check.detail
        if not check.passed and check.fix:
            detail = f"{check.detail}\n  Fix: {check.fix}" if check.detail else f"Fix: {check.fix}"

        table.add_row(check.name, status, detail)

    console.print(table)
    console.print()

    if issues == 0:
        console.print(f"[forge.success]{t('doctor_all_ok')}[/forge.success]")
    else:
        console.print(f"[forge.warn]{t('doctor_has_issues', count=str(issues))}[/forge.warn]")


def _check_python() -> HealthCheck:
    """Check Python version >= 3.11."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 11):
        return HealthCheck(t("doctor_python"), True, version_str)
    return HealthCheck(
        t("doctor_python"),
        False,
        version_str,
        fix="Install Python 3.11+: https://python.org/downloads/",
    )


def _check_config(project: Path) -> HealthCheck:
    """Check config file exists and is valid TOML."""
    config_path = project / ".forgegod" / "config.toml"
    if not config_path.exists():
        return HealthCheck(t("doctor_config"), False, "Not found", fix="Run: forgegod init")
    try:
        import toml

        toml.load(config_path)
        return HealthCheck(t("doctor_config"), True, str(config_path))
    except Exception as exc:
        return HealthCheck(
            t("doctor_config"),
            False,
            f"Invalid: {exc}",
            fix="Delete .forgegod/config.toml and run: forgegod init",
        )


def _check_ollama(project: Path) -> HealthCheck:
    """Check if Ollama is reachable."""
    config_path = project / ".forgegod" / "config.toml"
    uses_ollama = True

    if config_path.exists():
        try:
            import toml

            config = toml.load(config_path)
            budget_mode = config.get("budget", {}).get("mode", "")
            if budget_mode in ("local-only", "throttle"):
                uses_ollama = True
            models = config.get("models", {})
            uses_ollama = any("ollama:" in str(value) for value in models.values()) or uses_ollama
        except Exception:
            pass

    if not uses_ollama:
        return HealthCheck(t("doctor_ollama"), True, "Not configured (cloud-only mode)")

    try:
        import httpx

        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return HealthCheck(t("doctor_ollama"), True, f"Running ({len(models)} models)")
    except Exception:
        pass

    return HealthCheck(
        t("doctor_ollama"),
        False,
        "Not reachable",
        fix="Start Ollama: ollama serve",
    )


def _check_api_keys() -> HealthCheck:
    """Check if any auth surfaces are present.

    This is intentionally a presence check, not a live provider validation probe.
    """
    from forgegod.native_auth import codex_login_status_sync

    keys = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "OPENROUTER_API_KEY": "OpenRouter",
        "GOOGLE_API_KEY": "Gemini",
        "GEMINI_API_KEY": "Gemini",
        "DEEPSEEK_API_KEY": "DeepSeek",
        "MOONSHOT_API_KEY": "Kimi",
        "MINIMAX_API_KEY": "MiniMax (M2.7 Token Plan)",
        "ZAI_CODING_API_KEY": "Z.AI Coding Plan",
        "ZAI_API_KEY": "Z.AI",
    }

    found = []
    codex_logged_in, _ = codex_login_status_sync()
    if codex_logged_in:
        found.append("OpenAI Codex")
    for env_var, name in keys.items():
        if os.environ.get(env_var):
            found.append(name)

    if found:
        return HealthCheck(t("doctor_api_keys"), True, f"Detected: {', '.join(found)}")

    env_path = Path(".forgegod/.env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for env_var, name in keys.items():
            if env_var in content:
                found.append(name)

    if found:
        return HealthCheck(t("doctor_api_keys"), True, f"Detected: {', '.join(found)} (from .env)")

    return HealthCheck(
        t("doctor_api_keys"),
        False,
        "No API keys found",
        fix=(
            "Run: forgegod init (or use `forgegod auth login openai-codex`, set "
            "OPENAI_API_KEY / ANTHROPIC_API_KEY / MOONSHOT_API_KEY / "
            "ZAI_CODING_API_KEY / ZAI_API_KEY)"
        ),
    )


def _check_git(project: Path) -> HealthCheck:
    """Check git is installed and project has a repo."""
    if not shutil.which("git"):
        return HealthCheck(
            t("doctor_git"),
            False,
            "git not found",
            fix="Install git: https://git-scm.com/downloads",
        )

    if (project / ".git").exists():
        return HealthCheck(t("doctor_git"), True, "Repo detected")

    return HealthCheck(t("doctor_git"), False, "No git repo", fix="Run: git init")


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
        t("doctor_tests"),
        False,
        "No test runner found",
        fix="Install: pip install pytest",
    )


def _check_strict_sandbox(project: Path) -> HealthCheck:
    """Check whether strict sandbox prerequisites are ready."""
    config_path = project / ".forgegod" / "config.toml"
    if not config_path.exists():
        return HealthCheck(
            t("doctor_sandbox"),
            True,
            "Skipped until .forgegod/config.toml exists",
        )

    try:
        import toml

        config = toml.load(config_path)
    except Exception as exc:
        return HealthCheck(
            t("doctor_sandbox"),
            False,
            f"Could not read sandbox config: {exc}",
            fix="Fix .forgegod/config.toml before enabling strict sandbox.",
        )

    sandbox_mode = str(config.get("security", {}).get("sandbox_mode", "standard"))
    if sandbox_mode != "strict":
        return HealthCheck(
            t("doctor_sandbox"),
            True,
            f"Strict sandbox optional (current mode: {sandbox_mode})",
        )

    diagnosis = diagnose_strict_sandbox(project)
    if diagnosis.ready:
        return HealthCheck(t("doctor_sandbox"), True, diagnosis.detail)
    return HealthCheck(
        t("doctor_sandbox"),
        False,
        diagnosis.detail,
        fix=diagnosis.fix,
    )
