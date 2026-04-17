"""Tests for max_effort mode: ShortcutDetector and EffortGate."""

from __future__ import annotations

import pytest

from forgegod.config import EffortConfig, ForgeGodConfig
from forgegod.effort_gate import EffortGate, EffortResult
from forgegod.shortcut_detector import (
    ShortcutDetector,
)

# ── ShortcutDetector tests ────────────────────────────────────────────────

class TestShortcutDetectorPatterns:
    """Test that all pattern categories match expected phrases."""

    def test_skip_verification_patterns(self):
        detector = ShortcutDetector(blocked_categories=["skipped_verification"])
        texts = [
            "We skip tests for now",
            "no need to run linting",
            "won't run tests",
            "verification not needed",
            "assuming it should work",
            "tests can be redundant",
        ]
        for text in texts:
            matches = detector.detect(text)
            found = any(m.category == "skipped_verification" for m in matches)
            assert found, f"Should detect skipped_verification in: {text}"

    def test_good_enough_patterns(self):
        detector = ShortcutDetector(blocked_categories=["good_enough_language"])
        texts = [
            "This is good enough",
            "should work for our purposes",
            "looks good to me",
            "sufficient for now",
            "acceptable quality",
            "this will do",
            "good to go",
            "fine for now",
            "close enough",
        ]
        for text in texts:
            matches = detector.detect(text)
            found = any(m.category == "good_enough_language" for m in matches)
            assert found, f"Should detect good_enough_language in: {text}"

    def test_single_pass_patterns(self):
        detector = ShortcutDetector(blocked_categories=["single_pass"])
        texts = [
            "Done.",
            "Complete!",
            "All set.",
            "Implementation complete",
            "task is done",
        ]
        for text in texts:
            matches = detector.detect(text)
            found = any(m.category == "single_pass" for m in matches)
            assert found, f"Should detect single_pass in: {text}"

    def test_vague_copy_patterns(self):
        detector = ShortcutDetector(blocked_categories=["vague_copy"])
        texts = [
            "We help you scale",
            "transform your business",
            "seamless integration",
            "powered by AI",
            "cutting-edge technology",
            "next-generation platform",
            "unlock your potential",
            "leverage your data",
            "scalability",
            "robust solution",
            "effortless setup",
        ]
        for text in texts:
            matches = detector.detect(text)
            found = any(m.category == "vague_copy" for m in matches)
            assert found, f"Should detect vague_copy in: {text}"


class TestShortcutDetectorCleanCode:
    """Test that clean code without shortcuts is not flagged."""

    def test_no_false_positives_on_clean_code(self):
        blocked = ["skipped_verification", "good_enough_language", "single_pass", "vague_copy"]
        detector = ShortcutDetector(blocked_categories=blocked)
        clean_code = """
        def calculate_totals(items):
            total = 0
            for item in items:
                total += item.price
            return total

        # TODO: add validation
        # Note: run tests before committing
        result = calculate_totals(order_items)
        assert result > 0, "Total must be positive"
        """
        matches = detector.detect(clean_code)
        assert len(matches) == 0, f"Clean code should have no matches, got: {matches}"

    def test_has_skipped_verification(self):
        detector = ShortcutDetector(blocked_categories=["skipped_verification"])
        assert detector.has_skipped_verification("We skip tests")
        assert not detector.has_skipped_verification("Run the tests to verify")

    def test_detect_single_pass(self):
        detector = ShortcutDetector(blocked_categories=["single_pass"])
        assert detector.detect_single_pass("Done.")
        assert not detector.detect_single_pass("Implementation in progress...")

    def test_summary_empty(self):
        detector = ShortcutDetector()
        assert "No shortcuts detected" in detector.summary([])

    def test_summary_with_matches(self):
        detector = ShortcutDetector(blocked_categories=["skipped_verification"])
        matches = [
            type("M", (), {
                "category": "skipped_verification",
                "matched_text": "skip tests",
                "line": "We skip tests here",
                "line_number": 5,
            })()
        ]
        summary = detector.summary(matches)
        assert "skipped_verification" in summary
        assert "5" in summary  # line number


