"""ForgeGod data models — all Pydantic v2 models for the engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ──


class BudgetMode(str, Enum):
    NORMAL = "normal"
    THROTTLE = "throttle"
    LOCAL_ONLY = "local-only"
    HALT = "halt"


class StoryStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


class LoopStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    KILLED = "killed"
    IDLE = "idle"


# ── Model / Provider ──


class ModelSpec(BaseModel):
    """Parsed model specification like 'openai:gpt-4o-mini'."""

    provider: str  # openai, ollama, anthropic, openrouter, gemini
    model: str  # gpt-4o-mini, qwen3-coder-next, gemini-2.5-pro, etc.

    @classmethod
    def parse(cls, spec: str) -> "ModelSpec":
        if ":" not in spec:
            return cls(provider="openai", model=spec)
        provider, model = spec.split(":", 1)
        return cls(provider=provider, model=model)

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


class ModelUsage(BaseModel):
    """Token usage from a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    provider: str = ""
    elapsed_s: float = 0.0


# ── Tool System ──


class ToolCall(BaseModel):
    """A tool call parsed from LLM response."""

    id: str = ""
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of executing a tool."""

    tool_call_id: str = ""
    name: str = ""
    content: str = ""
    error: bool = False


class ToolDef(BaseModel):
    """Tool definition in OpenAI function-calling format."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


# ── Agent ──


class AgentResult(BaseModel):
    """Result of a complete agent run."""

    success: bool = False
    output: str = ""
    files_modified: list[str] = Field(default_factory=list)
    tool_calls_count: int = 0
    total_usage: ModelUsage = Field(default_factory=ModelUsage)
    error: str = ""


# ── Code Generation ──


class ReflexionAttempt(BaseModel):
    """One attempt in the Reflexion loop."""

    attempt_number: int
    model_used: str
    code_generated: str = ""
    validation_result: str = ""  # PASS or FAIL
    error_message: str = ""
    reflection: str = ""
    success: bool = False


class CodeFile(BaseModel):
    """Generated code file with validation metadata."""

    path: str
    content: str = ""
    ast_valid: bool = False
    imports_valid: bool = False
    tests_pass: bool = False
    reflexion_attempts: list[ReflexionAttempt] = Field(default_factory=list)


# ── PRD / Stories ──


class Story(BaseModel):
    """A single user story in the PRD."""

    id: str
    title: str
    description: str = ""
    status: StoryStatus = StoryStatus.TODO
    priority: int = 1
    acceptance_criteria: list[str] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    iterations: int = 0
    max_iterations: int = 5
    error_log: list[str] = Field(default_factory=list)
    completed_at: str = ""


class PRD(BaseModel):
    """Product Requirements Document — drives the Ralph loop."""

    project: str
    description: str = ""
    stories: list[Story] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    learnings: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Review ──


class ReviewResult(BaseModel):
    """Result of a frontier model review."""

    verdict: ReviewVerdict = ReviewVerdict.APPROVE
    confidence: float = 0.5
    reasoning: str = ""
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    model_used: str = ""
    cost_usd: float = 0.0


# ── Cost Tracking ──


class CostRecord(BaseModel):
    """Single cost record for SQLite."""

    timestamp: str = ""
    model: str = ""
    provider: str = ""
    role: str = ""  # planner, coder, reviewer, sentinel
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    task_id: str = ""


class BudgetStatus(BaseModel):
    """Current budget status."""

    mode: BudgetMode = BudgetMode.NORMAL
    daily_limit_usd: float = 5.0
    spent_today_usd: float = 0.0
    spent_total_usd: float = 0.0
    remaining_today_usd: float = 5.0
    calls_today: int = 0


# ── Memory / Learning ──


class Principle(BaseModel):
    """A learned coding principle from past outcomes."""

    principle_id: str = ""
    text: str = ""
    category: str = ""  # design, performance, security, testing, readability
    confidence: float = 0.0
    evidence_count: int = 0
    source_tasks: list[str] = Field(default_factory=list)
    created_at: str = ""


class CausalEdge(BaseModel):
    """An edge in the causal graph: factor → outcome."""

    factor: str = ""
    outcome: str = ""  # success or failure
    weight: float = 0.0
    observations: int = 0


# ── SICA ──


class SICAModification(BaseModel):
    """A proposed strategy modification."""

    target: str = ""  # e.g., "strategy:model_routing", "prompt:coder"
    action: str = ""
    reason: str = ""
    new_value: Any = None
    status: str = "proposed"  # proposed, tested, promoted, rejected, rolled_back
    score: float = 0.0
    proposed_at: str = ""


# ── Loop State ──


class LoopState(BaseModel):
    """Persistent state for the Ralph loop."""

    status: LoopStatus = LoopStatus.IDLE
    current_story_id: str = ""
    stories_completed: int = 0
    stories_failed: int = 0
    total_iterations: int = 0
    total_cost_usd: float = 0.0
    started_at: str = ""
    last_tick_at: str = ""
    gutter_count: int = 0
    context_rotations: int = 0


# ── Worktree ──


class WorkerStatus(BaseModel):
    """Status of a parallel worktree worker."""

    worker_id: str = ""
    worktree_path: str = ""
    branch: str = ""
    story_id: str = ""
    status: str = "idle"  # idle, running, done, failed
    result: AgentResult | None = None
