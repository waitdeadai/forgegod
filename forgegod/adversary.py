"""ForgeGod Adversary — adversarial plan critique and debate for Recon.

Phase 3 of Recon: a reviewer model attacks the plan across 6 dimensions,
the planner revises, and they iterate until convergence or max rounds.
"""

from __future__ import annotations

import json
import logging

from forgegod.config import ForgeGodConfig
from forgegod.models import (
    PRD,
    DebateResult,
    PlanCritique,
    ResearchBrief,
    Story,
    StoryStatus,
)
from forgegod.router import ModelRouter
from forgegod.terse import RECON_CRITIQUE_PROMPT, RECON_REVISION_PROMPT

logger = logging.getLogger("forgegod.adversary")


class Adversary:
    """Adversarial plan reviewer — multi-round critique and debate."""

    def __init__(self, config: ForgeGodConfig, router: ModelRouter):
        self.config = config
        self.router = router
        self.recon = config.recon

    async def debate(
        self, prd: PRD, brief: ResearchBrief, max_rounds: int | None = None,
    ) -> DebateResult:
        """Run adversarial debate loop on a PRD.

        Returns DebateResult with all critique rounds and final convergence status.
        """
        if max_rounds is None:
            max_rounds = self.recon.debate_rounds

        critiques: list[PlanCritique] = []
        current_prd = prd

        for round_num in range(1, max_rounds + 1):
            logger.info("Adversary: round %d/%d", round_num, max_rounds)

            # Critique
            critique = await self._critique(current_prd, brief, round_num, max_rounds)
            critiques.append(critique)

            logger.info(
                "Adversary: round %d — verdict=%s, score=%.1f",
                round_num, critique.verdict, critique.overall_score,
            )

            # Check convergence
            if self._has_converged(critique):
                logger.info(
                    "Adversary: converged at round %d (score %.1f)",
                    round_num, critique.overall_score,
                )
                return DebateResult(
                    rounds=round_num,
                    critiques=critiques,
                    converged=True,
                    final_score=critique.overall_score,
                )

            # Revise if not the last round
            if round_num < max_rounds:
                current_prd = await self._revise(current_prd, critique, brief, round_num)
                # Update the original PRD in-place
                prd.stories = current_prd.stories
                prd.guardrails = current_prd.guardrails
                prd.description = current_prd.description

        # Didn't converge — return best result
        final_score = critiques[-1].overall_score if critiques else 0.0
        logger.warning(
            "Adversary: did not converge after %d rounds (final score %.1f)",
            max_rounds, final_score,
        )
        return DebateResult(
            rounds=max_rounds,
            critiques=critiques,
            converged=False,
            final_score=final_score,
        )

    async def _critique(
        self, prd: PRD, brief: ResearchBrief, round_num: int, max_rounds: int,
    ) -> PlanCritique:
        """Generate a critique of the PRD."""
        from datetime import datetime, timezone

        year = datetime.now(timezone.utc).year

        prd_json = json.dumps(prd.model_dump(exclude={"learnings", "created_at"}), indent=2)
        brief_json = json.dumps({
            "libraries": [lib.model_dump() for lib in brief.libraries],
            "architecture_patterns": brief.architecture_patterns,
            "security_warnings": brief.security_warnings,
            "best_practices": brief.best_practices,
            "prior_art": brief.prior_art,
        }, indent=2)

        prompt = RECON_CRITIQUE_PROMPT.format(
            prd_json=prd_json,
            brief_json=brief_json,
            round_num=round_num,
            max_rounds=max_rounds,
            year=year,
        )

        response, usage = await self.router.call(
            prompt=prompt,
            role="reviewer",
            json_mode=True,
            max_tokens=2048,
            temperature=0.3,
        )

        return self._parse_critique(response, round_num, usage.model)

    def _parse_critique(self, response: str, round_num: int, model: str) -> PlanCritique:
        """Parse critique response into PlanCritique."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            import re

            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                logger.warning("Failed to parse critique, treating as revise")
                return PlanCritique(
                    round_num=round_num,
                    verdict="revise",
                    overall_score=5.0,
                    issues=["Failed to parse critique response"],
                    model_used=model,
                )

        return PlanCritique(
            round_num=round_num,
            verdict=data.get("verdict", "revise"),
            overall_score=float(data.get("overall_score", 0)),
            sota_score=float(data.get("sota_score", 0)),
            security_score=float(data.get("security_score", 0)),
            architecture_score=float(data.get("architecture_score", 0)),
            completeness_score=float(data.get("completeness_score", 0)),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            model_used=model,
        )

    async def _revise(
        self, prd: PRD, critique: PlanCritique, brief: ResearchBrief, round_num: int,
    ) -> PRD:
        """Revise the PRD based on critique feedback."""
        prd_json = json.dumps(prd.model_dump(exclude={"learnings", "created_at"}), indent=2)
        brief_json = json.dumps({
            "libraries": [lib.model_dump() for lib in brief.libraries],
            "security_warnings": brief.security_warnings,
            "best_practices": brief.best_practices,
        }, indent=2)
        critique_json = json.dumps(critique.model_dump(), indent=2)

        prompt = RECON_REVISION_PROMPT.format(
            prd_json=prd_json,
            brief_json=brief_json,
            critique_json=critique_json,
            round_num=round_num,
        )

        response, _ = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=4096,
            temperature=0.3,
        )

        revised = self._parse_revised_prd(response, prd)
        logger.info(
            "Adversary: revised PRD — %d stories, %d guardrails",
            len(revised.stories), len(revised.guardrails),
        )
        return revised

    def _parse_revised_prd(self, response: str, original: PRD) -> PRD:
        """Parse revised PRD from response, falling back to original on failure."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            import re

            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                logger.warning("Failed to parse revised PRD, keeping original")
                return original

        stories = []
        for s in data.get("stories", []):
            stories.append(Story(
                id=s.get("id", f"S{len(stories) + 1:03d}"),
                title=s.get("title", "Untitled"),
                description=s.get("description", ""),
                status=StoryStatus.TODO,
                priority=s.get("priority", len(stories) + 1),
                acceptance_criteria=s.get("acceptance_criteria", []),
            ))

        if not stories:
            logger.warning("Revised PRD has no stories, keeping original")
            return original

        return PRD(
            project=data.get("project", original.project),
            description=data.get("description", original.description),
            stories=stories,
            guardrails=data.get("guardrails", original.guardrails),
            learnings=original.learnings,
        )

    def _has_converged(self, critique: PlanCritique) -> bool:
        """Check if the critique indicates the plan is good enough."""
        if critique.verdict == "approve":
            return True

        min_score = self.recon.min_approval_score
        scores = [
            critique.sota_score,
            critique.security_score,
            critique.architecture_score,
            critique.completeness_score,
        ]
        # All dimensions must meet minimum AND overall must meet minimum
        return (
            critique.overall_score >= min_score
            and all(s >= min_score for s in scores if s > 0)
        )