# ── EffortConfig tests ────────────────────────────────────────────────────

class TestEffortConfigDefaults:
    """Test EffortConfig default values."""

    def test_effort_config_defaults(self):
        config = EffortConfig()
        assert config.enabled is False
        assert config.level == "thorough"
        assert config.min_drafts == 2
        assert config.always_verify is True
        assert config.no_shortcuts is True
        assert config.shortcuts_blocked == []
        assert config.research_before_code is True
        assert config.max_compaction_turns == 999
        assert config.retry_on_failure is True


class TestEffortConfigPresets:
    """Test EffortConfig level presets."""

    def test_effort_config_minimal_level(self):
        config = EffortConfig(level="minimal")
        assert config.min_drafts == 1
        assert config.always_verify is False
        assert config.no_shortcuts is False

    def test_effort_config_thorough_level(self):
        config = EffortConfig(level="thorough")
        assert config.min_drafts == 2
        assert config.always_verify is True
        assert config.no_shortcuts is True


# ── EffortGate tests ───────────────────────────────────────────────────────

class MockResult:
    """Mock result object for testing."""
    def __init__(self, output="", verification_commands=None):
        self.output = output
        self.verification_commands = verification_commands or []


class MockStory:
    """Mock story object for testing."""
    def __init__(self):
        self.id = "test-story-1"
        self.status = "todo"
        self.error_log = []


class TestEffortGateDisabled:
    """Test that EffortGate passes always when disabled."""

    @pytest.mark.asyncio
    async def test_disabled_passes_always(self):
        config = ForgeGodConfig()
        assert config.effort.enabled is False
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "some output")
        result = await gate.check("s1", MockResult(output="test"))
        assert result.passed is True


class TestEffortGateMinDrafts:
    """Test minimum drafts enforcement."""

    @pytest.mark.asyncio
    async def test_blocks_insufficient_drafts(self):
        config = ForgeGodConfig(effort=EffortConfig(enabled=True, min_drafts=2))
        gate = EffortGate(config)
        gate.start_story("s1")
        # Only 1 draft recorded, min_drafts=2
        gate.record_draft("s1", "first output")
        result = await gate.check("s1", MockResult(output="test"))
        assert result.passed is False
        assert result.shortcut_type == "insufficient_drafts"
        assert "draft 1" in result.blocked_reason
        assert "2" in result.blocked_reason

    @pytest.mark.asyncio
    async def test_passes_with_enough_drafts(self):
        config = ForgeGodConfig(effort=EffortConfig(enabled=True, min_drafts=2))
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "first output")
        gate.record_draft("s1", "second output")
        result = await gate.check("s1", MockResult(output="test", verification_commands=["pytest"]))
        assert result.passed is True


class TestEffortGateVerification:
    """Test verification evidence enforcement."""

    @pytest.mark.asyncio
    async def test_blocks_skipped_verification(self):
        config = ForgeGodConfig(effort=EffortConfig(
            enabled=True, always_verify=True, no_shortcuts=False))
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "done")
        gate.record_draft("s1", "done")
        # No verification_commands
        result = await gate.check("s1", MockResult(output="done"))
        assert result.passed is False
        assert result.shortcut_type == "skipped_verification"
        assert "verification" in result.blocked_reason.lower()

    @pytest.mark.asyncio
    async def test_passes_with_verification_commands(self):
        config = ForgeGodConfig(effort=EffortConfig(
            enabled=True, always_verify=True, no_shortcuts=False))
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "output")
        gate.record_draft("s1", "output")
        result = await gate.check("s1", MockResult(
            output="test", verification_commands=["pytest tests/"]))
        assert result.passed is True


