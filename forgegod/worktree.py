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
        tool_approver=None,
    ):
        self.config = config
        self.router = router or ModelRouter(config)
        self.budget = budget or BudgetTracker(config)
        self.max_workers = max_workers or config.loop.parallel_workers
        self.tool_approver = tool_approver
        self._workers: list[WorkerStatus] = []
        self._worktree_base = config.project_dir / "worktrees"

        if config.security.approval_mode == "prompt":
            if self.max_workers > 1:
                raise ValueError(
                    "Prompt approval mode is only supported with WorktreePool max_workers=1."
                )
            if self.tool_approver is None:
                raise ValueError(
                    "Prompt approval mode requires a tool_approver callback for WorktreePool."
                )

    async def run_parallel(
        self,
        stories: list[Story],
        project_context: str = "",
        guardrails: list[str] | None = None,
        story_prompts: dict[str, str] | None = None,
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
        scheduled: list[tuple[Story, asyncio.Task[AgentResult]]] = []
        output: list[tuple[Story, AgentResult]] = []
        for story in batch:
            worker_id = uuid.uuid4().hex[:8]
            branch = f"forgegod/{story.id}-{worker_id}"
            worktree_path = self._worktree_base / worker_id

            # Create worktree
            created = await self._create_worktree(str(worktree_path), branch)
            if not created:
                logger.warning(f"Failed to create worktree for {story.id}")
                output.append((
                    story,
                    AgentResult(
                        success=False,
                        error=(
                            f"Failed to create isolated git worktree for story {story.id}. "
                            "Parallel workers require a healthy git repository, at least one "
                            "commit, and worktree support."
                        ),
                    ),
                ))
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
            scheduled.append((
                story,
                asyncio.create_task(
                    self._run_worker(
                        worker,
                        story,
                        project_context,
                        guardrails or [],
                        prompt_override=(story_prompts or {}).get(story.id),
                    )
                ),
            ))

        # Execute all workers in parallel
        if not scheduled:
            await self._cleanup_all()
            return output

        results = await asyncio.gather(
            *[task for _, task in scheduled],
            return_exceptions=True,
        )

        # Collect results
        for (story, _task), result in zip(scheduled, results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"Worker for {story.id} failed: {result}")
                agent_result = AgentResult(
                    success=False, error=str(result)
                )
            else:
                agent_result = result

            output.append((story, agent_result))

        return output

    async def _run_worker(
        self,
        worker: WorkerStatus,
        story: Story,
        context: str,
        guardrails: list[str],
        prompt_override: str | None = None,
    ) -> AgentResult:
        """Run a single worker in its worktree."""
        # Build task prompt
        prompt = prompt_override or f"""## Story: [{story.id}] {story.title}
{story.description}

## Acceptance Criteria
"""
        if prompt_override is None:
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
            tool_approver=self.tool_approver,
        )

        timeout_s = self.config.loop.story_timeout_s or 600.0
        try:
            result = await asyncio.wait_for(agent.run(prompt), timeout=timeout_s)
        except asyncio.TimeoutError:
            result = AgentResult(
                success=False,
                error=f"Story timed out after {timeout_s}s (dead-man's switch)",
            )
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

        result = await _run_git(
            "worktree",
            "add",
            "-b",
            branch,
            path,
            cwd=self.config.project_dir.parent,
        )
        if result.startswith("Error"):
            logger.error(f"Worktree creation failed: {result}")
            return False
        return True

    def get_worker(self, story_id: str) -> WorkerStatus | None:
        """Return the current worker object for a story id."""
        return next((w for w in self._workers if w.story_id == story_id), None)

    async def diff_for_story(self, story_id: str, *, binary: bool = False) -> str:
        """Get the git diff for a worker story inside its isolated worktree."""
        worker = self.get_worker(story_id)
        if not worker:
            return f"Error: No worktree worker found for story {story_id}"

        if worker.result and worker.result.files_modified:
            add_result = await _run_git(
                "add",
                "-N",
                *worker.result.files_modified,
                cwd=Path(worker.worktree_path),
            )
            if add_result.startswith("Error"):
                return add_result

        args = ["git", "diff"]
        if binary:
            args.append("--binary")
        args.append("HEAD")
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(worker.worktree_path)),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if not detail:
                detail = stdout.decode("utf-8", errors="replace").strip()
            return f"Error (exit {proc.returncode}): {detail}"
        if not stdout:
            return "(no output)"
        return stdout.decode("utf-8", errors="replace")

    async def apply_patch_for_story(self, story_id: str) -> str:
        """Apply a worker worktree patch back onto the main workspace."""
        patch = await self.diff_for_story(story_id, binary=True)
        if patch.startswith("Error"):
            return patch
        if patch in {"", "(no output)", "(no changes)"}:
            return "Error: Worktree produced no patch to apply"

        proc = await asyncio.create_subprocess_exec(
            "git",
            "apply",
            "--3way",
            "--whitespace=nowarn",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.config.project_dir.parent),
        )
        assert proc.stdin is not None
        stdout, stderr = await proc.communicate(patch.encode("utf-8"))
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if not detail:
                detail = stdout.decode("utf-8", errors="replace").strip()
            return f"Error: Failed to apply worktree patch for {story_id}: {detail}"
        return "applied"

    async def ensure_parallel_ready(self) -> str | None:
        """Validate that the repo can support isolated parallel worktrees."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--is-inside-work-tree",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.config.project_dir.parent),
            )
        except FileNotFoundError:
            return "Git is not installed; parallel workers require git worktrees."

        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            return (
                "Parallel workers require a git repository because ForgeGod uses "
                f"isolated worktrees. Git reported: {detail or 'not a git worktree'}"
            )
        if stdout.decode("utf-8", errors="replace").strip().lower() != "true":
            return (
                "Parallel workers require a git repository because ForgeGod uses "
                "isolated worktrees."
            )

        head_check = await _run_git(
            "rev-parse",
            "--verify",
            "HEAD",
            cwd=self.config.project_dir.parent,
        )
        if head_check.startswith("Error"):
            return (
                "Parallel workers require at least one git commit before ForgeGod can "
                "create isolated worktrees."
            )
        return None

    async def cleanup(self):
        """Public cleanup hook for callers that merge/apply after execution."""
        await self._cleanup_all()

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
