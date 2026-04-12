"""Tests for SOTA 2026 self-healing: stuck detection and auto-research triggers."""

from __future__ import annotations

import pytest

from forgegod.agent import STUCK_PATTERNS
from forgegod.config import ForgeGodConfig
from forgegod.models import (
    AutoResearchReason,
    ParallelismMode,
    ParallelismRecommendation,
    ResearchDepth,
)


class TestStuckPatterns:
    """STUCK_PATTERNS regex-based detection for self-healing trigger."""

    def test_spanish_stuck_no_puedo(self):
        """Spanish 'no puedo' phrase should trigger detection."""
        import re
        text = "no puedo continuar con la implementación"
        matched = any(re.search(p, text.lower()) for p in STUCK_PATTERNS)
        assert matched

    def test_english_stuck(self):
        """English 'stuck' phrase should trigger detection."""
        import re
        text = "I am stuck and cannot proceed"
        matched = any(re.search(p, text.lower()) for p in STUCK_PATTERNS)
        assert matched

    def test_cannot_proceed(self):
        """'cannot proceed' should trigger detection."""
        import re
        text = "I cannot proceed with the implementation"
        matched = any(re.search(p, text.lower()) for p in STUCK_PATTERNS)
        assert matched

    def test_dont_know(self):
        """'don't know' pattern should trigger detection."""
        import re
        text = "I don't know how to implement this"
        matched = any(re.search(p, text.lower()) for p in STUCK_PATTERNS)
        assert matched

    def test_blocked(self):
        """'blocked' pattern should trigger detection."""
        import re
        text = "I am blocked by a dependency issue"
        matched = any(re.search(p, text.lower()) for p in STUCK_PATTERNS)
        assert matched

    def test_not_sure(self):
        """'not sure' pattern should trigger detection."""
        import re
        text = "I'm not sure how to approach this"
        matched = any(re.search(p, text.lower()) for p in STUCK_PATTERNS)
        assert matched

    def test_no_false_positive_on_success(self):
        """Normal success output should not trigger stuck detection."""
        import re
        normal_outputs = [
            "Task completed successfully. All tests pass.",
            "I have implemented the feature and verified it works.",
            "The refactoring is complete.",
            "Analysis complete. Recommended approach: ...",
        ]
        for output in normal_outputs:
            for pattern in STUCK_PATTERNS:
                if re.search(pattern, output.lower()):
                    pytest.fail(
                        f"False positive: pattern {pattern!r} matched: {output}"
                    )


class TestAgentConfig:
    """AgentConfig defaults for SOTA 2026 research-first behavior."""

    def test_research_before_code_defaults_true(self):
        """research_before_code should default to True (SOTA 2026 mandatory)."""
        cfg = ForgeGodConfig()
        assert cfg.agent.research_before_code is True

    def test_auto_research_on_stuck_defaults_true(self):
        """auto_research_on_stuck should default to True."""
        cfg = ForgeGodConfig()
        assert cfg.agent.auto_research_on_stuck is True

    def test_auto_research_on_bad_review_defaults_true(self):
        """auto_research_on_bad_review should default to True."""
        cfg = ForgeGodConfig()
        assert cfg.agent.auto_research_on_bad_review is True

    def test_max_auto_research_per_task_default(self):
        """max_auto_research_per_task should be 3."""
        cfg = ForgeGodConfig()
        assert cfg.agent.max_auto_research_per_task == 3

    def test_research_depth_defaults(self):
        """Default research depths should be set correctly."""
        cfg = ForgeGodConfig()
        assert cfg.agent.research_depth_default == ResearchDepth.SOTA
        assert cfg.agent.research_depth_on_stuck == ResearchDepth.DEEP
        assert cfg.agent.research_depth_on_bad_review == ResearchDepth.SOTA


class TestResearchDepth:
    """ResearchDepth enum values."""

    def test_quick_depth(self):
        """QUICK research ~30s."""
        assert ResearchDepth.QUICK.value == "quick"

    def test_deep_depth(self):
        """DEEP research ~2min."""
        assert ResearchDepth.DEEP.value == "deep"

    def test_sota_depth(self):
        """SOTA research ~3min."""
        assert ResearchDepth.SOTA.value == "sota"


class TestAutoResearchReason:
    """AutoResearchReason enum for trigger classification."""

    def test_all_reasons_exist(self):
        """All expected trigger reasons should be defined."""
        assert AutoResearchReason.STUCK.value == "stuck"
        assert AutoResearchReason.BAD_REVIEW.value == "bad_review"
        assert AutoResearchReason.UNKNOWN_LIB.value == "unknown_lib"
        assert AutoResearchReason.ARCHITECTURE.value == "architecture"
        assert AutoResearchReason.MANUAL.value == "manual"


class TestParallelismMode:
    """ParallelismMode enum for strategy selection."""

    def test_all_modes_exist(self):
        """All expected parallelism modes should be defined."""
        assert ParallelismMode.SEQUENTIAL.value == "sequential"
        assert ParallelismMode.SUBAGENTS.value == "subagents"
        assert ParallelismMode.HIVE.value == "hive"
        assert ParallelismMode.RESEARCH_FIRST.value == "research_first"


class TestParallelismRecommendation:
    """ParallelismRecommendation model construction."""

    def test_minimal_construction(self):
        """Can construct with minimal required fields."""
        rec = ParallelismRecommendation(
            mode=ParallelismMode.SEQUENTIAL,
            workers=1,
            reasoning="small task",
            research_recommended=False,
            estimated_speedup="1x",
        )
        assert rec.mode == ParallelismMode.SEQUENTIAL
        assert rec.workers == 1

    def test_research_first_with_speedup(self):
        """RESEARCH_FIRST should indicate quality improvement speedup."""
        rec = ParallelismRecommendation(
            mode=ParallelismMode.RESEARCH_FIRST,
            workers=1,
            reasoning="architectural decision",
            research_recommended=True,
            estimated_speedup="1.5-2x (quality improvement from SOTA research)",
        )
        assert "quality" in rec.estimated_speedup.lower()

    def test_hive_speedup(self):
        """HIVE mode should indicate multi-process speedup."""
        rec = ParallelismRecommendation(
            mode=ParallelismMode.HIVE,
            workers=8,
            reasoning="large task",
            research_recommended=False,
            estimated_speedup="4-8x faster",
        )
        assert "x faster" in rec.estimated_speedup


class TestSubagentsConfig:
    """SubagentsConfig defaults."""

    def test_defaults(self):
        """SubagentsConfig should have sensible defaults."""
        cfg = ForgeGodConfig()
        assert cfg.subagents.enabled is False
        assert cfg.subagents.max_concurrency == 3
        assert cfg.subagents.max_retries == 2


class TestHiveConfig:
    """HiveConfig defaults."""

    def test_defaults(self):
        """HiveConfig should have sensible defaults."""
        cfg = ForgeGodConfig()
        assert cfg.hive.max_workers == 4
        assert cfg.hive.max_iterations == 10
        assert cfg.hive.scheduler_mode == "hybrid"
