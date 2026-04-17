"""ForgeGod Subagent Orchestrator -- parallel analysis with adversarial review."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from forgegod.agent import Agent
from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.json_utils import extract_json
from forgegod.models import AgentResult, ResearchBrief, ReviewResult, ReviewVerdict
from forgegod.reviewer import Reviewer
from forgegod.router import ModelRouter

logger = logging.getLogger("forgegod.subagents")


class SubagentTask(BaseModel):
    """One subagent task definition."""

    id: str
    title: str
    focus: str


class SubagentReport(BaseModel):
    """Subagent execution report."""

    id: str
    title: str
    focus: str
    attempts: int = 0
    output: str = ""
    review_verdict: str = ""
    review_reasoning: str = ""
    error: str = ""


class SubagentBundle(BaseModel):
    """Aggregated subagent results."""

    summary: str = ""
    reports: list[SubagentReport] = Field(default_factory=list)
    merge_instructions: str = ""


@dataclass(frozen=True)
class _DecompositionPlan:
    tasks: list[SubagentTask]
    merge_instructions: str = ""


class SubagentOrchestrator:
    """Parallel subagent executor with per-subagent adversarial review."""

    def __init__(
        self,
        config: ForgeGodConfig,
        *,
        router: ModelRouter | None = None,
        budget: BudgetTracker | None = None,
    ) -> None:
        self.config = config
        self.budget = budget or BudgetTracker(config)

        self._owns_router = router is None
        if router is None:
            subagent_config = config.model_copy(deep=True)
            subagent_config.models.planner = config.subagents.planner_model
            subagent_config.models.reviewer = config.subagents.reviewer_model
            self.router = ModelRouter(subagent_config)
        else:
            self.router = router

    async def run(
        self,
        task: str,
        research_brief: ResearchBrief | None = None,
    ) -> SubagentBundle:
        if not self.config.subagents.enabled:
            return SubagentBundle()

        try:
            plan = await self._decompose(task)
            if not plan.tasks:
                return SubagentBundle()

            semaphore = asyncio.Semaphore(max(1, self.config.subagents.max_concurrency))
            reports = await asyncio.gather(
                *[
                    self._run_one_subagent(task, subtask, semaphore, research_brief)
                    for subtask in plan.tasks
                ]
            )
            summary = self._build_summary(reports, plan.merge_instructions)
            return SubagentBundle(
                summary=summary,
                reports=reports,
                merge_instructions=plan.merge_instructions,
            )
        finally:
            if self._owns_router:
                await self.router.close()

    async def _decompose(self, task: str) -> _DecompositionPlan:
        max_subagents = max(1, self.config.subagents.max_concurrency)
        prompt = f"""You are a senior orchestration planner. Break the task into up to {max_subagents} parallel ANALYSIS subtasks.

Rules:
- Subtasks are analysis only. No file edits.
- Each subtask should focus on a distinct angle (architecture, risks, tests, dependencies, etc).
- Keep tasks small and independent.

Return JSON only:
{{
  "subtasks": [
    {{"id": "S1", "title": "...", "focus": "..."}}
  ],
  "merge_instructions": "How the main agent should use the findings"
}}

