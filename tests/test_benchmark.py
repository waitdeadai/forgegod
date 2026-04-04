"""Tests for ForgeGod Benchmark Engine — scoring logic and task validation."""

from __future__ import annotations

import pytest

from forgegod.benchmark import (
    BENCHMARK_TASKS,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkTask,
)
from forgegod.config import BudgetConfig, ForgeGodConfig
from forgegod.models import BudgetMode


class TestBenchmarkTasks:
    """Test built-in benchmark task definitions."""

    def test_task_count(self):
        """Should have 12 built-in tasks."""
        assert len(BENCHMARK_TASKS) == 12

    def test_tier_distribution(self):
        """Should have 3 tasks per tier (1-4)."""
        for tier in range(1, 5):
            tier_tasks = [t for t in BENCHMARK_TASKS if t.tier == tier]
            assert len(tier_tasks) == 3, f"Tier {tier} should have 3 tasks, got {len(tier_tasks)}"

    def test_task_ids_unique(self):
        """All task IDs must be unique."""
        ids = [t.id for t in BENCHMARK_TASKS]
        assert len(ids) == len(set(ids))

    def test_task_ids_follow_convention(self):
        """Task IDs should follow t{tier}_ prefix convention."""
        for task in BENCHMARK_TASKS:
            assert task.id.startswith(f"t{task.tier}_"), (
                f"Task {task.id} should start with t{task.tier}_"
            )

    def test_all_tasks_have_prompts(self):
        """Every task must have a non-empty prompt."""
        for task in BENCHMARK_TASKS:
            assert len(task.prompt) > 20, f"Task {task.id} prompt too short"

    def test_all_tasks_have_validation(self):
        """Every task must have a validation command."""
        for task in BENCHMARK_TASKS:
            assert task.validation_cmd, f"Task {task.id} missing validation_cmd"

    def test_tier_1_tasks_are_trivial(self):
        """Tier 1 tasks should have low reference complexity."""
        for task in BENCHMARK_TASKS:
            if task.tier == 1:
                assert task.reference_complexity <= 30, (
                    f"Tier 1 task {task.id} has high complexity {task.reference_complexity}"
                )

    def test_tier_4_tasks_are_hard(self):
        """Tier 4 tasks should have higher reference complexity."""
        for task in BENCHMARK_TASKS:
            if task.tier == 4:
                assert task.reference_complexity >= 50, (
                    f"Tier 4 task {task.id} has low complexity {task.reference_complexity}"
                )


class TestBenchmarkResult:
    """Test BenchmarkResult model."""

    def test_default_values(self):
        """BenchmarkResult should have sensible defaults."""
        result = BenchmarkResult(task_id="t1_test", model="test:model", tier=1)
        assert result.attempt_1_pass is False
        assert result.attempt_2_pass is False
        assert result.quality_score == 0.0
        assert result.cost_usd == 0.0
        assert result.error == ""

    def test_result_with_values(self):
        """BenchmarkResult stores all fields correctly."""
        result = BenchmarkResult(
            task_id="t2_health",
            model="ollama:qwen3.5:9b",
            tier=2,
            attempt_1_pass=True,
            quality_score=7.5,
            elapsed_s=15.3,
            cost_usd=0.0,
            tokens_used=1200,
            tool_calls=5,
        )
        assert result.attempt_1_pass is True
        assert result.quality_score == 7.5
        assert result.tokens_used == 1200


