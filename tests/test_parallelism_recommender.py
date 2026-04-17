"""Tests for forgegod/parallelism.py — SOTA 2026 task → strategy mapping."""

from __future__ import annotations

from forgegod.config import ForgeGodConfig
from forgegod.models import (
    ParallelismMode,
    ResearchBrief,
)
from forgegod.parallelism import recommend_parallelism


def _cfg(**overrides) -> ForgeGodConfig:
    base = ForgeGodConfig()
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class TestRecommendParallelism:
    """Parallelism strategy recommendation based on task complexity."""

    def test_sequential_small_task(self):
        """Small/simple tasks → SEQUENTIAL (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        rec = recommend_parallelism("fix a typo in README", cfg)
        assert rec.mode == ParallelismMode.SEQUENTIAL
        assert rec.workers == 1

    def test_sequential_quick_task(self):
        """Quick tasks with one file → SEQUENTIAL (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        rec = recommend_parallelism("add one import to utils.py", cfg)
        assert rec.mode == ParallelismMode.SEQUENTIAL
        assert rec.workers == 1

    def test_subagents_medium_task(self):
        """Medium tasks with multiple files → SUBAGENTS (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        rec = recommend_parallelism(
            "add validation to multiple API endpoints in the auth module",
            cfg,
        )
        assert rec.mode == ParallelismMode.SUBAGENTS
        assert rec.workers >= 2

    def test_subagents_complex_task(self):
        """Complex tasks without architecture keywords → SUBAGENTS (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        rec = recommend_parallelism(
            "implement caching layer for database queries across multiple services",
            cfg,
        )
        assert rec.mode == ParallelismMode.SUBAGENTS

    def test_hive_large_task(self):
        """Very large tasks with many files → HIVE (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        rec = recommend_parallelism(
            "rebuild the entire authentication system across microservices",
            cfg,
        )
        assert rec.mode == ParallelismMode.HIVE

    def test_research_first_architecture_keyword(self):
        """Architecture keyword → RESEARCH_FIRST."""
        cfg = _cfg()
        rec = recommend_parallelism(
            "design a new microservices architecture pattern for the API",
            cfg,
        )
        assert rec.mode == ParallelismMode.RESEARCH_FIRST
        assert rec.research_recommended is True

    def test_research_before_code_marks_research_without_forcing_mode(self):
        """research_before_code=True keeps topology selection but marks research."""
        cfg = _cfg()
        cfg.agent.research_before_code = True
        rec = recommend_parallelism("add async caching to the cache module", cfg)
        assert rec.mode in (ParallelismMode.SEQUENTIAL, ParallelismMode.SUBAGENTS)
        assert rec.research_recommended is True

    def test_research_first_sota_keyword(self):
        """SOTA keyword → RESEARCH_FIRST."""
        cfg = _cfg()
        rec = recommend_parallelism(
            "implement SOTA async patterns for high-throughput API",
            cfg,
        )
        assert rec.mode == ParallelismMode.RESEARCH_FIRST

    def test_research_first_best_practice_keyword(self):
        """best practice keyword → RESEARCH_FIRST."""
        cfg = _cfg()
        rec = recommend_parallelism(
            "refactor to best practice design patterns for the service layer",
            cfg,
        )
        assert rec.mode == ParallelismMode.RESEARCH_FIRST

    def test_research_first_migration_keyword(self):
        """migration keyword → RESEARCH_FIRST."""
        cfg = _cfg()
        rec = recommend_parallelism(
            "migration strategy from REST to GraphQL API",
            cfg,
        )
        assert rec.mode == ParallelismMode.RESEARCH_FIRST

    def test_research_first_with_existing_brief(self):
        """Existing research brief with architecture patterns → RESEARCH_FIRST."""
        cfg = _cfg()
        brief = ResearchBrief(
            task="build cache",
            architecture_patterns=["CQRS pattern"],
        )
        rec = recommend_parallelism("implement cache invalidation", cfg, brief)
        assert rec.mode == ParallelismMode.RESEARCH_FIRST

    def test_hive_workers_capped_at_max(self):
        """Hive workers capped at config hive.max_workers (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        cfg.hive.max_workers = 2
        # Task with "multiple modules" + technical terms → HIVE
        rec = recommend_parallelism(
            "rebuild the entire microservices system across many distributed modules",
            cfg,
        )
        assert rec.mode == ParallelismMode.HIVE
        assert rec.workers <= cfg.hive.max_workers

    def test_subagents_workers_capped_at_concurrency(self):
        """Subagent workers capped at config.subagents.max_concurrency (research disabled)."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        cfg.subagents.max_concurrency = 2
        rec = recommend_parallelism(
            "implement caching across multiple API endpoints",
            cfg,
        )
        assert rec.mode == ParallelismMode.SUBAGENTS
        assert rec.workers <= cfg.subagents.max_concurrency

    def test_research_first_with_brief_no_architecture(self):
        """Research brief without architecture + research_before_code=False → size-based."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        brief = ResearchBrief(task="fix bug", libraries=[], architecture_patterns=[])
        rec = recommend_parallelism("fix typo", cfg, brief)
        assert rec.mode == ParallelismMode.SEQUENTIAL

    def test_research_first_disabled_falls_through(self):
        """research_before_code=False → size-based recommendation."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        # Task without architecture keywords → falls through to size-based
        rec = recommend_parallelism(
            "add logging to the database query functions",
            cfg,
        )
        # No architecture keywords + research disabled → size-based
        assert rec.mode in (ParallelismMode.SUBAGENTS, ParallelismMode.SEQUENTIAL)

    def test_reasoning_always_set(self):
        """Every recommendation includes a reasoning string."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        rec = recommend_parallelism("add async caching", cfg)
        assert len(rec.reasoning) > 10

    def test_estimated_speedup_always_set(self):
        """Every recommendation includes estimated speedup."""
        cfg = _cfg()
        cfg.agent.research_before_code = False
        for task in [
            "fix typo",
            "add one feature to api",
            "rebuild the entire auth system",
        ]:
            rec = recommend_parallelism(task, cfg)
            assert rec.estimated_speedup, f"Missing speedup for: {task}"
