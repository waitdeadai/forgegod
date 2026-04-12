from __future__ import annotations

import pytest

from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.models import AgentResult, ReviewResult, ReviewVerdict
from forgegod.subagents import SubagentOrchestrator, SubagentTask, _DecompositionPlan


class DummyRouter:
    async def close(self):
        return None


class FakeAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def run(self, _prompt: str) -> AgentResult:
        return AgentResult(success=True, output="analysis output")


class FakeReviewer:
    def __init__(self, *args, **kwargs):
        self.calls = 0

    async def review(self, **_kwargs) -> ReviewResult:
        self.calls += 1
        if self.calls == 1:
            return ReviewResult(
                verdict=ReviewVerdict.REVISE,
                confidence=0.3,
                reasoning="Need more detail",
                issues=["Missing tests"],
            )
        return ReviewResult(
            verdict=ReviewVerdict.APPROVE,
            confidence=0.8,
            reasoning="Looks good",
        )


@pytest.mark.asyncio
async def test_subagent_review_retry(monkeypatch):
    config = ForgeGodConfig()
    config.subagents.enabled = True
    config.subagents.max_retries = 1
    config.subagents.max_concurrency = 1

    async def fake_decompose(self, _task: str):
        return _DecompositionPlan(
            tasks=[SubagentTask(id="S1", title="Checks", focus="API impact")],
            merge_instructions="Use findings",
        )

    monkeypatch.setattr("forgegod.subagents.Agent", FakeAgent)
    monkeypatch.setattr("forgegod.subagents.Reviewer", FakeReviewer)
    monkeypatch.setattr(SubagentOrchestrator, "_decompose", fake_decompose)

    orchestrator = SubagentOrchestrator(
        config=config,
        router=DummyRouter(),
        budget=BudgetTracker(config),
    )
    bundle = await orchestrator.run("Build something")

    assert bundle.reports
    report = bundle.reports[0]
    assert report.attempts == 2
    assert report.review_verdict == "approve"
