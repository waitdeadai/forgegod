"""ForgeGod configuration — TOML files + env vars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field

from forgegod.models import BudgetMode

# ── Defaults ──

DEFAULT_GLOBAL_DIR = Path.home() / ".forgegod"
DEFAULT_PROJECT_DIR = Path(".forgegod")
DEFAULT_CONFIG_FILENAME = "config.toml"

# Per-million-token costs (input, output) in USD
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o3": (2.00, 8.00),
    "o4-mini": (1.10, 4.40),
    # Anthropic
    "claude-sonnet-4-6-20250514": (3.00, 15.00),
    "claude-opus-4-6-20250610": (5.00, 25.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    # Local (free)
    "qwen3-coder-next": (0.0, 0.0),
    "qwen3.5:9b": (0.0, 0.0),
    "tq-coder": (0.0, 0.0),
    "devstral-small-2:24b": (0.0, 0.0),
    # Google Gemini
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-3-flash": (0.075, 0.30),
    "gemini-3-pro": (1.25, 5.00),
    # DeepSeek (OpenAI-compatible, 22x cheaper than GPT-4o)
    "deepseek-chat": (0.28, 0.42),
    "deepseek-reasoner": (0.55, 2.19),
    "kimi-k2.5": (0.60, 3.00),
    "kimi-k2-thinking": (0.60, 2.50),
    "kimi-k2-0905-preview": (0.60, 2.50),
    # OpenRouter (varies — user overrides)
}


class ModelsConfig(BaseModel):
    planner: str = "openai:gpt-4o-mini"
    coder: str = "ollama:qwen3-coder-next"
    reviewer: str = "openai:o4-mini"
    sentinel: str = "openai:gpt-4o"
    escalation: str = "openai:gpt-4o"
    researcher: str = "gemini:gemini-2.5-flash"  # Recon: fast + cheap for search synthesis


class BudgetConfig(BaseModel):
    daily_limit_usd: float = 5.0
    mode: BudgetMode = BudgetMode.NORMAL


class LoopConfig(BaseModel):
    max_iterations: int = 100
    max_context_tokens: int = 100_000
    context_rotation_pct: int = 80
    gutter_detection: bool = True
    gutter_threshold: int = 3
    parallel_workers: int = 1
    story_max_retries: int = 3
    cooldown_seconds: float = 2.0
    story_timeout_s: float = 600.0  # Dead-man's switch per story (10 minutes)
    auto_commit_success: bool = False
    auto_push_success: bool = False


class OllamaConfig(BaseModel):
    host: str = "http://localhost:11434"
    model: str = "qwen3-coder-next"
    timeout: float = 300.0


class ReviewConfig(BaseModel):
    enabled: bool = True
    sample_rate: int = 3  # Review every Nth story in loop mode
    always_review_run: bool = True  # Always review in single-shot mode


class SICAConfig(BaseModel):
    enabled: bool = True
    max_modifications: int = 3
    improvement_threshold_pct: float = 5.0


class SecurityConfig(BaseModel):
    """Security guardrails — defense-in-depth for autonomous coding."""

    sandbox_mode: str = "standard"  # permissive | standard | strict
    redact_secrets: bool = True  # Strip API keys from tool output
    max_rules_file_chars: int = 10_000  # Cap rules.md injection (prompt injection defense)
    audit_commands: bool = True  # Log all bash commands to audit file
    blocked_paths: list[str] = Field(default_factory=lambda: [
        "/etc/shadow", "/etc/passwd",
    ])


class TerseConfig(BaseModel):
    """Caveman mode — terse prompts for 50-75% token savings."""

    enabled: bool = False
    compress_tool_output: bool = True
    tool_output_max_chars: int = 4000
    track_savings: bool = True


class GeminiConfig(BaseModel):
    """Google Gemini provider settings."""

    timeout: float = 120.0


class KimiConfig(BaseModel):
    """Moonshot / Kimi provider settings."""

    timeout: float = 120.0
    base_url: str = "https://api.moonshot.ai/v1"


class ReconConfig(BaseModel):
    """Reconnaissance mode — web research before planning."""

    enabled: bool = False
    max_searches: int = 15
    max_fetch_chars: int = 3000  # per-page content limit
    search_provider: str = "searxng"  # searxng, brave, exa
    searxng_url: str = "http://localhost:8888"
    brave_api_key: str = ""
    exa_api_key: str = ""
    debate_rounds: int = 3
    min_approval_score: float = 7.0  # 0-10, plan must score above this
    cache_results: bool = True


class ForgeGodConfig(BaseModel):
    """Root configuration — merges global + project + env."""

    models: ModelsConfig = Field(default_factory=ModelsConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    sica: SICAConfig = Field(default_factory=SICAConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    terse: TerseConfig = Field(default_factory=TerseConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    kimi: KimiConfig = Field(default_factory=KimiConfig)
    recon: ReconConfig = Field(default_factory=ReconConfig)

    # Runtime paths (not from config file)
    global_dir: Path = DEFAULT_GLOBAL_DIR
    project_dir: Path = DEFAULT_PROJECT_DIR


def load_config(project_root: Path | None = None) -> ForgeGodConfig:
    """Load config from global + project TOML, with env var overrides.

    Priority (highest wins):
    1. Environment variables (FORGEGOD_*)
    2. Project .forgegod/config.toml
    3. Global ~/.forgegod/config.toml
    4. Built-in defaults
    """
    merged: dict[str, Any] = {}

    # 0. Load .env file (python-dotenv) — so users don't need manual exports
    if project_root is None:
        project_root = Path.cwd()
    _load_dotenv(project_root / ".forgegod" / ".env")

    # 1. Global config
    global_dir = Path(os.environ.get("FORGEGOD_GLOBAL_DIR", DEFAULT_GLOBAL_DIR))
    global_config = global_dir / DEFAULT_CONFIG_FILENAME
    if global_config.exists():
        merged = _deep_merge(merged, toml.loads(global_config.read_text()))

    # 2. Project config
    project_dir = project_root / ".forgegod"
    project_config = project_dir / DEFAULT_CONFIG_FILENAME
    if project_config.exists():
        merged = _deep_merge(merged, toml.loads(project_config.read_text()))

    # 3. Env var overrides
    env_overrides = _env_overrides()
    merged = _deep_merge(merged, env_overrides)

    config = ForgeGodConfig(**merged)
    config.global_dir = global_dir
    config.project_dir = project_dir
    return config


def init_project(project_root: Path | None = None) -> Path:
    """Initialize .forgegod/ directory with default config."""
    if project_root is None:
        project_root = Path.cwd()

    project_dir = project_root / ".forgegod"
    project_dir.mkdir(parents=True, exist_ok=True)

    config_path = project_dir / DEFAULT_CONFIG_FILENAME
    if not config_path.exists():
        default = ForgeGodConfig()
        config_path.write_text(
            toml.dumps(default.model_dump(exclude={"global_dir", "project_dir"}))
        )

    # Create subdirs
    (project_dir / "logs").mkdir(exist_ok=True)

    return project_dir


def _env_overrides() -> dict[str, Any]:
    """Extract FORGEGOD_* env vars into nested dict."""
    result: dict[str, Any] = {}
    prefix = "FORGEGOD_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("_", 1)
        if len(parts) == 2:
            section, field = parts
            if section not in result:
                result[section] = {}
            result[section][field] = _coerce(value)
        elif len(parts) == 1:
            result[parts[0]] = _coerce(value)
    return result


def _coerce(value: str) -> Any:
    """Coerce string env var to appropriate type."""
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts — override wins on conflicts."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_dotenv(env_path: Path) -> None:
    """Load .env file if it exists. Uses python-dotenv if available, falls back to manual."""
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        # Fallback: manual .env parsing (no dependency needed)
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
