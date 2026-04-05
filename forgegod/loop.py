"""ForgeGod Ralph Loop — 24/7 autonomous coding with context rotation.

Ported from forge/forge_god_engine.py (Phase 76).
Stripped: Redis state, NATS events, soul/hormones, DGM archive.
Kept: Perpetual loop, killswitch, gutter detection, context rotation, scoring.

The key insight: progress lives in git + prd.json + learnings, NOT in LLM context.
Each iteration spawns a fresh agent that picks up from file state.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from forgegod.agent import Agent
from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.memory import Memory
from forgegod.models import (
    PRD,
    BudgetMode,
    LoopState,
    LoopStatus,
    ReviewVerdict,
    Story,
    StoryStatus,
)
from forgegod.reviewer import Reviewer
from forgegod.router import ModelRouter
from forgegod.terse import TERSE_STORY_INSTRUCTIONS

logger = logging.getLogger("forgegod.loop")
console = Console()


class RalphLoop:
    """24/7 autonomous coding loop — the god loop.

    Lifecycle per tick:
    1. Read prd.json → pick highest priority "todo" story
    2. Set story status = "in_progress"
    3. Spawn agent with story context + repo state
    4. Agent implements story (uses tools, Reflexion coder)
    5. Run validation (tests, lint, type check)
    6. If pass: commit, set status = "done", append learnings
    7. If fail (3 retries): set status = "blocked", log error
    8. If context > 80%: rotate context (fresh agent, git-based memory)
    9. Check KILLSWITCH → if set, stop
    10. Repeat from step 1
    """

    def __init__(
        self,
        config: ForgeGodConfig,
        prd: PRD,
        router: ModelRouter | None = None,
        budget: BudgetTracker | None = None,
        max_iterations: int | None = None,
    ):
        self.config = config
        self.prd = prd
        self.router = router or ModelRouter(config)
        self.budget = budget or BudgetTracker(config)
        self.max_iterations = max_iterations or config.loop.max_iterations

        # Reviewer (SOTA: sample-based quality gate)
        self.reviewer = Reviewer(config=config, router=self.router)

        # Memory system — shared across all story ticks
        try:
            self.memory = Memory(config)
        except Exception:
            self.memory = None
            logger.debug("Memory system unavailable in loop")

        # Memory Agent — dedicated LLM-powered memory extraction
        self._memory_agent = None
        if self.memory:
            try:
                from forgegod.memory_agent import MemoryAgent

                self._memory_agent = MemoryAgent(
                    config=config, router=self.router, memory=self.memory,
                )
            except Exception:
                logger.debug("MemoryAgent unavailable")

        # State
        self.state = LoopState()
        self._running = False
        self._state_path = config.project_dir / "state.json"
        self._prd_path = config.project_dir / "prd.json"
        self._killswitch_path = config.project_dir / "KILLSWITCH"
        self._learnings_path = config.project_dir / "progress.txt"

    async def run(self, dry_run: bool = False) -> LoopState:
        """Run the Ralph loop until complete or killed.

        Args:
            dry_run: If True, print story execution order and exit without running agents.
        """
        if dry_run:
            console.print(
                "[bold yellow]DRY RUN — No agents will be executed.[/bold yellow]"
            )
            console.print()
            console.print("[bold]Story Execution Order:[/bold]")
            console.print()
            for i, story in enumerate(self.prd.stories, 1):
                status = story.status
                console.print(f"  {i}. [{story.id}] {story.title}")
                console.print(f"     Status: {status.value}")
                if story.description:
                    console.print(f"     Description: {story.description[:200]}...")
                if story.files_touched:
                    console.print(f"     Files: {', '.join(story.files_touched)}")
                console.print()
            console.print("[bold green]Dry run complete.[/bold green]")
            self.state.status = LoopStatus.IDLE
            self._save_state()
            self._save_prd()
            return self.state

        self._running = True
        self.state.status = LoopStatus.RUNNING
        self.state.started_at = datetime.now(timezone.utc).isoformat()
        self._save_state()

        logger.info(
            f"Ralph loop started: {len(self.prd.stories)} stories, "
            f"max {self.max_iterations} iterations"
        )

        try:
            while self._running:
                await self._tick()

                # Check completion
                if self._all_done():
                    logger.info("All stories complete!")
                    self.state.status = LoopStatus.IDLE
                    break

                # Check iteration limit
                if self.state.total_iterations >= self.max_iterations:
                    logger.warning(f"Max iterations ({self.max_iterations}) reached")
                    break

                # Cooldown between ticks
                await asyncio.sleep(self.config.loop.cooldown_seconds)

        except asyncio.CancelledError:
            logger.info("Ralph loop cancelled")
        except Exception as e:
            logger.exception(f"Ralph loop error: {e}")
            self.state.status = LoopStatus.PAUSED

        self._save_state()
        self._save_prd()
        return self.state

    async def stop(self):
        """Stop the loop gracefully."""
        self._running = False

    async def _tick(self) -> None:
        """One tick of the Ralph loop."""
        self.state.total_iterations += 1
        self.state.last_tick_at = datetime.now(timezone.utc).isoformat()

        # 1. Check killswitch
        if self._is_killed():
            logger.info("KILLSWITCH detected — stopping")
            self.state.status = LoopStatus.KILLED
            self._running = False
            return

        # 2. Budget check
        effective_mode = self.budget.check_budget()
        if effective_mode == BudgetMode.HALT:
            logger.warning("Budget HALT — pausing loop")
            self.state.status = LoopStatus.PAUSED
            self._running = False
            return

        # 3. Pick next story
        story = self._next_story()
        if not story:
            logger.info("No stories ready — loop idle")
            return

        logger.info(f"Working on: [{story.id}] {story.title}")
        story.status = StoryStatus.IN_PROGRESS
        story.iterations += 1
        self.state.current_story_id = story.id
        self._save_state()
        self._save_prd()

        # 4. Build task prompt for agent
        task_prompt = self._build_story_prompt(story)

        # 5. Spawn fresh agent (context rotation — each story gets clean context)
        agent = Agent(
            config=self.config,
            router=self.router,
            budget=self.budget,
            role="coder",
            max_turns=100,
        )

        # 6. Execute
        result = await agent.run(task_prompt)

        # 7. Evaluate result
        if result.success:
            # Quality gate: sample-based frontier review (SOTA pattern)
            story_idx = self.prd.stories.index(story)
            if self.reviewer.should_review(story_idx):
                try:
                    review = await self.reviewer.review(
                        task=story.title,
                        code=result.output[:6000],
                        files_changed=result.files_modified,
                    )
                    if review.verdict == ReviewVerdict.REJECT:
                        logger.warning(
                            f"Story [{story.id}] REJECTED by reviewer: {review.reasoning}"
                        )
                        story.status = StoryStatus.TODO  # Retry with feedback
                        story.error_log.append(f"Reviewer rejected: {review.reasoning}")
                        self._save_prd()
                        return
                    if review.verdict == ReviewVerdict.REVISE and review.suggestions:
                        self.prd.learnings.append(
                            f"[{story.id}] Reviewer feedback: {'; '.join(review.suggestions[:3])}"
                        )
                except Exception as e:
                    logger.debug(f"Review skipped: {e}")

            story.status = StoryStatus.DONE
            story.completed_at = datetime.now(timezone.utc).isoformat()
            story.files_touched = result.files_modified
            self.state.stories_completed += 1
            self.state.total_cost_usd += result.total_usage.cost_usd
            self._append_learning(story, result.output)
            logger.info(
                f"Story [{story.id}] DONE — {result.tool_calls_count} tool calls, "
                f"${result.total_usage.cost_usd:.4f}"
            )
            # Auto-push to remote after successful story
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "push", "origin", "main",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    logger.info(f"Story [{story.id}] pushed to origin/main")
            except Exception:
                logger.debug("Auto-push skipped")
        else:
            # Check retry limit
            if story.iterations >= self.config.loop.story_max_retries:
                story.status = StoryStatus.BLOCKED
                story.error_log.append(result.error or result.output)
                self.state.stories_failed += 1
                logger.warning(
                    f"Story [{story.id}] BLOCKED after {story.iterations} attempts"
                )
            else:
                story.status = StoryStatus.TODO  # Will retry next tick
                story.error_log.append(result.error or result.output)
                logger.info(
                    f"Story [{story.id}] failed attempt {story.iterations}, "
                    f"will retry ({self.config.loop.story_max_retries - story.iterations} left)"
                )

        # 8. Dedicated MemoryAgent — LLM-powered extraction
        if self._memory_agent:
            try:
                await self._memory_agent.process_coding_task(
                    task_description=story.description or story.title,
                    result=result,
                    task_id=story.id,
                )
            except Exception as e:
                logger.debug(f"MemoryAgent extraction skipped: {e}")

        # 9. Auto-consolidate memory (AutoDream pattern)
        if self.memory:
            try:
                self.memory.maybe_consolidate()
            except Exception as e:
                logger.debug(f"Memory consolidation skipped: {e}")

        # 9. Context rotation tracking
        self.state.context_rotations += 1
        self.state.current_story_id = ""
        self._save_state()
        self._save_prd()

    def _next_story(self) -> Story | None:
        """Get the next story to work on (highest priority TODO)."""
        todos = [s for s in self.prd.stories if s.status == StoryStatus.TODO]
        if not todos:
            return None
        return min(todos, key=lambda s: s.priority)

    def _all_done(self) -> bool:
        """Check if all stories are done or blocked."""
        return all(
            s.status in (StoryStatus.DONE, StoryStatus.BLOCKED, StoryStatus.SKIPPED)
            for s in self.prd.stories
        )

    def _build_story_prompt(self, story: Story) -> str:
        """Build the full task prompt for a story."""
        prompt = f"""## Project: {self.prd.project}
{self.prd.description}

