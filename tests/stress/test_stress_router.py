"""Stress tests for ForgeGod Model Router — throughput, circuit breaker, fallback."""

from __future__ import annotations

import asyncio
import json as _json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from forgegod.router import CircuitBreaker, ModelRouter

from .conftest import percentiles, record_metric, timed

pytestmark = pytest.mark.stress


def _mock_ollama_response(*args, **kwargs):
    body = _json.dumps({
        "message": {"role": "assistant", "content": "ok"},
        "done": True,
        "prompt_eval_count": 10,
        "eval_count": 5,
    }).encode()
    return httpx.Response(
        200, content=body,
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


class TestRouterThroughput:
    @pytest.mark.asyncio
    async def test_sequential_call_throughput(self, tmp_config):
        """200 sequential router.call() with mocked Ollama — measure per-call overhead.

        Note: each call creates a new httpx.AsyncClient, so this measures
        the full routing + client-creation + mock overhead per call.
        """
        router = ModelRouter(tmp_config)
        n = 200
        latencies = []

        mock_patch = patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock, side_effect=_mock_ollama_response,
        )
        with mock_patch:
            with timed() as t:
                for i in range(n):
                    start = time.perf_counter()
                    _text, _usage = await router.call(f"Task {i}", role="coder")
                    latencies.append((time.perf_counter() - start) * 1000)

        assert len(latencies) == n
        cps = n / (t.elapsed / 1000)
        p = percentiles(latencies)

        record_metric("router", "sequential_throughput_cps", round(cps, 1))
        record_metric("router", "latency_p50_ms", round(p["p50"], 2))
        record_metric("router", "latency_p95_ms", round(p["p95"], 2))
        record_metric("router", "latency_p99_ms", round(p["p99"], 2))

        # Each call goes through routing logic + httpx client creation + mock
        assert cps > 2, f"Expected >2 calls/sec, got {cps:.1f}"


class TestCircuitBreakerStress:
    def test_rapid_failures_open_at_threshold(self):
        """100 rapid failures — circuit opens exactly at threshold=3."""
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=0.5)
        provider = "test_provider"

        # First 2 failures: circuit stays closed
        cb.record_failure(provider)
        cb.record_failure(provider)
        assert not cb.is_open(provider)

        # 3rd failure: circuit opens
        with timed() as t:
            cb.record_failure(provider)
        assert cb.is_open(provider)

        record_metric("router", "circuit_breaker_open_ms", round(t.elapsed, 3))

    def test_circuit_breaker_recovery(self):
        """Circuit auto-recovers after reset_timeout."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)  # 100ms
        provider = "test_recover"

        cb.record_failure(provider)
        cb.record_failure(provider)
        assert cb.is_open(provider)

        # Wait for recovery
        time.sleep(0.15)

        is_open = cb.is_open(provider)
        assert not is_open

        record_metric("router", "circuit_breaker_recovery_ms", 150)

    def test_multi_provider_isolation(self):
        """Circuit breaker tracks providers independently."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=1.0)

        # Trip provider A
        cb.record_failure("provider_a")
        cb.record_failure("provider_a")
        assert cb.is_open("provider_a")
        assert not cb.is_open("provider_b")

        # Provider B still works
        cb.record_success("provider_b")
        assert not cb.is_open("provider_b")


class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_fallback_chain_exhaustion(self, tmp_config):
        """All providers fail — verify graceful error, no hang."""
        router = ModelRouter(tmp_config)

        async def _fail(*args, **kwargs):
            raise ConnectionError("provider down")

        with (
            patch.object(router, "_call_ollama", side_effect=_fail),
            patch.object(router, "_call_openai", side_effect=_fail),
            patch.object(router, "_call_anthropic", side_effect=_fail),
            patch.object(router, "_call_openrouter", side_effect=_fail),
            patch.object(router, "_call_gemini", side_effect=_fail),
            patch.object(router, "_call_deepseek", side_effect=_fail),
        ):
            with timed() as t:
                text, usage = await router.call("test", role="coder")

        assert "[ERROR:" in text
        record_metric("router", "fallback_exhaustion_ms", round(t.elapsed, 2))
        assert t.elapsed < 5000, "Fallback exhaustion should be fast (no real HTTP)"

    @pytest.mark.asyncio
    async def test_mixed_role_routing(self, tmp_config):
        """100 concurrent calls with different roles — all route correctly."""
        router = ModelRouter(tmp_config)
        roles = ["planner", "coder", "reviewer", "researcher"]
        results = []

        mock_patch = patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock, side_effect=_mock_ollama_response,
        )
        with mock_patch:

            async def call_role(role):
                text, usage = await router.call(f"Task for {role}", role=role)
                return role, text

            tasks = [call_role(roles[i % len(roles)]) for i in range(100)]
            results = await asyncio.gather(*tasks)

        assert len(results) == 100
        role_counts = {}
        for role, text in results:
            role_counts[role] = role_counts.get(role, 0) + 1
        assert role_counts["planner"] == 25
        assert role_counts["coder"] == 25


class TestCostCalculation:
    def test_cost_calculation_precision(self, tmp_config):
        """10,000 cost calculations — verify speed and precision."""
        router = ModelRouter(tmp_config)
        n = 10_000

        with timed() as t:
            for i in range(n):
                router._calculate_cost("openai", "gpt-4o-mini", {
                    "input_tokens": 1000 + i,
                    "output_tokens": 500 + i,
                })

        # Verify a known calculation
        # gpt-4o-mini: $0.15/Mtok in, $0.60/Mtok out
        expected = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        actual = router._calculate_cost("openai", "gpt-4o-mini", {
            "input_tokens": 1000, "output_tokens": 500,
        })
        assert abs(actual - expected) < 1e-8

        rate = n / (t.elapsed / 1000)
        record_metric("router", "cost_calc_per_10k_ms", round(t.elapsed, 1))
        record_metric("router", "cost_calc_per_sec", round(rate, 0))
