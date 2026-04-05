"""ForgeGod Model Router — multi-provider with circuit breaker and fallback.

Ported from forge/forge_llm.py (Phase 80, 5-tier cascade).
Adapted: Redis → local tracking, MiniMax → OpenAI, added OpenRouter.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from forgegod.config import MODEL_COSTS, ForgeGodConfig
from forgegod.models import BudgetMode, ModelSpec, ModelUsage

logger = logging.getLogger("forgegod.router")


class CircuitBreaker:
    """Per-provider circuit breaker — prevents hammering a down provider."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def is_open(self, provider: str) -> bool:
        if provider not in self._open_until:
            return False
        if time.time() > self._open_until[provider]:
            self._failures[provider] = 0
            del self._open_until[provider]
            return False
        return True

    def record_failure(self, provider: str):
        self._failures[provider] = self._failures.get(provider, 0) + 1
        if self._failures[provider] >= self.failure_threshold:
            self._open_until[provider] = time.time() + self.reset_timeout
            logger.warning(f"Circuit breaker OPEN for {provider}")

    def record_success(self, provider: str):
        self._failures[provider] = 0
        self._open_until.pop(provider, None)


# Role → fallback chain (most expensive last)
FALLBACK_CHAINS: dict[str, list[str]] = {
    "planner": ["planner", "coder"],
    "coder": ["coder", "reviewer", "escalation"],
    "reviewer": ["reviewer", "sentinel", "escalation"],
    "sentinel": ["sentinel", "escalation"],
    "escalation": ["escalation"],
    "researcher": ["researcher", "planner", "coder"],
}