## Current Story: [{story.id}] {story.title}
{story.description}

## Acceptance Criteria
"""
        for ac in story.acceptance_criteria:
            prompt += f"- {ac}\n"

        if self.prd.guardrails:
            prompt += "\n## Guardrails (NEVER violate these)\n"
            for g in self.prd.guardrails:
                prompt += f"- {g}\n"

        if self.prd.learnings:
            prompt += "\n## Learnings from previous stories\n"
            for learning in self.prd.learnings[-5:]:
                prompt += f"- {learning}\n"

        if story.error_log:
            prompt += "\n## Previous attempt errors (FIX THESE)\n"
            for err in story.error_log[-2:]:
                prompt += f"- {err[:500]}\n"

        # Inject relevant memory for this story
        if self.memory:
            try:
                mem_text = self.memory.smart_recall(story.title)
                if mem_text:
                    prompt += f"\n## Memory (from previous tasks)\n{mem_text}\n"
            except Exception:
                pass

        if self.config.terse.enabled:
            prompt += TERSE_STORY_INSTRUCTIONS
        else:
            prompt += """
## Instructions (MANDATORY — follow in ORDER)
1. Call `repo_map` to orient yourself in the codebase
2. Call `read_file` on the specific files relevant to this story
3. Call `write_file` or `edit_file` to CREATE/MODIFY actual files — you MUST produce file changes
4. Call `bash` to run `python -m pytest tests/ -x -v` (or relevant tests) to verify
5. Call `bash` to run `git add . && git commit -m "story_id: description"` to commit

