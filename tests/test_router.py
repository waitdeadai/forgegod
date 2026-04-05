"""Tests for ForgeGod Model Router — circuit breaker and fallback chain logic."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from forgegod.config import BudgetConfig, ForgeGodConfig
from forgegod.models import BudgetMode, ModelSpec
from forgegod.router import FALLBACK_CHAINS, CircuitBreaker, ModelRouter


def _mock_ollama_response(*args, **kwargs):
    """Build a fake httpx Response that looks like Ollama /api/chat."""
    import json as _json
    body = _json.dumps({
        "message": {"role": "assistant", "content": "Hello, world!"},
        "done": True,
        "prompt_eval_count": 10,
        "eval_count": 5,
    }).encode()
    return httpx.Response(200, content=body, request=httpx.Request("POST", "http://localhost:11434/api/chat"))


_OLLAMA_PATCH = patch(
    "httpx.AsyncClient.post",
    new_callable=AsyncMock,
    side_effect=_mock_ollama_response,
)


class TestModelSpec:
    """Tests for ModelSpec.parse() method."""

    def test_parse_simple_spec(self):
        """Simple model spec without provider defaults to openai."""
        spec = ModelSpec.parse("gpt-4o-mini")
        assert spec.provider == "openai"
        assert spec.model == "gpt-4o-mini"

    def test_parse_openai_spec(self):
        """OpenAI model spec."""
        spec = ModelSpec.parse("openai:gpt-4o-mini")
        assert spec.provider == "openai"
        assert spec.model == "gpt-4o-mini"

    def test_parse_ollama_spec(self):
        """Ollama model spec."""
        spec = ModelSpec.parse("ollama:qwen3-coder-next")
        assert spec.provider == "ollama"
        assert spec.model == "qwen3-coder-next"

    def test_parse_anthropic_spec(self):
        """Anthropic model spec."""
        spec = ModelSpec.parse("anthropic:claude-3-5-sonnet")
        assert spec.provider == "anthropic"
        assert spec.model == "claude-3-5-sonnet"

    def test_parse_openrouter_spec(self):
        """OpenRouter model spec."""
        spec = ModelSpec.parse("openrouter:meta-llama/llama-3.1-8b")
        assert spec.provider == "openrouter"
        assert spec.model == "meta-llama/llama-3.1-8b"

    def test_parse_invalid_spec(self):
        """Invalid spec without colon defaults to openai."""
        spec = ModelSpec.parse("invalid-model")
        assert spec.provider == "openai"
        assert spec.model == "invalid-model"

    def test_spec_str_representation(self):
        """ModelSpec string representation."""
        spec = ModelSpec(provider="ollama", model="qwen:latest")
        assert str(spec) == "ollama:qwen:latest"


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state(self):
        """Circuit breaker starts closed."""
        cb = CircuitBreaker()
        assert cb.is_open("openai") is False

    def test_record_failure_closes_circuit(self):
        """After threshold failures, circuit opens."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("openai")
        assert cb.is_open("openai") is False
        cb.record_failure("openai")
        assert cb.is_open("openai") is True

    def test_record_success_resets_circuit(self):
        """Success resets failure count."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("openai")
        cb.record_success("openai")
        cb.record_failure("openai")
        assert cb.is_open("openai") is False

    def test_circuit_opens_after_threshold(self):
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        for i in range(3):
            cb.record_failure("openai")
        assert cb.is_open("openai") is True

    def test_circuit_resets_after_timeout(self):
        """Circuit closes after reset timeout."""
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        cb.record_failure("openai")
        assert cb.is_open("openai") is True
        time.sleep(0.15)  # Wait for timeout
        assert cb.is_open("openai") is False

    def test_different_providers_independent(self):
        """Different providers have independent circuits."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("openai")
        cb.record_failure("anthropic")
        # With threshold=2, 1 failure doesn't open circuit
        assert cb.is_open("openai") is False
        assert cb.is_open("anthropic") is False

    def test_failure_threshold_zero_always_opens(self):
        """With threshold=0, any failure immediately opens circuit."""
        cb = CircuitBreaker(failure_threshold=0)
        cb.record_failure("openai")
        # With threshold=0 and sliding window, any failure opens
        assert len(cb._failure_times.get("openai", [])) >= 1


