"""Tests for ForgeGod data models."""

from forgegod.models import (
    PRD,
    AgentResult,
    BudgetMode,
    BudgetStatus,
    CausalEdge,
    LoopState,
    LoopStatus,
    ModelSpec,
    Principle,
    ReflexionAttempt,
    ReviewResult,
    ReviewVerdict,
    SICAModification,
    Story,
    StoryStatus,
    ToolCall,
)


def test_model_spec_parse_with_provider():
    spec = ModelSpec.parse("openai:gpt-4o-mini")
    assert spec.provider == "openai"
    assert spec.model == "gpt-4o-mini"


def test_model_spec_parse_default_provider():
    spec = ModelSpec.parse("gpt-4o")
    assert spec.provider == "openai"
    assert spec.model == "gpt-4o"


def test_model_spec_str():
    spec = ModelSpec(provider="ollama", model="qwen3-coder-next")
    assert str(spec) == "ollama:qwen3-coder-next"


def test_budget_mode_enum():
    assert BudgetMode.NORMAL.value == "normal"
    assert BudgetMode.HALT.value == "halt"
    assert BudgetMode.LOCAL_ONLY.value == "local-only"


def test_story_defaults():
    story = Story(id="S001", title="Test story")
    assert story.status == StoryStatus.TODO
    assert story.priority == 1
    assert story.iterations == 0
    assert story.acceptance_criteria == []


def test_prd_creation():
    prd = PRD(
        project="test",
        stories=[
            Story(id="S001", title="First"),
            Story(id="S002", title="Second"),
        ],
    )
    assert len(prd.stories) == 2
    assert prd.stories[0].id == "S001"


def test_agent_result_defaults():
    result = AgentResult()
    assert result.success is False
    assert result.tool_calls_count == 0
    assert result.files_modified == []


def test_reflexion_attempt():
    attempt = ReflexionAttempt(
        attempt_number=1,
        model_used="openai:gpt-4o-mini",
        code_generated="print('hello')",
        validation_result="PASS",
        success=True,
    )
    assert attempt.success
    assert attempt.attempt_number == 1


def test_review_result():
    result = ReviewResult(
        verdict=ReviewVerdict.REVISE,
        confidence=0.8,
        reasoning="Missing error handling",
        issues=["No try/except"],
    )
    assert result.verdict == ReviewVerdict.REVISE
    assert len(result.issues) == 1


def test_budget_status():
    status = BudgetStatus(
        spent_today_usd=3.50,
        daily_limit_usd=5.00,
    )
    assert status.remaining_today_usd == 5.0  # default, not computed


def test_loop_state_defaults():
    state = LoopState()
    assert state.status == LoopStatus.IDLE
    assert state.stories_completed == 0
    assert state.total_cost_usd == 0.0


def test_tool_call():
    tc = ToolCall(name="read_file", arguments={"path": "/tmp/test.py"})
    assert tc.name == "read_file"
    assert tc.arguments["path"] == "/tmp/test.py"


def test_sica_modification():
    mod = SICAModification(
        target="strategy:model_routing",
        action="escalate",
        reason="low score",
    )
    assert mod.status == "proposed"


def test_principle():
    p = Principle(
        text="Write tests first",
        category="testing",
        confidence=0.7,
    )
    assert p.confidence == 0.7


def test_causal_edge():
    edge = CausalEdge(
        factor="type_hints",
        outcome="success",
        weight=0.8,
        observations=5,
    )
    assert edge.weight == 0.8