CRITICAL: You MUST use `write_file` or `edit_file` tools to make actual code changes.
Do NOT just describe what you would do — actually DO it by calling the tools.
If the story says "add tests", CREATE the test file with `write_file`.
If the story says "add type hints", EDIT the file with `edit_file`.
"""
        return prompt

    def _is_killed(self) -> bool:
        """Check if killswitch file exists."""
        return self._killswitch_path.exists()

    def _append_learning(self, story: Story, output: str):
        """Append a learning from a completed story."""
        learning = f"[{story.id}] {story.title}: completed"
        self.prd.learnings.append(learning)

        # Also append to progress.txt for human readability
        self._learnings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._learnings_path, "a", encoding="utf-8") as f:
            f.write(
                f"\n[{datetime.now(timezone.utc).isoformat()}] "
                f"{story.id} — {story.title}\n"
                f"  Files: {', '.join(story.files_touched)}\n"
            )

    def _save_state(self):
        """Persist loop state to JSON."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            self.state.model_dump_json(indent=2), encoding="utf-8"
        )

    def _save_prd(self):
        """Persist PRD to JSON."""
        self._prd_path.parent.mkdir(parents=True, exist_ok=True)
        self._prd_path.write_text(
            self.prd.model_dump_json(indent=2), encoding="utf-8"
        )

    @classmethod
    def from_prd_file(
        cls,
        prd_path: Path,
        config: ForgeGodConfig,
        **kwargs,
    ) -> "RalphLoop":
        """Create a RalphLoop from a PRD JSON file."""
        data = json.loads(prd_path.read_text(encoding="utf-8"))
        prd = PRD(**data)
        return cls(config=config, prd=prd, **kwargs)
