"""Unit tests for reviewer.py — review verdict parsing and sampling logic."""

from __future__ import annotations

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.models import ReviewVerdict, ReviewResult
from forgegod.reviewer import Reviewer
from forgegod.router import ModelRouter


class TestReviewVerdict:
    """Test ReviewVerdict enum."""

    def test_review_verdict_approve(self) -> None:
        """Test APPROVE enum value."""
        assert ReviewVerdict.APPROVE.value == "approve"

    def test_review_verdict_revise(self) -> None:
        """Test REVISE enum value."""
        assert ReviewVerdict.REVISE.value == "revise"

    def test_review_verdict_reject(self) -> None:
        """Test REJECT enum value."""
        assert ReviewVerdict.REJECT.value == "reject"


class TestParseReview:
    """Test _parse_review() parsing logic."""

    @pytest.fixture
    def reviewer(self) -> Reviewer:
        """Create a reviewer with minimal config."""
        config = ForgeGodConfig(
            model="ollama:qwen3-coder-next",
            review_enabled=True,
            review_sample_rate=1,
            review_always_review_run=False,
        )
        return Reviewer(config=config)

    def test_parse_valid_review_all_fields(self, reviewer: Reviewer) -> None:
        """Test parsing valid JSON with all fields."""
        response = '''{
            "verdict": "approve",
            "confidence": 0.95,
            "reasoning": "Code looks good",
            "issues": [],
            "suggestions": []
        }'''
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.APPROVE
        assert result.confidence == 0.95
        assert result.reasoning == "Code looks good"
        assert result.issues == []
        assert result.suggestions == []
        assert result.model_used == "ollama:qwen3-coder-next"

    def test_parse_valid_review_missing_fields(self, reviewer: Reviewer) -> None:
        """Test parsing valid JSON with missing fields (defaults)."""
        response = '''{
            "verdict": "revise",
            "confidence": 0.8
        }'''
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.REVISE
        assert result.confidence == 0.8
        assert result.reasoning == ""
        assert result.issues == []
        assert result.suggestions == []

    def test_parse_invalid_json_fallback(self, reviewer: Reviewer) -> None:
        """Test parsing invalid JSON falls back to APPROVE."""
        response = "not valid json {{{"
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.APPROVE
        assert result.confidence == 0.3
        assert "Failed to parse" in result.reasoning

    def test_parse_malformed_verdict_fallback(self, reviewer: Reviewer) -> None:
        """Test parsing malformed verdict falls back to APPROVE."""
        response = '''{
            "verdict": "unknown",
            "confidence": 0.7,
            "reasoning": "Unknown verdict"
        }'''
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.APPROVE
        assert result.confidence == 0.7
        assert result.reasoning == "Unknown verdict"

    def test_parse_empty_response(self, reviewer: Reviewer) -> None:
        """Test parsing empty response."""
        response = ""
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.APPROVE
        assert result.confidence == 0.3

    def test_parse_partial_json(self, reviewer: Reviewer) -> None:
        """Test parsing partial JSON (missing closing brace)."""
        response = '{"verdict": "approve"'
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.APPROVE
        assert result.confidence == 0.3

    def test_parse_json_with_extra_whitespace(self, reviewer: Reviewer) -> None:
        """Test parsing JSON with extra whitespace."""
        response = '''   {
            "verdict": "reject",
            "confidence": 0.6,
            "reasoning": "   ",
            "issues": ["issue1", "issue2"],
            "suggestions": ["fix1"]
        }   '''
        result = reviewer._parse_review(response, "ollama:qwen3-coder-next")
        assert result.verdict == ReviewVerdict.REJECT
        assert result.confidence == 0.6
        assert result.reasoning == "   "
        assert result.issues == ["issue1", "issue2"]
        assert result.suggestions == ["fix1"]


class TestShouldReview:
    """Test should_review() sampling logic."""

    @pytest.fixture
    def reviewer_loop(self) -> Reviewer:
        """Create a reviewer for loop mode (sample every Nth)."""
        config = ForgeGodConfig(
            model="ollama:qwen3-coder-next",
            review_enabled=True,
            review_sample_rate=3,
            review_always_review_run=False,
        )
        return Reviewer(config=config)

    @pytest.fixture
    def reviewer_run(self) -> Reviewer:
        """Create a reviewer for run mode (always review)."""
        config = ForgeGodConfig(
            model="ollama:qwen3-coder-next",
            review_enabled=True,
            review_sample_rate=1,
            review_always_review_run=True,
        )
        return Reviewer(config=config)

    @pytest.fixture
    def reviewer_disabled(self) -> Reviewer:
        """Create a reviewer with review disabled."""
        config = ForgeGodConfig(
            model="ollama:qwen3-coder-next",
            review_enabled=False,
            review_sample_rate=1,
            review_always_review_run=False,
        )
        return Reviewer(config=config)

    def test_should_review_disabled(self, reviewer_disabled: Reviewer) -> None:
        """Test should_review returns False when disabled."""
        assert reviewer_disabled.should_review(0) is False
        assert reviewer_disabled.should_review(5) is False

    def test_should_review_run_mode_always(self, reviewer_run: Reviewer) -> None:
        """Test should_review returns True in run mode for all indices."""
        for i in range(10):
            assert reviewer_run.should_review(i, is_single_shot=True) is True

    def test_should_review_loop_mode_sample_rate_3(self, reviewer_loop: Reviewer) -> None:
        """Test should_review samples every 3rd story when sample_rate=3."""
        # sample_rate=3 means review stories 3, 6, 9, etc. (1-indexed)
        # story_index is 0-based, so (story_index + 1) % 3 == 0
        assert reviewer_loop.should_review(0) is False  # (0+1) % 3 = 1
        assert reviewer_loop.should_review(1) is False  # (1+1) % 3 = 2
        assert reviewer_loop.should_review(2) is False  # (2+1) % 3 = 0 -> True
        assert reviewer_loop.should_review(3) is False  # (3+1) % 3 = 1
        assert reviewer_loop.should_review(4) is False  # (4+1) % 3 = 2
        assert reviewer_loop.should_review(5) is False  # (5+1) % 3 = 0 -> True
        assert reviewer_loop.should_review(6) is False  # (6+1) % 3 = 1
        assert reviewer_loop.should_review(7) is False  # (7+1) % 3 = 2
        assert reviewer_loop.should_review(8) is False  # (8+1) % 3 = 0 -> True

    def test_should_review_loop_mode_sample_rate_1(self, reviewer_run: Reviewer) -> None:
        """Test should_review reviews every story when sample_rate=1."""
        for i in range(10):
            assert reviewer_run.should_review(i) is True

    def test_should_review_loop_mode_sample_rate_5(self) -> None:
        """Test should_review with sample_rate=5."""
        config = ForgeGodConfig(
            model="ollama:qwen3-coder-next",
            review_enabled=True,
            review_sample_rate=5,
            review_always_review_run=False,
        )
        reviewer = Reviewer(config=config)
        # Review stories 5, 10, 15, etc.
        for i in range(10):
            expected = (i + 1) % 5 == 0
            assert reviewer.should_review(i) is expected

    def test_should_review_single_shot_with_always_review(self, reviewer_run: Reviewer) -> None:
        """Test should_review in single shot mode with always_review_run=True."""
        for i in range(10):
            assert reviewer_run.should_review(i, is_single_shot=True) is True
            assert reviewer_run.should_review(i, is_single_shot=False) is True