class ModelRouter:
    """Unified LLM client — routes by role, falls back on failure, tracks cost."""

    def __init__(self, config: ForgeGodConfig):
        self.config = config
        self.circuit = CircuitBreaker()
        self._total_cost = 0.0
        self._call_log: list[dict] = []

    async def call(
        self,
        prompt: str | list[dict],
        role: str = "coder",
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[dict] | None = None,
    ) -> tuple[str, ModelUsage]:
        """Call an LLM with automatic role-based routing and fallback.

        Args:
            prompt: Either a string or a list of message dicts.
            role: One of planner|coder|reviewer|sentinel|escalation.
            system: System prompt.
            json_mode: Request JSON output.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
            tools: OpenAI-format tool definitions for function calling.

        Returns:
            (response_text, usage)
        """
        # Budget check
        if self.config.budget.mode == BudgetMode.HALT:
            return "[BUDGET HALT: All LLM calls paused]", ModelUsage()

        if self.config.budget.mode == BudgetMode.LOCAL_ONLY:
            spec = ModelSpec(provider="ollama", model=self.config.ollama.model)
            return await self._call_single(
                spec, prompt, system, json_mode, max_tokens, temperature, tools
            )

        # Build fallback chain from role config
        chain = FALLBACK_CHAINS.get(role, ["coder", "escalation"])
        specs = []
        for r in chain:
            model_str = getattr(self.config.models, r, None)
            if model_str:
                specs.append(ModelSpec.parse(model_str))

        # Throttle mode: prepend local model
        if self.config.budget.mode == BudgetMode.THROTTLE:
            local = ModelSpec(provider="ollama", model=self.config.ollama.model)
            specs.insert(0, local)

        last_error = ""
        for spec in specs:
            if self.circuit.is_open(spec.provider):
                continue

            try:
                return await self._call_single(
                    spec, prompt, system, json_mode, max_tokens, temperature, tools
                )
            except Exception as e:
                last_error = str(e)
                self.circuit.record_failure(spec.provider)
                logger.warning(f"{spec} failed: {e}, trying next")

        logger.error(f"All models failed for role={role}. Last: {last_error}")
        return (
            f"[ERROR: All models failed for role={role}.\n"
            f"  Last error: {last_error}\n"
            f"  Fix: Check `forgegod doctor` or try a different model with --model]"
        ), ModelUsage()

    async def _call_single(
        self,
        spec: ModelSpec,
        prompt: str | list[dict],
        system: str,
        json_mode: bool,
        max_tokens: int,
        temperature: float,
        tools: list[dict] | None,
    ) -> tuple[str, ModelUsage]:
        """Call a single model. Returns (text, usage)."""
        start = time.time()

        if spec.provider == "ollama":
            text, usage_dict = await self._call_ollama(
                spec.model, prompt, system, max_tokens, temperature, tools
            )
        elif spec.provider == "openai":
            text, usage_dict = await self._call_openai(
                spec.model, prompt, system, json_mode, max_tokens, temperature, tools
            )
        elif spec.provider == "anthropic":
            text, usage_dict = await self._call_anthropic(
                spec.model, prompt, system, json_mode, max_tokens, temperature, tools
            )
        elif spec.provider == "openrouter":
            text, usage_dict = await self._call_openrouter(
                spec.model, prompt, system, json_mode, max_tokens, temperature, tools
            )
        elif spec.provider == "gemini":
            text, usage_dict = await self._call_gemini(
                spec.model, prompt, system, json_mode, max_tokens, temperature, tools
            )
        elif spec.provider == "deepseek":
            text, usage_dict = await self._call_deepseek(
                spec.model, prompt, system, json_mode, max_tokens, temperature, tools
            )
        else:
            raise ValueError(f"Unknown provider: {spec.provider}")

        elapsed = time.time() - start
        self.circuit.record_success(spec.provider)

        cost = self._calculate_cost(spec.model, usage_dict)
        usage = ModelUsage(
            input_tokens=usage_dict.get("input_tokens", 0),
            output_tokens=usage_dict.get("output_tokens", 0),
            cost_usd=cost,
            model=spec.model,
            provider=spec.provider,
            elapsed_s=round(elapsed, 2),
        )
        self._total_cost += cost
        self._call_log.append({"spec": str(spec), "usage": usage.model_dump()})

        return text, usage

    # ── Provider Implementations ──

    async def _call_ollama(
        self, model: str, prompt: str | list[dict], system: str,
        max_tokens: int, temperature: float,
        tools: list[dict] | None = None,
    ) -> tuple[str, dict]:
        messages = self._to_messages(prompt, system)
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            # Qwen3.5 thinking mode: slower but needed for multi-step tool workflows
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }

        # Ollama tool use (Qwen3, Llama 3.1+, Mistral support function calling)
        if tools:
            ollama_tools = []
            for t in tools:
                fn = t.get("function", {})
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {}),
                    },
                })
            body["tools"] = ollama_tools

        async with httpx.AsyncClient(timeout=self.config.ollama.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.config.ollama.host}/api/chat",
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError as e:
                raise RuntimeError(
                    f"error: Cannot connect to Ollama at {self.config.ollama.host}\n"
                    f"  Ollama doesn't appear to be running.\n"
                    f"  Fix: Start it with `ollama serve`, then retry."
                ) from e
            except httpx.TimeoutException as e:
                raise RuntimeError(
                    f"error: Ollama request timed out after {self.config.ollama.timeout}s\n"
                    f"  The model may still be loading into memory.\n"
                    f"  Fix: Wait a moment and retry, or increase timeout in .forgegod/config.toml"
                ) from e

        msg = data.get("message", {})
        content = msg.get("content", "")

        # Handle Ollama tool calls
        tool_calls_raw = msg.get("tool_calls", [])
        if tool_calls_raw:
            tool_calls_json = []
            for i, tc in enumerate(tool_calls_raw):
                fn = tc.get("function", {})
                tool_calls_json.append({
                    "id": f"ollama_call_{i}",
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", {}),
                })
            content = json.dumps({"tool_calls": tool_calls_json})
        else:
            # Strip think tags from reasoning models (Qwen3 think mode)
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        return content, {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
        }

    # Reasoning models that need special handling
    _REASONING_MODELS = {
        "o3", "o3-mini", "o4-mini", "o1", "o1-mini",
        "o1-preview", "deepseek-reasoner",
    }

    async def _call_openai(
        self, model: str, prompt: str | list[dict], system: str,
        json_mode: bool, max_tokens: int, temperature: float,
        tools: list[dict] | None,
    ) -> tuple[str, dict]:
        import openai

        is_reasoning = model in self._REASONING_MODELS

        # Reasoning models: no temperature, no system role, use max_completion_tokens
        if is_reasoning:
            messages = self._to_messages(prompt, "")
            # Prepend system content as user message for reasoning models
            if system:
                messages.insert(0, {"role": "user", "content": f"[System context]\n{system}"})
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
            }
        else:
            messages = self._to_messages(prompt, system)
            kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools

        client = openai.AsyncOpenAI()
        resp = await client.chat.completions.create(**kwargs)

        choice = resp.choices[0]
        # Handle tool calls
        if choice.message.tool_calls:
            tool_calls_json = []
            for tc in choice.message.tool_calls:
                tool_calls_json.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
            content = json.dumps({"tool_calls": tool_calls_json})
        else:
            content = choice.message.content or ""

        usage_data = {
            "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        # Reasoning models report reasoning tokens separately
        if is_reasoning and resp.usage and hasattr(resp.usage, "completion_tokens_details"):
            details = resp.usage.completion_tokens_details
            if details and hasattr(details, "reasoning_tokens"):
                usage_data["reasoning_tokens"] = details.reasoning_tokens

        return content, usage_data

    async def _call_anthropic(
        self, model: str, prompt: str | list[dict], system: str,
        json_mode: bool, max_tokens: int, temperature: float,
        tools: list[dict] | None = None,
    ) -> tuple[str, dict]:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("Install anthropic: pip install 'forgegod[anthropic]'")

        messages = self._to_messages(prompt, "")  # Anthropic uses separate system param

        client = anthropic.AsyncAnthropic()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            # Prompt caching: mark system prompt as cacheable (90% discount on reads)
            kwargs["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]

        # Convert OpenAI tool format to Anthropic format
        if tools:
            anthropic_tools = []
            for t in tools:
                fn = t.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                })
            kwargs["tools"] = anthropic_tools

        resp = await client.messages.create(**kwargs)

        # Parse response — handle both text and tool_use blocks
        content = ""
        tool_calls_json = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls_json.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        if tool_calls_json:
            content = json.dumps({"tool_calls": tool_calls_json})

        # Include cache stats if available
        usage_data = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
        if hasattr(resp.usage, "cache_creation_input_tokens"):
            usage_data["cache_creation_tokens"] = resp.usage.cache_creation_input_tokens
        if hasattr(resp.usage, "cache_read_input_tokens"):
            usage_data["cache_read_tokens"] = resp.usage.cache_read_input_tokens

        return content, usage_data

    async def _call_openrouter(
        self, model: str, prompt: str | list[dict], system: str,
        json_mode: bool, max_tokens: int, temperature: float,
        tools: list[dict] | None,
    ) -> tuple[str, dict]:
        import os

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")

        messages = self._to_messages(prompt, system)
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if tools:
            body["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content", "")

        # Handle OpenRouter tool calls (OpenAI-compatible format)
        tool_calls_raw = msg.get("tool_calls", [])
        if tool_calls_raw:
            tool_calls_json = []
            for tc in tool_calls_raw:
                fn = tc.get("function", {})
                tool_calls_json.append({
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                })
            content = json.dumps({"tool_calls": tool_calls_json})

        usage = data.get("usage", {})
        return content, {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

    async def _call_gemini(
        self, model: str, prompt: str | list[dict], system: str,
        json_mode: bool, max_tokens: int, temperature: float,
        tools: list[dict] | None,
    ) -> tuple[str, dict]:
        """Call Google Gemini via OpenAI-compatible endpoint."""
        import os

        import openai

        api_key = (
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY", "")
        )
        if not api_key:
            raise RuntimeError(
                "error: No Google API key set.\n"
                "  Fix: export GOOGLE_API_KEY=AIza... or GEMINI_API_KEY=AIza...\n"
                "  Get one at: https://aistudio.google.com/app/apikey"
            )

        messages = self._to_messages(prompt, system)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        resp = await client.chat.completions.create(**kwargs)

        choice = resp.choices[0]
        if choice.message.tool_calls:
            tool_calls_json = []
            for tc in choice.message.tool_calls:
                tool_calls_json.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
            content = json.dumps({"tool_calls": tool_calls_json})
        else:
            content = choice.message.content or ""

        usage_data = {
            "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        return content, usage_data

    async def _call_deepseek(
        self, model: str, prompt: str | list[dict], system: str,
        json_mode: bool, max_tokens: int, temperature: float,
        tools: list[dict] | None,
    ) -> tuple[str, dict]:
        """Call DeepSeek via OpenAI-compatible API. 22x cheaper than GPT-4o."""
        import os

        import openai

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "error: No DeepSeek API key set.\n"
                "  Fix: export DEEPSEEK_API_KEY=sk-...\n"
                "  Get one at: https://platform.deepseek.com/api_keys"
            )

        is_reasoning = model in self._REASONING_MODELS

        if is_reasoning:
            messages = self._to_messages(prompt, "")
            if system:
                messages.insert(0, {"role": "user", "content": f"[System context]\n{system}"})
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
            }
        else:
            messages = self._to_messages(prompt, system)
            kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

        if json_mode and not is_reasoning:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        resp = await client.chat.completions.create(**kwargs)

        choice = resp.choices[0]
        if choice.message.tool_calls:
            tool_calls_json = []
            for tc in choice.message.tool_calls:
                tool_calls_json.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
            content = json.dumps({"tool_calls": tool_calls_json})
        else:
            content = choice.message.content or ""
            # Strip thinking tags from deepseek-reasoner
            if is_reasoning:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        usage_data = {
            "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        if is_reasoning and resp.usage and hasattr(resp.usage, "completion_tokens_details"):
            details = resp.usage.completion_tokens_details
            if details and hasattr(details, "reasoning_tokens"):
                usage_data["reasoning_tokens"] = details.reasoning_tokens

        return content, usage_data

    # ── Helpers ──

    def _to_messages(self, prompt: str | list[dict], system: str) -> list[dict]:
        if isinstance(prompt, list):
            messages = list(prompt)
            if system and (not messages or messages[0].get("role") != "system"):
                messages.insert(0, {"role": "system", "content": system})
            return messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _calculate_cost(self, model: str, usage: dict) -> float:
        costs = MODEL_COSTS.get(model, (0, 0))
        input_price, output_price = costs

        # Base input/output cost
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Anthropic prompt caching: cache reads at 10% price, creation at 125%
        cache_read = usage.get("cache_read_tokens", 0)
        cache_creation = usage.get("cache_creation_tokens", 0)
        # Subtract cached tokens from base input (they're priced separately)
        regular_input = max(0, input_tokens - cache_read - cache_creation)

        input_cost = (regular_input / 1_000_000) * input_price
        input_cost += (cache_read / 1_000_000) * input_price * 0.1
        input_cost += (cache_creation / 1_000_000) * input_price * 1.25
        output_cost = (output_tokens / 1_000_000) * output_price

        return round(input_cost + output_cost, 6)

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def call_count(self) -> int:
        return len(self._call_log)
