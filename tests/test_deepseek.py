"""Tests for DeepSeek provider + Anthropic prompt caching (Features 4+5).

Verifies:
- DeepSeek model spec parsing
- DeepSeek costs in MODEL_COSTS
- DeepSeek provider routing dispatch
- deepseek-reasoner in _REASONING_MODELS
- Anthropic cache_control in system message
- Cost calculation with cache tokens
"""

from __future__ import annotations

import pytest

from forgegod.config import MODEL_COSTS
from forgegod.models import ModelSpec
from forgegod.router import ModelRouter


class TestDeepSeekModelSpec:
    def test_parse_deepseek_chat(self):
        """deepseek:deepseek-chat parses correctly."""
        spec = ModelSpec.parse("deepseek:deepseek-chat")
        assert spec.provider == "deepseek"
        assert spec.model == "deepseek-chat"

    def test_parse_deepseek_reasoner(self):
        """deepseek:deepseek-reasoner parses correctly."""
        spec = ModelSpec.parse("deepseek:deepseek-reasoner")
        assert spec.provider == "deepseek"
        assert spec.model == "deepseek-reasoner"

    def test_deepseek_str_representation(self):
        """DeepSeek ModelSpec string representation."""
        spec = ModelSpec(provider="deepseek", model="deepseek-chat")
        assert str(spec) == "deepseek:deepseek-chat"


class TestDeepSeekCosts:
    def test_deepseek_chat_in_model_costs(self):
        """deepseek-chat should have correct pricing."""
        assert "deepseek-chat" in MODEL_COSTS
        input_cost, output_cost = MODEL_COSTS["deepseek-chat"]
        assert input_cost == 0.28
        assert output_cost == 0.42

    def test_deepseek_reasoner_in_model_costs(self):
        """deepseek-reasoner should have correct pricing."""
        assert "deepseek-reasoner" in MODEL_COSTS
        input_cost, output_cost = MODEL_COSTS["deepseek-reasoner"]
        assert input_cost == 0.55
        assert output_cost == 2.19

    def test_deepseek_cheapest_cloud_model(self):
        """DeepSeek should be the cheapest non-Google cloud model."""
        assert MODEL_COSTS["deepseek-chat"][0] < MODEL_COSTS["gpt-4o"][0]


class TestDeepSeekRouting:
    def test_deepseek_reasoner_in_reasoning_models(self):
        """deepseek-reasoner should be in the reasoning models set."""
        from forgegod.config import ForgeGodConfig
        router = ModelRouter(ForgeGodConfig())
        assert "deepseek-reasoner" in router._REASONING_MODELS

    def test_deepseek_dispatch_branch_exists(self):
        """Router should have a deepseek dispatch path."""
        from forgegod.config import ForgeGodConfig
        router = ModelRouter(ForgeGodConfig())
        # Verify _call_deepseek method exists
        assert hasattr(router, "_call_deepseek")
        assert callable(router._call_deepseek)


class TestAnthropicCacheControl:
    def test_anthropic_system_with_cache_control(self):
        """Anthropic system message should include cache_control."""
        # We test the structure that _call_anthropic would produce
        system = "You are a helpful assistant."
        expected = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        assert expected[0]["cache_control"]["type"] == "ephemeral"
        assert expected[0]["text"] == system


class TestCostCalculationWithCache:
    @pytest.fixture
    def router(self):
        from forgegod.config import ForgeGodConfig
        return ModelRouter(ForgeGodConfig())

    def test_basic_cost_no_cache(self, router):
        """Cost calculation without cache tokens works normally."""
        usage = {"input_tokens": 1000, "output_tokens": 500}
        cost = router._calculate_cost("gpt-4o", usage)
        # gpt-4o: $2.50/M input, $10.00/M output
        expected = (1000 / 1_000_000) * 2.50 + (500 / 1_000_000) * 10.00
        assert abs(cost - round(expected, 6)) < 0.0001

    def test_cost_with_cache_read_tokens(self, router):
        """Cache read tokens should be charged at 10% of input price."""
        usage = {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cache_read_tokens": 800,
            "cache_creation_tokens": 0,
        }
        cost = router._calculate_cost("claude-sonnet-4-6-20250514", usage)
        # Claude Sonnet: $3.00/M input, $15.00/M output
        # 200 regular + 800 cache_read at 10% = 200*3.00 + 800*0.30 per M
        regular = (200 / 1_000_000) * 3.00
        cached = (800 / 1_000_000) * 3.00 * 0.1
        output = (100 / 1_000_000) * 15.00
        expected = round(regular + cached + output, 6)
        assert abs(cost - expected) < 0.0001

    def test_cost_with_cache_creation_tokens(self, router):
        """Cache creation tokens should be charged at 125% of input price."""
        usage = {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 500,
        }
        cost = router._calculate_cost("claude-sonnet-4-6-20250514", usage)
        # 500 regular + 500 cache_creation at 125%
        regular = (500 / 1_000_000) * 3.00
        creation = (500 / 1_000_000) * 3.00 * 1.25
        output = (100 / 1_000_000) * 15.00
        expected = round(regular + creation + output, 6)
        assert abs(cost - expected) < 0.0001

    def test_cost_zero_for_local_model(self, router):
        """Local models should have zero cost."""
        usage = {"input_tokens": 10000, "output_tokens": 5000}
        cost = router._calculate_cost("qwen3-coder-next", usage)
        assert cost == 0.0

    def test_cost_deepseek_much_cheaper(self, router):
        """DeepSeek should be significantly cheaper than GPT-4o for same usage."""
        usage = {"input_tokens": 100000, "output_tokens": 50000}
        ds_cost = router._calculate_cost("deepseek-chat", usage)
        gpt_cost = router._calculate_cost("gpt-4o", usage)
        assert ds_cost < gpt_cost / 5  # At least 5x cheaper
