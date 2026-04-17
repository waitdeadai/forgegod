"""ForgeGod effort gate for max-effort completion checks.

The gate stays fully local by default: it uses deterministic shortcut detection,
minimum-draft enforcement, and verification evidence checks. That keeps the
quality floor stable even when no external quality-judge package is installed.
"""

from __future__ import annotations

import logging

from forgegod.config import EffortConfig, ForgeGodConfig
from forgegod.shortcut_detector import ShortcutDetector

logger = logging.getLogger("forgegod.effort")

class EffortResult:
    def __init__(
        self,
        passed: bool = False,
        shortcut_detected: bool = False,
        shortcut_type: str = "",
        shortcut_detail: str = "",
        draft_count: int = 0,
        verification_evidence: list = None,
        blocked_reason: str = "",
        suggestions: list = None,
    ):
        self.passed = passed
        self.shortcut_detected = shortcut_detected
        self.shortcut_type = shortcut_type
        self.shortcut_detail = shortcut_detail
        self.draft_count = draft_count
        self.verification_evidence = verification_evidence or []
        self.blocked_reason = blocked_reason
        self.suggestions = suggestions or []

class EffortGate:
    def __init__(self, config: ForgeGodConfig):
        self.config = config
        self.effort: EffortConfig = config.effort
        self._detector = ShortcutDetector(
            blocked_categories=(
                ["skipped_verification", "good_enough_language", "single_pass", "vague_copy"]
                if self.effort.no_shortcuts else []
            ),
        )
        self._draft_counts: dict[str, int] = {}
        self._story_histories: dict[str, list[str]] = {}

    def start_story(self, story_id: str) -> None:
        self._draft_counts[story_id] = 0
        self._story_histories[story_id] = []

    def record_draft(self, story_id: str, draft_output: str) -> None:
        self._draft_counts[story_id] = self._draft_counts.get(story_id, 0) + 1
        self._story_histories.setdefault(story_id, []).append(draft_output)

    async def check(
        self,
        story_id: str,
        result,  # AgentResult-like object with .output and .verification_commands
        conversation_text: str = "",
    ) -> EffortResult:
        if not self.effort.enabled:
            return EffortResult(passed=True)

        draft_count = self._draft_counts.get(story_id, 0)

        # Rule 1: Minimum drafts
        if draft_count < self.effort.min_drafts:
            return EffortResult(
                passed=False,
                shortcut_detected=True,
                shortcut_type="insufficient_drafts",
                shortcut_detail=(
                    f"Story completed after {draft_count} draft(s), "
                    f"minimum required: {self.effort.min_drafts}"
                ),
                draft_count=draft_count,
                blocked_reason=(
                    f"max_effort requires at least {self.effort.min_drafts} "
                    f"draft(s). This was draft {draft_count}. Please iterate."
                ),
                suggestions=[
                    "Re-examine the implementation for edge cases or subtle bugs.",
                    "Consider alternative approaches not yet explored.",
                    "Add more comprehensive test coverage.",
                ],
            )

        # Rule 2: Verification evidence
        if self.effort.always_verify:
            verified = getattr(result, 'verification_commands', []) or []
            if not verified:
                return EffortResult(
                    passed=False,
                    shortcut_detected=True,
                    shortcut_type="skipped_verification",
                    shortcut_detail=(
                        "No post-edit verification commands were recorded."
                    ),
                    draft_count=draft_count,
                    blocked_reason=(
                        "max_effort always_verify is enabled: "
                        "post-edit verification evidence is required."
                    ),
                    suggestions=[
                        "Run pytest or the relevant test suite and include output.",
                        "Run linting (ruff, eslint) and include output.",
                    ],
                )

        # Rule 3: Shortcut detection
        text_to_scan = conversation_text or getattr(result, 'output', '') or ""
        if text_to_scan and self.effort.no_shortcuts:
            shortcuts = self._detector.detect(text_to_scan)
            if shortcuts:
                primary = shortcuts[0]
                return EffortResult(
                    passed=False,
                    shortcut_detected=True,
                    shortcut_type=primary.category,
                    shortcut_detail=primary.line.strip()[:200],
                    draft_count=draft_count,
                    blocked_reason=(
                        f"Shortcut detected: [{primary.category}] in coder output. "
                        f"max_effort no_shortcuts is enabled."
                    ),
                    suggestions=self._detector.summary(shortcuts).split("\n")[:5],
                )

        # Rule 4: Single-pass detection
        if self.effort.no_shortcuts and len(self._story_histories.get(story_id, [])) == 1:
            if text_to_scan:
                single_pass = self._detector.detect_single_pass(text_to_scan)
                if single_pass:
                    return EffortResult(
                        passed=False,
                        shortcut_detected=True,
                        shortcut_type="single_pass",
                        shortcut_detail=(
                            "Coder declared done after single pass without iteration."
                        ),
                        draft_count=draft_count,
                        blocked_reason=(
                            "max_effort requires iterative refinement. "
                            "Single-pass completion is not acceptable."
                        ),
                        suggestions=[
                            "Review your implementation critically.",
                            "Identify at least one area for improvement.",
                        ],
                    )

        return EffortResult(
            passed=True,
            draft_count=draft_count,
            verification_evidence=getattr(result, 'verification_commands', []) or [],
        )

    def apply_to_story(self, story, effort_result: EffortResult) -> None:
        if effort_result.passed:
            return
        from forgegod.models import StoryStatus

        story.status = StoryStatus.TODO
        story.error_log.append(f"[effort_gate] {effort_result.blocked_reason}")
        if effort_result.suggestions:
            story.error_log.append(
                f"[effort_gate] Suggestions: {'; '.join(effort_result.suggestions[:2])}"
            )
