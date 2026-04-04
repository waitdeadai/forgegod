"""ForgeGod Reviewer — frontier model quality gate.

Inspired by forge/forge_council.py, simplified from multi-member council
to single reviewer with configurable frontier model.
"""

from __future__ import annotations

import json
import logging

from forgegod.config import ForgeGodConfig
from forgegod.models import ReviewResult, ReviewVerdict
from forgegod.router import ModelRouter
from forgegod.terse import TERSE_REVIEWER_PROMPT

logger = logging.getLogger("forgegod.reviewer")


class Reviewer:
    """Quality gate — reviews agent output with a frontier model.

    Usage:
    - `run` mode: Always review final output
    - `loop` mode: Sample every Nth story (configurable)
    - Budget-aware: skip review when budget is tight
    """

    def __init__(self, config: ForgeGodConfig, router: ModelRouter | None = None):
        self.config = config
        self.router = router or ModelRouter(config)
        self._reviews_done = 0

    async def review(
        self,
        task: str,
        code: str,
        test_output: str = "",
        files_changed: list[str] | None = None,
    ) -> ReviewResult:
        """Review code with frontier model.

        Args:
            task: The original task description.
            code: The code to review (or diff).
            test_output: Test results if available.
            files_changed: List of files modified.

        Returns:
            ReviewResult with verdict, reasoning, and suggestions.
        """
        if self.config.terse.enabled:
            test_block = f"## Tests\n{test_output[:2000]}" if test_output else ""
            files_block = f"## Files\n{chr(10).join(files_changed)}" if files_changed else ""
            prompt = TERSE_REVIEWER_PROMPT.format(
                task=task,
                code=code[:8000],
                test_block=test_block,
                files_block=files_block,
            )
        else:
            prompt = f"""You are a senior code reviewer. Review the following code changes.

## Original Task
{task}

## Code
```
{code[:8000]}
```

{('## Test Output' + chr(10) + test_output[:2000]) if test_output else ''}

{('## Files Changed' + chr(10) + chr(10).join(files_changed)) if files_changed else ''}

## Review Criteria
1. **Correctness**: Does the code fulfill the task requirements?
2. **Security**: Any vulnerabilities (injection, hardcoded secrets, etc.)?
3. **Quality**: Clean code, proper error handling, no obvious bugs?
4. **Completeness**: Are edge cases handled? Are tests adequate?

## Output Format (JSON)
{{
  "verdict": "approve" | "revise" | "reject",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "issues": ["Issue 1", "Issue 2"],
  "suggestions": ["Suggestion 1", "Suggestion 2"]
}}

Output ONLY valid JSON."""

        response, usage = await self.router.call(
            prompt=prompt,
            role="reviewer",
            json_mode=True,
            max_tokens=2048,
            temperature=0.2,
        )

        self._reviews_done += 1
        return self._parse_review(response, usage.model)

    async def review_path(self, path: str) -> ReviewResult:
        """Review code at a file or directory path.

        Reads git diff or file contents and sends for review.
        """
        from pathlib import Path as P

        target = P(path)
        if target.is_file():
            code = target.read_text(encoding="utf-8", errors="replace")
            task = f"Review the code in {path}"
        else:
            # Use git diff for directories
            import asyncio
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD", "--", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            code = stdout.decode("utf-8", errors="replace")
            if not code.strip():
                # No diff — show recent changes
                proc2 = await asyncio.create_subprocess_exec(
                    "git", "diff", "HEAD~1", "--", path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout2, _ = await proc2.communicate()
                code = stdout2.decode("utf-8", errors="replace")
            task = f"Review recent changes in {path}"

        if not code.strip():
            return ReviewResult(
                verdict=ReviewVerdict.APPROVE,
                confidence=1.0,
                reasoning="No code changes to review",
            )

        return await self.review(task=task, code=code)

    def should_review(self, story_index: int, is_single_shot: bool = False) -> bool:
        """Decide whether to review this output.

        Args:
            story_index: 0-based index of the story in the loop.
            is_single_shot: True if running in `forgegod run` mode.
        """
        if not self.config.review.enabled:
            return False

        if is_single_shot and self.config.review.always_review_run:
            return True

        # In loop mode, sample every Nth story
        return (story_index + 1) % self.config.review.sample_rate == 0

    def _parse_review(self, response: str, model: str) -> ReviewResult:
        """Parse LLM response into ReviewResult."""
        try:
            data = json.loads(response)
            verdict_str = data.get("verdict", "approve").lower()
            verdict = {
                "approve": ReviewVerdict.APPROVE,
                "revise": ReviewVerdict.REVISE,
                "reject": ReviewVerdict.REJECT,
            }.get(verdict_str, ReviewVerdict.APPROVE)

            return ReviewResult(
                verdict=verdict,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                model_used=model,
            )
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse review response, defaulting to APPROVE")
            return ReviewResult(
                verdict=ReviewVerdict.APPROVE,
                confidence=0.3,
                reasoning="Failed to parse review response",
                model_used=model,
            )

    @property
    def reviews_done(self) -> int:
        return self._reviews_done