Task:
{task}
"""
        response, _usage = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=1200,
            temperature=0.2,
        )
        try:
            data = extract_json(response)
        except ValueError:
            logger.warning("Subagent decomposition failed to parse; skipping.")
            return _DecompositionPlan(tasks=[])

        tasks = []
        for idx, item in enumerate(data.get("subtasks", []) or []):
            task_id = str(item.get("id") or f"S{idx+1}")
            title = str(item.get("title") or "Subagent analysis")
            focus = str(item.get("focus") or title)
            tasks.append(SubagentTask(id=task_id, title=title, focus=focus))

        merge_instructions = str(data.get("merge_instructions") or "").strip()
        return _DecompositionPlan(tasks=tasks, merge_instructions=merge_instructions)

    async def _run_one_subagent(
        self,
        parent_task: str,
        subtask: SubagentTask,
        semaphore: asyncio.Semaphore,
        research_brief: ResearchBrief | None = None,
    ) -> SubagentReport:
        async with semaphore:
            attempts = 0
            last_error = ""
            last_output = ""
            review_result: ReviewResult | None = None
            reviewer = self._build_reviewer()

            while attempts <= self.config.subagents.max_retries:
                attempts += 1
                prompt = self._build_subagent_prompt(parent_task, subtask, review_result, research_brief)
                result = await self._run_subagent_prompt(prompt)
                if not result.success:
                    last_error = result.error or "subagent failed"
                    last_output = result.output
                    break
                last_output = result.output or ""
                review_result = await self._review_subagent_output(
                    reviewer,
                    subtask,
                    last_output,
                )
                if review_result.verdict == ReviewVerdict.APPROVE:
                    break
                if attempts > self.config.subagents.max_retries:
                    break

            return SubagentReport(
                id=subtask.id,
                title=subtask.title,
                focus=subtask.focus,
                attempts=attempts,
                output=last_output,
                review_verdict=review_result.verdict.value if review_result else "",
                review_reasoning=review_result.reasoning if review_result else "",
                error=last_error,
            )

    def _build_subagent_prompt(
        self,
        parent_task: str,
        subtask: SubagentTask,
        review_result: ReviewResult | None,
        research_brief: ResearchBrief | None = None,
    ) -> str:
        """Build subagent prompt, optionally enriched with SOTA 2026 research findings."""
        lines = [
            f"Analyze the task below with focus on: {subtask.focus}\n",
            f"Task:\n{parent_task}\n",
            "Rules:",
            "- Analysis only, do NOT modify files.",
            "- Provide a concise report with: key findings, recommended changes, and risks/tests.",
        ]

        # Inject SOTA 2026 research findings if available
        if research_brief:
            lines.append("")
            lines.append("[ SOTA 2026 RESEARCH FINDINGS ]")
            if research_brief.libraries:
                lines.append("\nRecommended Libraries:")
                for lib in research_brief.libraries[:5]:
                    lines.append(f"  - {lib.name} v{lib.version}: {lib.why}")
            if research_brief.architecture_patterns:
                lines.append("\nArchitecture Patterns:")
                for pattern in research_brief.architecture_patterns[:5]:
                    lines.append(f"  - {pattern}")
            if research_brief.security_warnings:
                lines.append("\nSecurity Warnings:")
                for warning in research_brief.security_warnings[:5]:
                    lines.append(f"  - {warning}")
            if research_brief.best_practices:
                lines.append("\nBest Practices:")
                for bp in research_brief.best_practices[:5]:
                    lines.append(f"  - {bp}")
            lines.append("")

        if review_result and review_result.verdict != ReviewVerdict.APPROVE:
            feedback = review_result.reasoning or ""
            issues = "\n".join(f"- {issue}" for issue in review_result.issues) if review_result.issues else ""
            lines.append("\nReviewer feedback to address:")
            lines.append(feedback)
            if issues:
                lines.append(f"\nIssues:\n{issues}")

        return "\n".join(lines)

    async def _run_subagent_prompt(self, prompt: str) -> AgentResult:
        sub_config = self.config.model_copy(deep=True)
        sub_config.security.permission_mode = "read-only"
        sub_config.security.approval_mode = "deny"
        sub_config.subagents.enabled = False
        if self.config.subagents.allowed_tools:
            sub_config.security.allowed_tools = list(self.config.subagents.allowed_tools)

        agent = Agent(
            config=sub_config,
            router=self.router,
            budget=self.budget,
            role="coder",
            max_turns=30,
        )
        return await agent.run(prompt)

    def _build_reviewer(self) -> Reviewer:
        review_config = self.config.model_copy(deep=True)
        review_config.models.reviewer = self.config.subagents.reviewer_model
        return Reviewer(config=review_config, router=self.router)

    async def _review_subagent_output(
        self,
        reviewer: Reviewer,
        subtask: SubagentTask,
        output: str,
    ) -> ReviewResult:
        return await reviewer.review(
            task=f"Review subagent analysis for {subtask.title}",
            code=output[:8000],
            test_output="",
            files_changed=[],
        )

    @staticmethod
    def _build_summary(
        reports: list[SubagentReport],
        merge_instructions: str,
    ) -> str:
        lines = []
        if merge_instructions:
            lines.append("Merge instructions:")
            lines.append(merge_instructions.strip())
            lines.append("")
        for report in reports:
            header = f"[{report.id}] {report.title} - {report.focus}"
            lines.append(header)
            body = report.output.strip().replace("\n", "\n  ")
            lines.append(f"  {body[:1200]}" if body else "  (no output)")
            if report.review_verdict:
                lines.append(f"  Review: {report.review_verdict}")
            if report.review_reasoning:
                lines.append(f"  Reason: {report.review_reasoning[:200]}")
            if report.error:
                lines.append(f"  Error: {report.error[:200]}")
            lines.append("")
        return "\n".join(lines).strip()
