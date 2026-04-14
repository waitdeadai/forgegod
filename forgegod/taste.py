"""ForgeGod Taste Agent — adversarial design director integration.

This module provides the ForgeGod-side integration for the taste-agent package.
It handles:
- Config detection from .forgegod/config.toml
- Running taste evaluation after reviewer approval
- Memory sync with ForgeGod's existing memory system

The actual taste evaluation is delegated to the taste_agent package if installed,
otherwise this module provides a no-op fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from forgegod.config import ForgeGodConfig

if TYPE_CHECKING:
    from forgegod.router import ModelRouter

logger = logging.getLogger("forgegod.taste")


class TasteVerdict:
    """Taste verdict — mirrors taste_agent VERDICT."""

    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


class TasteResult:
    """Taste evaluation result — mirrors taste_agent EvaluationResult."""

    def __init__(
        self,
        verdict: str = TasteVerdict.APPROVE,
        overall_score: float = 1.0,
        reasoning: str = "",
        issues: list | None = None,
        suggestions: list | None = None,
        revision_guidance: str = "",
        model_used: str = "",
        cost_usd: float = 0.0,
        latency_ms: int = 0,
    ):
        self.verdict = verdict
        self.overall_score = overall_score
        self.reasoning = reasoning
        self.issues = issues or []
        self.suggestions = suggestions or []
        self.revision_guidance = revision_guidance
        self.model_used = model_used
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms

    @classmethod
    def skip(cls) -> "TasteResult":
        """Return a skipped result (taste disabled)."""
        return cls(verdict=TasteVerdict.APPROVE, reasoning="Taste disabled — skipped.")

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "overall_score": self.overall_score,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "revision_guidance": self.revision_guidance,
            "model_used": self.model_used,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
        }


class TasteAgent:
    """ForgeGod taste agent — wraps taste_agent package.

    Falls back to no-op if taste_agent is not installed.
    """

    def __init__(
        self,
        config: ForgeGodConfig,
        router: "ModelRouter | None" = None,
    ):
        self.config = config
        self.router = router
        self._enabled = config.taste.enabled
        self._impl = None
        self._load_impl()

    def _load_impl(self) -> None:
        """Try to load the taste_agent package."""
        if not self._enabled:
            return
        try:
            # Import the standalone taste_agent package
            from taste_agent import TasteAgent as ExternalTasteAgent
            from taste_agent import TasteConfig as ExternalTasteConfig

            external_config = ExternalTasteConfig(
                enabled=True,
                model=self.config.taste.model,
                taste_spec_path=self.config.taste.taste_spec_path,
                memory_path=self.config.taste.memory_path,
                memory_scope=self.config.taste.memory_scope,
                require_taste_md=self.config.taste.require_taste_md,
                auto_approve_threshold=self.config.taste.auto_approve_threshold,
                max_revision_cycles=self.config.taste.max_revision_cycles,
            )
            self._impl = ExternalTasteAgent(
                config=external_config,
                project_root=str(self.config.project_dir.parent),
            )
            logger.debug("taste-agent package loaded successfully")
        except ImportError as e:
            logger.warning(
                f"taste-agent package not installed. "
                f"Taste evaluation disabled. Install with: pip install taste-agent. "
                f"Error: {e}"
            )
            self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._impl is not None

    @property
    def has_taste_spec(self) -> bool:
        if not self.is_enabled:
            return False
        return self._impl.has_taste_spec

    async def evaluate(
        self,
        task: str,
        output_files: list[str] | None = None,
        file_contents: dict[str, str] | None = None,
        diff: str = "",
        **kwargs,
    ) -> TasteResult:
        """Run taste evaluation.

        Args:
            task: The original task description.
            output_files: List of files modified.
            file_contents: Dict of filename -> content.
            diff: Optional git diff string.

        Returns:
            TasteResult with verdict and feedback.
        """
        if not self.is_enabled:
            return TasteResult.skip()

        try:
            result = await self._impl.evaluate(
                task=task,
                output_files=output_files or [],
                file_contents=file_contents or {},
                diff=diff,
                **kwargs,
            )
            return TasteResult(
                verdict=result.verdict,
                overall_score=result.overall_score,
                reasoning=result.reasoning,
                issues=[i.get("problem", "") for i in result.issues] if result.issues else [],
                suggestions=result.principles_learned,
                revision_guidance=result.revision_guidance,
                model_used=result.model_used,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
            )
        except Exception as e:
            logger.warning(f"Taste evaluation failed: {e}")
            return TasteResult(
                verdict=TasteVerdict.REVISE,
                reasoning=f"Taste evaluation error: {e}",
            )

    def discover_taste_md(self) -> Path | None:
        """Discover taste.md path by upward search from project root."""
        if not self.is_enabled:
            return None
        spec_path = self.config.project_dir.parent / self.config.taste.taste_spec_path
        return spec_path if spec_path.exists() else None

    def discover_taste_memory(self) -> Path | None:
        """Discover taste.memory path."""
        if not self.is_enabled:
            return None
        if self.config.taste.memory_scope == "global":
            memory_path = self.config.global_dir / "taste.memory"
        else:
            memory_path = self.config.project_dir.parent / self.config.taste.memory_path
        return memory_path if memory_path.exists() else None