class TestEffortGateShortcuts:
    """Test shortcut detection."""

    @pytest.mark.asyncio
    async def test_blocks_skip_verification_shortcut(self):
        config = ForgeGodConfig(effort=EffortConfig(
            enabled=True, no_shortcuts=True, always_verify=False))
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "skip tests")
        gate.record_draft("s1", "done")
        result = await gate.check("s1", MockResult(output="skip tests"))
        assert result.passed is False
        assert result.shortcut_type == "skipped_verification"

    @pytest.mark.asyncio
    async def test_blocks_good_enough_shortcut(self):
        config = ForgeGodConfig(effort=EffortConfig(
            enabled=True, no_shortcuts=True, always_verify=False))
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "looks good")
        gate.record_draft("s1", "done")
        result = await gate.check("s1", MockResult(output="looks good"))
        assert result.passed is False
        assert result.shortcut_type == "good_enough_language"

    @pytest.mark.asyncio
    async def test_blocks_single_pass_shortcut(self):
        config = ForgeGodConfig(effort=EffortConfig(
            enabled=True, no_shortcuts=True, always_verify=False, min_drafts=1))
        gate = EffortGate(config)
        gate.start_story("s1")
        # Only one draft recorded
        gate.record_draft("s1", "Done.")
        result = await gate.check("s1", MockResult(output="Done."))
        assert result.passed is False
        assert result.shortcut_type == "single_pass"

    @pytest.mark.asyncio
    async def test_passes_with_iteration_and_no_shortcuts(self):
        config = ForgeGodConfig(effort=EffortConfig(
            enabled=True, no_shortcuts=True, always_verify=False, min_drafts=1))
        gate = EffortGate(config)
        gate.start_story("s1")
        gate.record_draft("s1", "first iteration")
        gate.record_draft("s1", "second iteration with improvements")
        # Clean output with no shortcuts
        result = await gate.check("s1", MockResult(
            output="Implementation improved based on feedback"))
        assert result.passed is True


class TestEffortGateApplyToStory:
    """Test apply_to_story behavior."""

    def test_apply_to_story_blocks_passed_story(self):
        config = ForgeGodConfig(effort=EffortConfig(enabled=True))
        gate = EffortGate(config)
        story = MockStory()
        result = EffortResult(passed=True)
        gate.apply_to_story(story, result)
        # Story status should not change when passed
        assert story.status == "todo"

    def test_apply_to_story_sets_todo_on_failure(self):
        config = ForgeGodConfig(effort=EffortConfig(enabled=True))
        gate = EffortGate(config)
        story = MockStory()
        result = EffortResult(
            passed=False,
            shortcut_detected=True,
            shortcut_type="skipped_verification",
            blocked_reason="Skipped verification",
            suggestions=["Run tests", "Check lint"],
        )
        gate.apply_to_story(story, result)
        assert story.status.value == "todo"  # StoryStatus.TODO
        assert any("[effort_gate]" in err for err in story.error_log)

    def test_apply_to_story_records_suggestions(self):
        config = ForgeGodConfig(effort=EffortConfig(enabled=True))
        gate = EffortGate(config)
        story = MockStory()
        result = EffortResult(
            passed=False,
            shortcut_detected=True,
            shortcut_type="insufficient_drafts",
            blocked_reason="Need another draft",
            suggestions=["Review edge cases", "Run tests"],
        )

        gate.apply_to_story(story, result)

        assert any("Suggestions:" in err for err in story.error_log)


# ── Integration: config profile → effort enabled ─────────────────────────

class TestMaxEffortProfile:
    """Test that max_effort harness profile enables effort config."""

    def test_load_config_enables_effort_for_max_effort_profile(self):
        import tempfile
        from pathlib import Path

        from forgegod.config import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / ".forgegod"
            project_dir.mkdir()
            config_path = project_dir / "config.toml"
            config_path.write_text('[harness]\nprofile = "max_effort"\n')

            config = load_config(project_root=Path(tmpdir))
            assert config.harness.profile == "max_effort"
            assert config.effort.enabled is True
