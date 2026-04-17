from __future__ import annotations

import sys
import types

from forgegod.config import ForgeGodConfig
from forgegod.taste import TasteAgent, TasteVerdict


def test_taste_disabled_skips_cleanly():
    config = ForgeGodConfig()
    config.taste.enabled = False

    agent = TasteAgent(config=config)

    assert agent.is_enabled is False


def test_taste_missing_package_disables(monkeypatch):
    config = ForgeGodConfig()
    config.taste.enabled = True

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "taste_agent":
            raise ImportError("missing taste_agent")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    agent = TasteAgent(config=config)

    assert agent.is_enabled is False


async def _fake_taste_evaluate(**_kwargs):
    return types.SimpleNamespace(
        verdict=TasteVerdict.REVISE,
        overall_score=0.72,
        reasoning="Needs polish",
        issues=[{"problem": "Weak hierarchy"}, "Spacing drift"],
        principles_learned=["Tighter spacing", "Stronger focal point"],
        revision_guidance="Improve the hero rhythm",
        model_used="zai:glm-5.1",
        cost_usd=0.04,
        latency_ms=2100,
    )


def test_taste_maps_external_result(monkeypatch):
    module = types.ModuleType("taste_agent")

    class ExternalTasteConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class ExternalTasteAgent:
        def __init__(self, config, project_root):
            self.config = config
            self.project_root = project_root
            self.has_taste_spec = True

        evaluate = staticmethod(_fake_taste_evaluate)

    module.TasteAgent = ExternalTasteAgent
    module.TasteConfig = ExternalTasteConfig
    monkeypatch.setitem(sys.modules, "taste_agent", module)

    config = ForgeGodConfig()
    config.taste.enabled = True
    agent = TasteAgent(config=config)

    result = __import__("asyncio").run(agent.evaluate(task="Refine landing page"))

    assert agent.is_enabled is True
    assert result.verdict == TasteVerdict.REVISE
    assert result.issues == ["Weak hierarchy", "Spacing drift"]
    assert result.suggestions == ["Tighter spacing", "Stronger focal point"]
    assert result.model_used == "zai:glm-5.1"
