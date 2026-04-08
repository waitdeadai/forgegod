"""Tests for Z.AI / GLM provider integration."""

import pytest

from forgegod.config import MODEL_COSTS, ForgeGodConfig
from forgegod.models import ModelSpec


def test_model_spec_parse_zai():
    spec = ModelSpec.parse("zai:glm-5.1")
    assert spec.provider == "zai"
    assert spec.model == "glm-5.1"
    assert str(spec) == "zai:glm-5.1"


def test_zai_costs_in_model_costs():
    assert MODEL_COSTS["glm-5.1"] == (1.40, 4.40)
    assert MODEL_COSTS["glm-5"] == (1.00, 3.20)
    assert MODEL_COSTS["glm-4.7"] == (0.60, 2.20)


def test_zai_config_defaults():
    config = ForgeGodConfig()
    assert config.zai.timeout == 120.0
    assert config.zai.base_url == "https://api.z.ai/api/paas/v4"
    assert config.zai.coding_plan_base_url == "https://api.z.ai/api/coding/paas/v4"
    assert config.zai.use_coding_plan is True


def test_zai_provider_routing():
    from forgegod.router import ModelRouter

    router = ModelRouter(ForgeGodConfig())
    assert hasattr(router, "_call_zai")
    assert callable(router._call_zai)


@pytest.mark.asyncio
async def test_zai_missing_api_key(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_CODING_API_KEY", raising=False)

    from forgegod.router import ModelRouter

    router = ModelRouter(ForgeGodConfig())

    with pytest.raises(RuntimeError, match="ZAI_CODING_API_KEY or ZAI_API_KEY"):
        await router._call_zai(
            model="glm-5.1",
            prompt="test",
            system="",
            json_mode=False,
            max_tokens=100,
            temperature=0.3,
            tools=None,
        )
