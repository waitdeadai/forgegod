"""ForgeGod configuration — TOML files + env vars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field, model_validator

from forgegod.models import BudgetMode, ResearchDepth

# ── Defaults ──

DEFAULT_GLOBAL_DIR = Path.home() / ".forgegod"
DEFAULT_PROJECT_DIR = Path(".forgegod")
DEFAULT_CONFIG_FILENAME = "config.toml"

# Per-million-token costs (input, output) in USD
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-5.4": (1.25, 10.00),
    "gpt-5.4-mini": (0.25, 2.00),
    "gpt-5.4-nano": (0.05, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
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
    # Z.AI / GLM
    "glm-5.1": (1.40, 4.40),
    "glm-5": (1.00, 3.20),
    "glm-5-turbo": (1.20, 4.00),
    "glm-4.7": (0.60, 2.20),
    "glm-4.5-air": (0.20, 1.10),
    "kimi-k2.5": (0.60, 3.00),
    "kimi-k2-thinking": (0.60, 2.50),
    "kimi-k2-0905-preview": (0.60, 2.50),
    # MiniMax (OpenAI-compatible — pricing from platform.minimaxi.com)
    "minimax-m2": (0.50, 1.50),
    # OpenRouter (varies — user overrides)
}


class ModelsConfig(BaseModel):
    planner: str = "openai:gpt-5.4"
    coder: str = "ollama:qwen3-coder-next"
    reviewer: str = "openai:gpt-5.4"
    sentinel: str = "openai:gpt-5.4"
    escalation: str = "openai:gpt-5.4"
    researcher: str = "openai:gpt-5.4-mini"
    taste: str = "zai:glm-5.1"


class HarnessConfig(BaseModel):
    """Harness profile selection for role routing."""

    profile: str = "adversarial"  # adversarial | single-model | max_effort
    preferred_provider: str = "auto"  # auto | openai
    openai_surface: str = "auto"  # auto | api-only | codex-only | api+codex


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
    force_review_acceptance_criteria: bool = True


class TasteConfig(BaseModel):
    """Taste agent configuration — adversarial design director."""

    enabled: bool = False  # Opt-in
    model: str = "zai:glm-5.1"
    taste_spec_path: str = "taste.md"
    memory_path: str = ".forgegod/taste.memory"
    memory_scope: str = "both"  # project | global | both
    require_taste_md: bool = False
    auto_approve_threshold: float = 0.9
    max_revision_cycles: int = 3
    # Weights for overall score
    aesthetic_weight: float = 0.3
    ux_weight: float = 0.3
    copy_weight: float = 0.2
    adherence_weight: float = 0.2


# Level presets for EffortConfig (defined before class to avoid Pydantic metaclass issues)
EFFORT_LEVEL_PRESETS = {
    "minimal": {"min_drafts": 1, "always_verify": False, "no_shortcuts": False},
    "thorough": {"min_drafts": 2, "always_verify": True, "no_shortcuts": True},
}


class EffortConfig(BaseModel):
    """Max-effort mode — enforces thorough execution, blocks shortcuts.

    Activated by setting harness.profile = "max_effort".
    """
    enabled: bool = False
    level: str = "thorough"
    min_drafts: int = 2
    always_verify: bool = True
    no_shortcuts: bool = True
    shortcuts_blocked: list[str] = Field(default_factory=list)
    research_before_code: bool = True
    max_compaction_turns: int = 999
    retry_on_failure: bool = True

    @model_validator(mode="before")
    @classmethod
    def _apply_level_presets(cls, data):
        if isinstance(data, dict):
            level = data.get("level", "thorough")
            preset = EFFORT_LEVEL_PRESETS.get(level, {})
            for key, value in preset.items():
                if key not in data:
                    data[key] = value
        return data


class MemoryConfig(BaseModel):
    enabled: bool = True
    extraction_enabled: bool = True


class SICAConfig(BaseModel):
    enabled: bool = True
    max_modifications: int = 3
    improvement_threshold_pct: float = 5.0


class SecurityConfig(BaseModel):
    """Security guardrails — defense-in-depth for autonomous coding."""

    permission_mode: str = "workspace-write"  # read-only | workspace-write | danger-full-access
    approval_mode: str = "deny"  # deny | prompt | approve
    allowed_tools: list[str] = Field(default_factory=list)
    sandbox_mode: str = "standard"  # permissive | standard | strict
    sandbox_backend: str = "auto"  # auto | docker
    sandbox_image: str = "auto"  # auto chooses managed polyglot image for Node/Next repos
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


class OpenAIConfig(BaseModel):
    """OpenAI-compatible provider settings for direct and mock endpoints."""

    timeout: float = 120.0
    base_url: str = "https://api.openai.com/v1"
    reasoning_effort: str = "medium"
    verbosity: str = "medium"
    parallel_tool_calls: bool = True


class OpenAICodexConfig(BaseModel):
    """OpenAI Codex CLI subscription-backed provider settings."""

    command: str = "codex"
    timeout: float = 180.0
    sandbox: str = "read-only"
    ephemeral: bool = True


class KimiConfig(BaseModel):
    """Moonshot / Kimi provider settings."""

    timeout: float = 120.0
    base_url: str = "https://api.moonshot.ai/v1"


class ZAIConfig(BaseModel):
    """Z.AI / GLM provider settings."""

    timeout: float = 120.0
    base_url: str = "https://api.z.ai/api/paas/v4"
    coding_plan_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    use_coding_plan: bool = True


class MiniMaxConfig(BaseModel):
    """MiniMax M2 provider settings (OpenAI-compatible API)."""

    timeout: float = 120.0
    base_url: str = "https://api.minimax.io/v1"
    use_reasoning: bool = False  # enables reasoning_split in extra_body


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


class AgentConfig(BaseModel):
    """SOTA 2026 research-first agent configuration."""

    research_before_code: bool = True
    auto_research_on_stuck: bool = True
    auto_research_on_bad_review: bool = True
    auto_research_on_unknown_lib: bool = True
    max_auto_research_per_task: int = 3
    research_depth_default: ResearchDepth = ResearchDepth.SOTA
    research_depth_on_stuck: ResearchDepth = ResearchDepth.DEEP
    research_depth_on_bad_review: ResearchDepth = ResearchDepth.SOTA
    min_confidence_to_proceed: str = "medium"


class DeepResearchConfig(BaseModel):
    """Deep research phase configuration — causal chain + information gain threshold."""

    enabled: bool = False
    information_gain_threshold: float = 1.5
    max_search_iterations: int = 8
    causal_chain_mode: bool = True
    source_verification: bool = True
    competitive_intel: bool = True
    sota_patterns: bool = True
    complexity_tags: list[str] = Field(
        default_factory=lambda: ["architecture", "refactor", "security", "api", "auth", "database"]
    )


class AuditAgentConfig(BaseModel):
    """audit-agent bridge settings for ForgeGod runtime and CLI surfaces."""

    enabled: bool = True
    command: str = "auto"
    timeout_s: float = 300.0
    auto_run_on_loop: bool = True
    auto_run_on_hive: bool = True
    require_ready_to_plan: bool = True
    prefer_json_artifacts: bool = True


class SOTAMonitorConfig(BaseModel):
    """SOTA monitoring configuration — tracks performance against external benchmarks."""

    enabled: bool = False
    history_path: str = ".forgegod/sota_history.jsonl"
    cache_ttl_hours: int = 24


class SubagentsConfig(BaseModel):
    """Parallel subagent orchestration settings."""

    enabled: bool = False
    max_concurrency: int = 3
    max_retries: int = 2
    planner_model: str = "openai:gpt-5.4"
    reviewer_model: str = "openai:gpt-5.4"
    allowed_tools: list[str] = Field(default_factory=list)


class HiveConfig(BaseModel):
    """Hive multi-process coordinator settings."""

    max_workers: int = 4
    max_iterations: int = 10
    scheduler_mode: str = "hybrid"  # hybrid | greedy | priority


class ObsidianConfig(BaseModel):
    """Optional Obsidian vault projection/ingest settings."""

    enabled: bool = False
    vault_path: str = ""
    mode: str = "projection"  # disabled | projection | projection+ingest | bridge
    cli_command: str = "obsidian"
    headless_command: str = "ob"
    use_cli_when_available: bool = True
    write_strategy: str = "file-io"  # file-io | cli
    link_style: str = "wikilink"
    export_root: str = "ForgeGod"
    ingest_enabled: bool = False
    ingest_folders: list[str] = Field(
        default_factory=lambda: [
            "ForgeGod/Research",
            "ForgeGod/Patterns",
            "ForgeGod/Decisions",
        ]
    )
    ingest_max_notes: int = 25
    project_stable_memories_only: bool = True
    min_confidence: float = 0.65
    generate_dashboard: bool = True


class ForgeGodConfig(BaseModel):
    """Root configuration — merges global + project + env."""

    debug_wire: bool = False

    models: ModelsConfig = Field(default_factory=ModelsConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    sica: SICAConfig = Field(default_factory=SICAConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    terse: TerseConfig = Field(default_factory=TerseConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    openai_codex: OpenAICodexConfig = Field(default_factory=OpenAICodexConfig)
    kimi: KimiConfig = Field(default_factory=KimiConfig)
    zai: ZAIConfig = Field(default_factory=ZAIConfig)
    minimax: MiniMaxConfig = Field(default_factory=MiniMaxConfig)
    recon: ReconConfig = Field(default_factory=ReconConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    audit: AuditAgentConfig = Field(default_factory=AuditAgentConfig)
    subagents: SubagentsConfig = Field(default_factory=SubagentsConfig)
    hive: HiveConfig = Field(default_factory=HiveConfig)
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    taste: TasteConfig = Field(default_factory=TasteConfig)
    effort: EffortConfig = Field(default_factory=EffortConfig)
    deep_research: DeepResearchConfig = Field(default_factory=DeepResearchConfig)
    sota_monitor: SOTAMonitorConfig = Field(default_factory=SOTAMonitorConfig)

    # Runtime paths (not from config file)
    global_dir: Path = DEFAULT_GLOBAL_DIR
    project_dir: Path = DEFAULT_PROJECT_DIR


def recommend_model_defaults(
    providers: list[str] | set[str] | None = None,
    *,
    ollama_available: bool = True,
    codex_automation_supported: bool | None = None,
    profile: str = "adversarial",
    preferred_provider: str = "auto",
    openai_surface: str = "auto",
) -> ModelsConfig:
    """Choose sane default models for the currently available auth surfaces."""
    if codex_automation_supported is None:
        from forgegod.native_auth import codex_automation_status

        codex_automation_supported, _ = codex_automation_status()

    provider_set = set(providers or [])
    recommended = ModelsConfig()
    effective_openai_surface = resolve_openai_surface(
        openai_surface,
        provider_set,
        codex_automation_supported=codex_automation_supported,
    )

    def surface_allows(provider: str) -> bool:
        if effective_openai_surface == "auto":
            return True
        if provider == "openai":
            return effective_openai_surface in {"api-only", "api+codex"}
        if provider == "openai-codex":
            return effective_openai_surface in {"codex-only", "api+codex"}
        return False

    def prioritize(candidates: list[str]) -> list[str]:
        if effective_openai_surface != "auto":
            preferred: list[str] = []
            fallback: list[str] = []
            for spec in candidates:
                provider, _ = spec.split(":", 1)
                if surface_allows(provider):
                    preferred.append(spec)
                else:
                    fallback.append(spec)
            return preferred + fallback
        if preferred_provider != "openai":
            return candidates
        preferred: list[str] = []
        fallback: list[str] = []
        for spec in candidates:
            provider, _ = spec.split(":", 1)
            if provider in {"openai", "openai-codex"}:
                preferred.append(spec)
            else:
                fallback.append(spec)
        return preferred + fallback

    def pick(candidates: list[str]) -> str | None:
        for spec in prioritize(candidates):
            provider, _ = spec.split(":", 1)
            if not surface_allows(provider):
                continue
            if provider == "openai-codex" and not codex_automation_supported:
                continue
            if provider == "ollama":
                if ollama_available:
                    return spec
            elif provider in provider_set:
                return spec
        return None

    if profile == "single-model":
        unified = pick([
            "zai:glm-5.1",
            "minimax:minimax-m2",
            "openai:gpt-5.4",
            "openai-codex:gpt-5.4",
            "openai:gpt-5.4-mini",
            "anthropic:claude-sonnet-4-6-20250514",
            "kimi:kimi-k2.5",
            "gemini:gemini-2.5-flash",
            "deepseek:deepseek-chat",
            "openrouter:meta-llama/llama-3.3-70b-instruct",
            "ollama:qwen3-coder-next",
        ])
        if unified:
            recommended.planner = unified
            recommended.coder = unified
            recommended.reviewer = unified
            recommended.sentinel = unified
            recommended.escalation = unified
            recommended.researcher = unified
        return recommended

    planner = pick([
        "zai:glm-5.1",
        "minimax:minimax-m2",
        "openai:gpt-5.4",
        "openai-codex:gpt-5.4",
        "openai:gpt-5.4-mini",
        "anthropic:claude-sonnet-4-6-20250514",
        "kimi:kimi-k2.5",
        "gemini:gemini-2.5-flash",
        "deepseek:deepseek-chat",
        "openrouter:meta-llama/llama-3.3-70b-instruct",
        "ollama:qwen3-coder-next",
    ])
    if planner:
        recommended.planner = planner

    coder = pick([
        "openai:gpt-5.4-mini",
        "minimax:minimax-m2",
        "openai:gpt-5.4",
        "zai:glm-5.1",
        "openai-codex:gpt-5.4",
        "anthropic:claude-sonnet-4-6-20250514",
        "kimi:kimi-k2.5",
        "deepseek:deepseek-chat",
        "gemini:gemini-2.5-flash",
        "openrouter:meta-llama/llama-3.3-70b-instruct",
        "ollama:qwen3-coder-next",
    ])
    if coder:
        recommended.coder = coder

    reviewer = pick([
        "openai-codex:gpt-5.4",
        "minimax:minimax-m2",
        "openai:gpt-5.4",
        "openai:gpt-5.4-mini",
        "zai:glm-5.1",
        "anthropic:claude-sonnet-4-6-20250514",
        "kimi:kimi-k2.5",
        "deepseek:deepseek-reasoner",
        "gemini:gemini-2.5-flash",
        "openrouter:meta-llama/llama-3.3-70b-instruct",
        "ollama:qwen3-coder-next",
    ])
    if reviewer:
        recommended.reviewer = reviewer

    sentinel = pick([
        "openai:gpt-5.4",
        "openai-codex:gpt-5.4",
        "minimax:minimax-m2",
        "openai:gpt-5.4-mini",
        "zai:glm-5.1",
        "anthropic:claude-opus-4-6-20250610",
        "kimi:kimi-k2.5",
        "gemini:gemini-2.5-pro",
        "deepseek:deepseek-reasoner",
        "openrouter:meta-llama/llama-3.3-70b-instruct",
        "ollama:qwen3-coder-next",
    ])
    if sentinel:
        recommended.sentinel = sentinel
        recommended.escalation = sentinel

    researcher = pick([
        "openai:gpt-5.4-mini",
        "openai:gpt-5.4",
        "openai-codex:gpt-5.4",
        "zai:glm-5.1",
        "gemini:gemini-2.5-flash",
        "deepseek:deepseek-chat",
        "kimi:kimi-k2.5",
        "openrouter:meta-llama/llama-3.3-70b-instruct",
        "ollama:qwen3-coder-next",
    ])
    if researcher:
        recommended.researcher = researcher

    return recommended


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

    if config.harness.profile == "max_effort":
        config.effort.enabled = True

    return config


def init_project(
    project_root: Path | None = None,
    *,
    model_defaults: ModelsConfig | None = None,
    harness_profile: str | None = None,
    preferred_provider: str | None = None,
    openai_surface: str | None = None,
) -> Path:
    """Initialize .forgegod/ directory with default config."""
    if project_root is None:
        project_root = Path.cwd()

    project_dir = project_root / ".forgegod"
    project_dir.mkdir(parents=True, exist_ok=True)

    config_path = project_dir / DEFAULT_CONFIG_FILENAME
    if not config_path.exists():
        default = ForgeGodConfig()
        if model_defaults is not None:
            default.models = model_defaults
        if harness_profile is not None:
            default.harness.profile = harness_profile
        if preferred_provider is not None:
            default.harness.preferred_provider = preferred_provider
        if openai_surface is not None:
            default.harness.openai_surface = openai_surface
        config_path.write_text(
            toml.dumps(
                default.model_dump(
                    mode="json",
                    exclude={"global_dir", "project_dir"},
                )
            )
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
        # Top-level fields (not nested under a section)
        if key == prefix + "DEBUG_WIRE":
            result["debug_wire"] = _coerce(value)
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


def resolve_openai_surface(
    requested_surface: str,
    providers: list[str] | set[str] | None = None,
    *,
    codex_automation_supported: bool = True,
) -> str:
    """Resolve the requested OpenAI surface against the auth surfaces that are ready."""
    provider_set = set(providers or [])
    has_api = "openai" in provider_set
    has_codex = "openai-codex" in provider_set and codex_automation_supported

    if requested_surface == "api-only":
        if has_api:
            return "api-only"
        if has_codex:
            return "codex-only"
        return "auto"
    if requested_surface == "codex-only":
        if has_codex:
            return "codex-only"
        if has_api:
            return "api-only"
        return "auto"
    if requested_surface == "api+codex":
        if has_api and has_codex:
            return "api+codex"
        if has_api:
            return "api-only"
        if has_codex:
            return "codex-only"
        return "auto"
    return "auto"


def openai_surface_label(surface: str) -> str:
    """Return a short label for an OpenAI surface selection."""
    labels = {
        "auto": "auto",
        "api-only": "api-only",
        "codex-only": "codex-only",
        "api+codex": "api+codex",
    }
    return labels.get(surface, surface)