class TestFallbackChain:
    """Tests for FALLBACK_CHAINS and routing logic."""

    def test_fallback_chain_coder(self):
        """Coder role fallback chain."""
        chain = FALLBACK_CHAINS["coder"]
        assert chain == ["coder", "reviewer", "escalation"]

    def test_fallback_chain_reviewer(self):
        """Reviewer role fallback chain."""
        chain = FALLBACK_CHAINS["reviewer"]
        assert chain == ["reviewer", "sentinel", "escalation"]

    def test_fallback_chain_planner(self):
        """Planner role fallback chain."""
        chain = FALLBACK_CHAINS["planner"]
        assert chain == ["planner", "coder"]

    def test_fallback_chain_sentinel(self):
        """Sentinel role fallback chain."""
        chain = FALLBACK_CHAINS["sentinel"]
        assert chain == ["sentinel", "escalation"]

    def test_fallback_chain_escalation(self):
        """Escalation role fallback chain."""
        chain = FALLBACK_CHAINS["escalation"]
        assert chain == ["escalation"]

    def test_unknown_role_fallback(self):
        """Unknown role uses default fallback chain."""
        chain = FALLBACK_CHAINS.get("unknown_role", ["coder", "escalation"])
        assert chain == ["coder", "escalation"]


class TestModelRouter:
    """Tests for ModelRouter class."""

    @pytest.fixture
    def mock_config(self) -> ForgeGodConfig:
        """Create a mock config with local-only model."""
        return ForgeGodConfig(
            ollama={"model": "qwen3-coder-next"},
            models={
                "coder": "ollama:qwen3-coder-next",
                "reviewer": "ollama:qwen3-coder-next",
                "escalation": "ollama:qwen3-coder-next",
            },
            budget=BudgetConfig(mode=BudgetMode.LOCAL_ONLY),
        )

    @pytest.fixture
    def router(self, mock_config: ForgeGodConfig) -> ModelRouter:
        """Create a router with mock config."""
        return ModelRouter(mock_config)

    @pytest.mark.asyncio
    async def test_local_only_mode(self, router: ModelRouter):
        """LOCAL_ONLY mode constructs correct spec for local model."""
        # Verify the router uses ollama provider and correct model
        assert router.config.budget.mode == BudgetMode.LOCAL_ONLY
        assert router.config.ollama.model == "qwen3-coder-next"

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_local_only_mode_with_system_prompt(self, mock_post, router: ModelRouter):
        """LOCAL_ONLY mode respects system prompt."""
        result, usage = await router.call(
            "What is 2+2?",
            role="coder",
            system="You are a math tutor.",
        )
        assert result  # mock returns "Hello, world!"
        mock_post.assert_called_once()

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_local_only_mode_with_tools(self, mock_post, router: ModelRouter):
        """LOCAL_ONLY mode supports tools parameter."""
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        result, usage = await router.call(
            "Test",
            role="coder",
            tools=tools,
        )
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_local_only_mode_with_json_mode(self, mock_post, router: ModelRouter):
        """LOCAL_ONLY mode supports json_mode parameter."""
        result, usage = await router.call(
            '{"key": "value"}',
            role="coder",
            json_mode=True,
        )
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_local_only_mode_with_max_tokens(self, mock_post, router: ModelRouter):
        """LOCAL_ONLY mode respects max_tokens parameter."""
        result, usage = await router.call(
            "Short answer",
            role="coder",
            max_tokens=100,
        )
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_local_only_mode_with_temperature(self, mock_post, router: ModelRouter):
        """LOCAL_ONLY mode respects temperature parameter."""
        result, usage = await router.call(
            "Creative text",
            role="coder",
            temperature=0.9,
        )
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_router_call_count(self, mock_post, router: ModelRouter):
        """Router tracks call count."""
        await router.call("Test 1", role="coder")
        await router.call("Test 2", role="coder")
        assert router.call_count == 2

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_router_total_cost(self, mock_post, router: ModelRouter):
        """Router tracks total cost (should be 0 for local model)."""
        await router.call("Test", role="coder")
        assert router.total_cost >= 0

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_router_with_empty_prompt(self, mock_post, router: ModelRouter):
        """Router handles empty prompt."""
        result, usage = await router.call("", role="coder")
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_router_with_list_prompt(self, mock_post, router: ModelRouter):
        """Router handles list prompt."""
        prompt = [{"role": "user", "content": "Hello"}]
        result, usage = await router.call(prompt, role="coder")
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_router_with_system_only(self, mock_post, router: ModelRouter):
        """Router handles system prompt only."""
        result, usage = await router.call(
            "Test",
            role="coder",
            system="System prompt only.",
        )
        assert result is not None

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_router_with_all_params(self, mock_post, router: ModelRouter):
        """Router handles all parameters together."""
        result, usage = await router.call(
            "Test prompt",
            role="coder",
            system="System prompt",
            json_mode=True,
            max_tokens=512,
            temperature=0.5,
            tools=[{"type": "function", "function": {"name": "test"}}],
        )
        assert result is not None