class TestCompositeScoring:
    """Test composite score computation."""

    @pytest.fixture
    def config(self) -> ForgeGodConfig:
        return ForgeGodConfig(budget=BudgetConfig(mode=BudgetMode.LOCAL_ONLY))

    @pytest.fixture
    def runner(self, config: ForgeGodConfig) -> BenchmarkRunner:
        return BenchmarkRunner(config, models=["test:model"])

    def test_perfect_score(self, runner: BenchmarkRunner):
        """All tasks passing should give high composite score."""
        for task in BENCHMARK_TASKS:
            runner._results.append(BenchmarkResult(
                task_id=task.id,
                model="test:model",
                tier=task.tier,
                attempt_1_pass=True,
                quality_score=8.0,
                elapsed_s=10.0,
                cost_usd=0.0,
                tokens_used=500,
            ))

        scores = runner.compute_composite_scores()
        assert "test:model" in scores
        assert scores["test:model"] > 7.0  # Should be high

    def test_zero_score(self, runner: BenchmarkRunner):
        """All tasks failing should give low composite score."""
        for task in BENCHMARK_TASKS:
            runner._results.append(BenchmarkResult(
                task_id=task.id,
                model="test:model",
                tier=task.tier,
                attempt_1_pass=False,
                attempt_2_pass=False,
                quality_score=2.0,
                elapsed_s=60.0,
                cost_usd=0.5,
                tokens_used=5000,
            ))

        scores = runner.compute_composite_scores()
        assert scores["test:model"] < 3.0  # Should be low

    def test_self_repair_scoring(self, runner: BenchmarkRunner):
        """Self-repair (pass on attempt 2) should be scored."""
        runner._results.append(BenchmarkResult(
            task_id="t1_test",
            model="test:model",
            tier=1,
            attempt_1_pass=False,
            attempt_2_pass=True,
            quality_score=6.0,
            elapsed_s=20.0,
            cost_usd=0.0,
            tokens_used=800,
        ))

        scores = runner.compute_composite_scores()
        assert scores["test:model"] > 0  # Should still get points

    def test_multi_model_comparison(self, runner: BenchmarkRunner):
        """Multiple models should get independent scores."""
        runner._results.append(BenchmarkResult(
            task_id="t1_test", model="model_a", tier=1,
            attempt_1_pass=True, quality_score=9.0,
            elapsed_s=5.0, cost_usd=0.0, tokens_used=200,
        ))
        runner._results.append(BenchmarkResult(
            task_id="t1_test", model="model_b", tier=1,
            attempt_1_pass=False, quality_score=3.0,
            elapsed_s=30.0, cost_usd=0.5, tokens_used=2000,
        ))

        # Reconfigure for 2 models
        runner.models = ["model_a", "model_b"]
        scores = runner.compute_composite_scores()
        assert "model_a" in scores
        assert "model_b" in scores
        assert scores["model_a"] > scores["model_b"]

    def test_empty_results(self, runner: BenchmarkRunner):
        """Empty results should return empty scores."""
        scores = runner.compute_composite_scores()
        assert scores == {}

    def test_tier_weighting(self, runner: BenchmarkRunner):
        """Higher tiers should be worth more in correctness scoring."""
        # Model A: passes only tier 1 (weight 1)
        runner._results.append(BenchmarkResult(
            task_id="t1_test", model="model_a", tier=1,
            attempt_1_pass=True, quality_score=5.0,
            elapsed_s=10.0, cost_usd=0.0, tokens_used=500,
        ))
        runner._results.append(BenchmarkResult(
            task_id="t4_test", model="model_a", tier=4,
            attempt_1_pass=False, quality_score=5.0,
            elapsed_s=10.0, cost_usd=0.0, tokens_used=500,
        ))
        # Model B: passes only tier 4 (weight 4)
        runner._results.append(BenchmarkResult(
            task_id="t1_test", model="model_b", tier=1,
            attempt_1_pass=False, quality_score=5.0,
            elapsed_s=10.0, cost_usd=0.0, tokens_used=500,
        ))
        runner._results.append(BenchmarkResult(
            task_id="t4_test", model="model_b", tier=4,
            attempt_1_pass=True, quality_score=5.0,
            elapsed_s=10.0, cost_usd=0.0, tokens_used=500,
        ))

        runner.models = ["model_a", "model_b"]
        scores = runner.compute_composite_scores()
        # Model B should score higher on correctness (tier 4 = weight 4 vs tier 1 = weight 1)
        assert scores["model_b"] > scores["model_a"]


class TestLeaderboardFormatting:
    """Test markdown leaderboard generation."""

    @pytest.fixture
    def runner(self) -> BenchmarkRunner:
        config = ForgeGodConfig(budget=BudgetConfig(mode=BudgetMode.LOCAL_ONLY))
        runner = BenchmarkRunner(config, models=["test:model"])
        runner._results.append(BenchmarkResult(
            task_id="t1_test", model="test:model", tier=1,
            attempt_1_pass=True, quality_score=7.0,
            elapsed_s=12.0, cost_usd=0.01, tokens_used=500,
        ))
        return runner

    def test_markdown_has_header(self, runner: BenchmarkRunner):
        """Leaderboard should have markdown table header."""
        md = runner.format_leaderboard_markdown()
        assert "## Model Leaderboard" in md
        assert "| Model |" in md

    def test_markdown_has_model_row(self, runner: BenchmarkRunner):
        """Leaderboard should include model results."""
        md = runner.format_leaderboard_markdown()
        assert "test:model" in md

    def test_markdown_has_run_instruction(self, runner: BenchmarkRunner):
        """Leaderboard should tell users how to run."""
        md = runner.format_leaderboard_markdown()
        assert "forgegod benchmark" in md
