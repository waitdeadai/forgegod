"""Tests for OpenAI Codex subscription-backed provider integration."""

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.models import ModelSpec


def test_model_spec_parse_openai_codex():
    spec = ModelSpec.parse("openai-codex:gpt-5.4")
    assert spec.provider == "openai-codex"
    assert spec.model == "gpt-5.4"
    assert str(spec) == "openai-codex:gpt-5.4"


def test_openai_codex_config_defaults():
    config = ForgeGodConfig()
    assert config.openai_codex.command == "codex"
    assert config.openai_codex.timeout == 180.0
    assert config.openai_codex.sandbox == "read-only"
    assert config.openai_codex.ephemeral is True


def test_openai_codex_provider_routing():
    from forgegod.router import ModelRouter

    router = ModelRouter(ForgeGodConfig())
    assert hasattr(router, "_call_openai_codex")
    assert callable(router._call_openai_codex)


def test_openai_codex_subscription_cost_is_zero():
    from forgegod.router import ModelRouter

    router = ModelRouter(ForgeGodConfig())
    assert router._calculate_cost(
        "openai-codex",
        "gpt-5.4",
        {"input_tokens": 1000, "output_tokens": 500, "subscription_billing": True},
    ) == 0.0


@pytest.mark.asyncio
async def test_openai_codex_missing_login(monkeypatch):
    from forgegod.router import ModelRouter

    async def fake_status(command: str = "codex"):
        return False, "Not logged in"

    monkeypatch.setattr("forgegod.router.codex_automation_status", lambda: (True, "ok"))
    monkeypatch.setattr("forgegod.router.codex_login_status", fake_status)

    router = ModelRouter(ForgeGodConfig())

    with pytest.raises(RuntimeError, match="codex login"):
        await router._call_openai_codex(
            model="gpt-5.4",
            prompt="test",
            system="",
            json_mode=False,
            max_tokens=100,
            temperature=0.3,
            tools=None,
        )


@pytest.mark.asyncio
async def test_openai_codex_blocks_native_windows_automation(monkeypatch):
    from forgegod.router import ModelRouter

    monkeypatch.setattr(
        "forgegod.router.codex_automation_status",
        lambda: (False, "Use WSL for best Windows experience"),
    )

    router = ModelRouter(ForgeGodConfig())

    with pytest.raises(RuntimeError, match="Use WSL"):
        await router._call_openai_codex(
            model="gpt-5.4",
            prompt="test",
            system="",
            json_mode=False,
            max_tokens=100,
            temperature=0.3,
            tools=None,
        )


@pytest.mark.asyncio
async def test_codex_login_status_reports_timeout(monkeypatch):
    from forgegod.native_auth import codex_login_status

    monkeypatch.setattr("forgegod.native_auth.find_command", lambda _command: "codex")

    async def fake_run_command(*_args, **_kwargs):
        raise RuntimeError("Command timed out after 20s: codex login status")

    monkeypatch.setattr("forgegod.native_auth.run_command", fake_run_command)

    ready, detail = await codex_login_status()
    assert ready is False
    assert "timed out" in detail