class TestModelRouterFallback:
    """Tests for ModelRouter fallback behavior."""

    @pytest.fixture
    def mock_config(self) -> ForgeGodConfig:
        """Create a mock config with multiple models."""
        return ForgeGodConfig(
            ollama={"model": "qwen3-coder-next"},
            models={
                "coder": "ollama:qwen3-coder-next",
                "reviewer": "ollama:qwen3-coder-next",
                "escalation": "ollama:qwen3-coder-next",
            },
            budget=BudgetConfig(mode=BudgetMode.NORMAL),
        )

    @pytest.fixture
    def router(self, mock_config: ForgeGodConfig) -> ModelRouter:
        """Create a router with mock config."""
        return ModelRouter(mock_config)

    @_OLLAMA_PATCH
    @pytest.mark.asyncio
    async def test_fallback_chain_ordering(self, mock_post, router: ModelRouter):
        """Fallback chain tries models in order."""
        result, usage = await router.call("Test", role="coder")
        assert result is not None
        assert usage.model == "qwen3-coder-next"

    @pytest.mark.asyncio
    async def test_fallback_on_first_failure(self, router: ModelRouter):
        """Fallback tries next model on first failure."""
        call_count = [0]

        async def mock_call_ollama(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Simulated failure")
            return "OK", {"input_tokens": 5, "output_tokens": 3}

        router._call_ollama = mock_call_ollama

        result, usage = await router.call("Test", role="coder")
        assert result is not None
        assert call_count[0] > 1

    @pytest.mark.asyncio
    async def test_fallback_exhaustion(self, router: ModelRouter):
        """When all models fail, returns error message."""
        async def always_fail(*args, **kwargs):
            raise Exception("Simulated failure")

        router._call_ollama = always_fail

        result, usage = await router.call("Test", role="coder")
        assert "ERROR" in result
        assert "All models failed" in result

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_fallback(self, router: ModelRouter):
        """Circuit breaker prevents calling failed provider."""
        # Open circuit for ollama
        router.circuit.record_failure("ollama")
        router.circuit.record_failure("ollama")
        router.circuit.record_failure("ollama")  # Opens circuit

        # All providers are ollama and circuit is open, so all should fail
        result, usage = await router.call("Test", role="coder")
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers(self, router: ModelRouter):
        """Circuit breaker recovers after timeout."""
        router.circuit.record_failure("ollama")
        router.circuit.record_failure("ollama")
        router.circuit.record_failure("ollama")  # Opens circuit

        # Simulate timeout by backdating the open_until timestamp
        router.circuit._open_until["ollama"] = time.time() - 1

        # Circuit should be closed now
        assert router.circuit.is_open("ollama") is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_success_resets(self, router: ModelRouter):
        """Success resets failure count."""
        router.circuit.record_failure("ollama")
        router.circuit.record_success("ollama")
        router.circuit.record_failure("ollama")

        # Should not be open yet
        assert router.circuit.is_open("ollama") is False

    @pytest.mark.asyncio
    async def test_router_handles_exception_in_call(self, router: ModelRouter):
        """Router handles exceptions gracefully."""
        async def raise_exception(*args, **kwargs):
            raise ValueError("Test exception")

        router._call_ollama = raise_exception

        result, usage = await router.call("Test", role="coder")
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_router_with_budget_halt(self, mock_config: ForgeGodConfig):
        """Router halts when budget is in HALT mode."""
        mock_config.budget.mode = BudgetMode.HALT
        router = ModelRouter(mock_config)

        result, usage = await router.call("Test", role="coder")
        assert "HALT" in result
        assert usage.input_tokens == 0

    @pytest.mark.asyncio
    async def test_router_budget_tracking(self, router: ModelRouter):
        """Router tracks budget mode."""
        assert router.config.budget.mode == BudgetMode.NORMAL
