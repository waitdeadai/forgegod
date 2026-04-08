"""Tests for Kimi / Moonshot provider integration."""

import pytest

from forgegod.config import MODEL_COSTS, ForgeGodConfig
from forgegod.models import ModelSpec


def test_model_spec_parse_kimi():
    """kimi:kimi-k2.5 parses correctly."""
    spec = ModelSpec.parse("kimi:kimi-k2.5")
    assert spec.provider == "kimi"
    assert spec.model == "kimi-k2.5"
    assert str(spec) == "kimi:kimi-k2.5"


def test_model_spec_parse_kimi_thinking():
    """kimi:kimi-k2-thinking parses correctly."""
    spec = ModelSpec.parse("kimi:kimi-k2-thinking")
    assert spec.provider == "kimi"
    assert spec.model == "kimi-k2-thinking"


def test_kimi_costs_in_model_costs():
    """Kimi models exist in MODEL_COSTS."""
    assert "kimi-k2.5" in MODEL_COSTS
    assert "kimi-k2-thinking" in MODEL_COSTS
    assert "kimi-k2-0905-preview" in MODEL_COSTS

    assert MODEL_COSTS["kimi-k2.5"] == (0.60, 3.00)
    assert MODEL_COSTS["kimi-k2-thinking"] == (0.60, 2.50)


def test_kimi_config_defaults():
    """KimiConfig defaults are correct."""
    config = ForgeGodConfig()
    assert config.kimi.timeout == 120.0
    assert config.kimi.base_url == "https://api.moonshot.ai/v1"


def test_kimi_provider_routing():
    """Router dispatches to _call_kimi for kimi provider."""
    from forgegod.router import ModelRouter

    router = ModelRouter(ForgeGodConfig())
    assert hasattr(router, "_call_kimi")
    assert callable(router._call_kimi)


@pytest.mark.asyncio
async def test_kimi_missing_api_key(monkeypatch):
    """Raises RuntimeError when no Moonshot key is set."""
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)

    from forgegod.router import ModelRouter

    router = ModelRouter(ForgeGodConfig())

    with pytest.raises(RuntimeError, match="MOONSHOT_API_KEY"):
        await router._call_kimi(
            model="kimi-k2.5",
            prompt="test",
            system="",
            json_mode=False,
            max_tokens=100,
            temperature=0.3,
            tools=None,
        )
