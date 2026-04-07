"""ForgeGod Worktree Pool — parallel execution via git worktrees.

Each worker gets its own worktree + branch. No shared mutable state
except prd.json (read-only during parallel execution). Merges are
reviewed before applying.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from forgegod.agent import Agent
from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.models import AgentResult, Story, WorkerStatus
from forgegod.router import ModelRouter
from forgegod.tools.git import _run_git

logger = logging.getLogger("forgegod.worktree")


class WorktreePool:
    """Manages parallel agent instances via git worktrees.

    Each story runs in an isolated worktree on a feature branch.
    Results are reviewed and merged back to the main branch.
    """

    def __init__(
        self,
        config: ForgeGodConfig,
        router: ModelRouter | None = None,
        budget: BudgetTracker | None = None,
        max_workers: int | None = None,
    ):
        self.config = config
        self.router = router or ModelRouter(config)
        self.budget = budget or BudgetTracker(config)
        self.max_workers = max_workers or config.loop.parallel_workers
        self._workers: list[WorkerStatus] = []
        self._worktree_base = config.project_dir / "worktrees"

    async def run_parallel(
        self,
        stories: list[Story],
        project_context: str = "",
        guardrails: list[str] | None = None,
    ) -> list[tuple[Story, AgentResult]]:
        """Execute multiple stories in parallel using worktrees.

        Args:
            stories: Stories to execute (will take up to max_workers).
            project_context: Shared context for all agents.
            guardrails: Rules all agents must follow.

        Returns:
            List of (story, result) tuples.
        """
        # Take up to max_workers stories
        batch = stories[: self.max_workers]
        if not batch:
            return []

        logger.info(f"Launching {len(batch)} parallel workers")

        # Create worktrees and spawn agents
        tasks = []
        for story in batch:
            worker_id = uuid.uuid4().hex[:8]
            branch = f"forgegod/{story.id}-{worker_id}"
            worktree_path = self._worktree_base / worker_id

            # Create worktree
            created = await self._create_worktree(str(worktree_path), branch)
            if not created:
                logger.warning(f"Failed to create worktree for {story.id}")
                continue

            worker = WorkerStatus(
                worker_id=worker_id,
                worktree_path=str(worktree_path),
                branch=branch,
                story_id=story.id,
                status="running",
            )
            self._workers.append(worker)

            # Spawn agent task
            tasks.append(
                self._run_worker(worker, story, project_context, guardrails or [])
            )

        # Execute all workers in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        output: list[tuple[Story, AgentResult]] = []
        for i, (story, result) in enumerate(
            zip(batch, results, strict=False)
        ):
            if isinstance(result, Exception):
                logger.error(f"Worker for {story.id} failed: {result}")
                agent_result = AgentResult(
                    success=False, error=str(result)
                )
            else:
                agent_result = result

            output.append((story, agent_result))

        # Cleanup worktrees
        await self._cleanup_all()

        return output

    async def _run_worker(
        self,
        worker: WorkerStatus,
        story: Story,
        context: str,
        guardrails: list[str],
    ) -> AgentResult:
        """Run a single worker in its worktree."""
        # Build task prompt
        prompt = f"""## Story: [{story.id}] {story.title}
{story.description}

## Acceptance Criteria
"""
        for ac in story.acceptance_criteria:
            prompt += f"- {ac}\n"

        if guardrails:
            prompt += "\n## Guardrails\n"
            for g in guardrails:
                prompt += f"- {g}\n"

        if context:
            prompt += f"\n## Project Context\n{context[:3000]}\n"

        prompt += f"\nWorking in worktree: {worker.worktree_path}\n"
        prompt += f"Branch: {worker.branch}\n"
        prompt += (
            "\nImplement the story, run tests, review the diff, "
            "and stop without committing.\n"
        )

        # Create agent scoped to worktree
        worker_config = self.config.model_copy(deep=True)
        worker_config.project_dir = Path(worker.worktree_path) / ".forgegod"
        agent = Agent(
            config=worker_config,
            router=self.router,
            budget=self.budget,
            role="coder",
            max_turns=50,
        )

        result = await agent.run(prompt)
        worker.status = "done" if result.success else "failed"
        worker.result = result
        return result

    async def merge_results(
        self, results: list[tuple[Story, AgentResult]]
    ) -> list[str]:
        """Merge successful worktree branches back to main.

        Returns list of merged branch names.
        """
        merged = []
        for story, result in results:
            if not result.success:
                continue

            worker = next(
                (w for w in self._workers if w.story_id == story.id), None
            )
            if not worker:
                continue

            # Merge branch
            merge_result = await _run_git(
                "merge",
                worker.branch,
                "--no-ff",
                "-m",
                f"Merge {story.id}: {story.title}",
                cwd=self.config.project_dir.parent,
            )
            if merge_result.startswith("Error"):
                logger.warning(f"Merge failed for {worker.branch}: {merge_result}")
            else:
                merged.append(worker.branch)
                logger.info(f"Merged {worker.branch}")

        return merged

    async def _create_worktree(self, path: str, branch: str) -> bool:
        """Create a git worktree for a worker."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # Create branch from HEAD
        await _run_git("branch", branch, "HEAD", cwd=self.config.project_dir.parent)
        result = await _run_git(
            "worktree",
            "add",
            path,
            branch,
            cwd=self.config.project_dir.parent,
        )
        if result.startswith("Error"):
            logger.error(f"Worktree creation failed: {result}")
            return False
        return True

    async def _cleanup_all(self):
        """Remove all worktrees created by this pool."""
        for worker in self._workers:
            try:
                await _run_git(
                    "worktree",
                    "remove",
                    "--force",
                    worker.worktree_path,
                    cwd=self.config.project_dir.parent,
                )
                await _run_git(
                    "branch",
                    "-D",
                    worker.branch,
                    cwd=self.config.project_dir.parent,
                )
            except Exception as e:
                logger.debug(f"Cleanup error for {worker.worker_id}: {e}")
        self._workers.clear()
