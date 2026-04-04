"""Tests for Google Gemini provider integration."""

import pytest

from forgegod.config import MODEL_COSTS, ForgeGodConfig
from forgegod.models import ModelSpec


def test_model_spec_parse_gemini():
    """gemini:gemini-2.5-pro parses correctly."""
    spec = ModelSpec.parse("gemini:gemini-2.5-pro")
    assert spec.provider == "gemini"
    assert spec.model == "gemini-2.5-pro"
    assert str(spec) == "gemini:gemini-2.5-pro"


def test_model_spec_parse_gemini_flash():
    """gemini:gemini-3-flash parses correctly."""
    spec = ModelSpec.parse("gemini:gemini-3-flash")
    assert spec.provider == "gemini"
    assert spec.model == "gemini-3-flash"


def test_gemini_costs_in_model_costs():
    """Gemini models exist in MODEL_COSTS."""
    assert "gemini-2.5-pro" in MODEL_COSTS
    assert "gemini-2.5-flash" in MODEL_COSTS
    assert "gemini-3-flash" in MODEL_COSTS
    assert "gemini-3-pro" in MODEL_COSTS

    # Verify cost tuple structure (input, output per 1M tokens)
    cost = MODEL_COSTS["gemini-2.5-pro"]
    assert len(cost) == 2
    assert cost[0] == 1.25  # input
    assert cost[1] == 5.00  # output


def test_gemini_config_defaults():
    """GeminiConfig defaults correct."""
    config = ForgeGodConfig()
    assert config.gemini.timeout == 120.0


def test_gemini_provider_routing():
    """Router dispatches to _call_gemini for gemini provider."""
    from forgegod.router import ModelRouter

    config = ForgeGodConfig()
    router = ModelRouter(config)

    # Verify _call_gemini method exists
    assert hasattr(router, "_call_gemini")
    assert callable(router._call_gemini)


@pytest.mark.asyncio
async def test_gemini_missing_api_key(monkeypatch):
    """Raises RuntimeError when no Gemini key set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    from forgegod.router import ModelRouter

    config = ForgeGodConfig()
    router = ModelRouter(config)

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        await router._call_gemini(
            model="gemini-2.5-pro",
            prompt="test",
            system="",
            json_mode=False,
            max_tokens=100,
            temperature=0.3,
            tools=None,
        )
