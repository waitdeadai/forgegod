"""ForgeGod Hive -- multi-process coordinator with central brain."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.loop import RalphLoop
from forgegod.models import PRD, HiveState, HiveWorkerPayload, HiveWorkerResult, Story, StoryStatus
from forgegod.router import ModelRouter
from forgegod.tools.git import _run_git
from forgegod.worktree import WorktreePool

logger = logging.getLogger("forgegod.hive")


@dataclass
class HiveWorker:
    worker_id: str
    story_id: str
    branch: str
    worktree_path: Path
    payload_path: Path
    result_path: Path


class HiveCoordinator:
    """Coordinate multi-process ForgeGod workers with a central planner."""

    def __init__(
        self,
        config: ForgeGodConfig,
        *,
        router: ModelRouter | None = None,
        budget: BudgetTracker | None = None,
        worker_runner=None,
    ) -> None:
        self.config = config
        self.router = router or ModelRouter(config)
        self.budget = budget or BudgetTracker(config)
        self.worker_runner = worker_runner or self._run_worker_process

        self.state = HiveState()
        self._state_path = self.config.project_dir / "hive" / "state.json"
        self._results_dir = self.config.project_dir / "hive" / "results"
        self._queue_dir = self.config.project_dir / "hive" / "queue"
        self._worktree_base = self.config.project_dir / "worktrees"
        self._obsidian = None
        if self.config.obsidian.enabled:
            try:
                from forgegod.obsidian import ObsidianAdapter

                adapter = ObsidianAdapter(config)
                if adapter.is_configured():
                    self._obsidian = adapter
            except Exception as exc:
                logger.debug("Obsidian adapter unavailable: %s", exc)

    async def run(
        self,
        prd_path: Path,
        *,
        max_iterations: int | None = None,
        max_workers: int | None = None,
        dry_run: bool = False,
    ) -> HiveState:
        """Run hive batches until done or iteration limit reached."""
        prd = PRD(**json.loads(prd_path.read_text(encoding="utf-8")))
        loop_helper = RalphLoop(config=self.config, prd=prd, router=self.router)

        workers = max_workers or self.config.hive.max_workers
        iterations = max_iterations or self.config.hive.max_iterations
        if self.config.security.approval_mode == "prompt":
            raise RuntimeError(
                "Hive mode does not support prompt approvals. "
                "Use approval_mode=approve or approval_mode=deny."
            )
        self.state.status = "running"
        self._save_state()

        readiness_error = await WorktreePool(self.config).ensure_parallel_ready()
        if readiness_error:
            self.state.status = "paused"
            self._save_state()
            raise RuntimeError(readiness_error)

        for _ in range(iterations):
            ready = self._get_ready_stories(prd, max_count=workers)
            if not ready:
                self.state.status = "idle"
                self._save_state()
                break

            selected = await self._plan_batch(prd, ready, max_workers=workers)
            if not selected:
                selected = ready[:workers]

            self.state.current_batch = [s.id for s in selected]
            self.state.total_iterations += 1
            self._save_state()

            if dry_run:
                break

            for story in selected:
                story.status = StoryStatus.IN_PROGRESS

            await self._run_batch(loop_helper, prd, selected)
            self._save_prd(prd_path, prd)
            self._save_state()
            self._export_hive_summary(prd)

            if self._all_done(prd):
                self.state.status = "idle"
                self._save_state()
                break

        self._export_hive_summary(prd)
        return self.state

    async def _plan_batch(
        self,
        prd: PRD,
        ready: list[Story],
        *,
        max_workers: int,
    ) -> list[Story]:
        if self.config.hive.scheduler_mode != "hybrid":
            return ready[:max_workers]

        payload = [
            {
                "id": s.id,
                "title": s.title,
                "priority": s.priority,
                "depends_on": s.depends_on,
                "files_touched": s.files_touched,
            }
            for s in ready
        ]
        prompt = f"""You are the hive planner. Select up to {max_workers} story IDs to run in parallel.

Rules:
- Only choose from READY stories.
- Avoid selecting stories that touch overlapping files.
- Prefer higher priority.

Return JSON only:
{{"selected_story_ids": ["T001"], "reasoning": "why"}}

Ready stories:
{json.dumps(payload, indent=2)}
"""
        response, _usage = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=800,
            temperature=0.2,
        )
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return ready[:max_workers]

        selected_ids = {str(sid) for sid in data.get("selected_story_ids", [])}
        filtered = [s for s in ready if s.id in selected_ids]
        if not filtered:
            return ready[:max_workers]
        return self._filter_conflicts(filtered, max_workers=max_workers)

    async def _run_batch(
        self,
        loop_helper: RalphLoop,
        prd: PRD,
        stories: list[Story],
    ) -> None:
        scheduled: list[tuple[Story, HiveWorker]] = []
        self._queue_dir.mkdir(parents=True, exist_ok=True)
        self._results_dir.mkdir(parents=True, exist_ok=True)

        for story in stories:
            worker_id = uuid.uuid4().hex[:8]
            branch = f"forgegod/hive/{story.id}-{worker_id}"
            worktree_path = self._worktree_base / worker_id
            if not await self._create_worktree(worktree_path, branch):
                story.status = StoryStatus.BLOCKED
                story.error_log.append("Failed to create worktree")
                self.state.stories_failed += 1
                continue

            await self._sync_worktree_config(worktree_path)
            prompt = await loop_helper._build_story_prompt(story)

            payload = HiveWorkerPayload(
                task=prompt,
                story_id=story.id,
                review=True,
                permission_mode=self.config.security.permission_mode,
                approval_mode=self.config.security.approval_mode,
                allowed_tools=self.config.security.allowed_tools,
                terse=self.config.terse.enabled,
                subagents_enabled=self.config.subagents.enabled,
            )
            payload_path = self._queue_dir / f"{worker_id}.json"
            result_path = self._results_dir / f"{worker_id}.json"
            payload_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

            scheduled.append((story, HiveWorker(
                worker_id=worker_id,
                story_id=story.id,
                branch=branch,
                worktree_path=worktree_path,
                payload_path=payload_path,
                result_path=result_path,
            )))

        results = await asyncio.gather(
            *[self.worker_runner(worker) for _, worker in scheduled],
            return_exceptions=True,
        )

        for (story, worker), result in zip(scheduled, results, strict=False):
            if isinstance(result, Exception):
                story.status = StoryStatus.BLOCKED
                story.error_log.append(str(result))
                self.state.stories_failed += 1
                await self._cleanup_worker(worker)
                continue

            if not result.success:
                story.status = StoryStatus.BLOCKED
                if result.error:
                    story.error_log.append(result.error)
                self.state.stories_failed += 1
                await self._cleanup_worker(worker)
                continue

            if result.files_modified:
                apply_status = await self._apply_patch(worker, result.files_modified, story_id=story.id)
                if apply_status != "applied":
                    story.status = StoryStatus.BLOCKED
                    story.error_log.append(apply_status)
                    self.state.stories_failed += 1
                    await self._cleanup_worker(worker)
                    continue

            story.status = StoryStatus.DONE
            story.completed_at = datetime.now(timezone.utc).isoformat()
            story.files_touched = result.files_modified
            self.state.stories_completed += 1
            await self._cleanup_worker(worker)

    async def _run_worker_process(self, worker: HiveWorker) -> HiveWorkerResult:
        cmd = [
            sys.executable,
            "-m",
            "forgegod",
            "worker",
            "--payload",
            str(worker.payload_path),
            "--json-out",
            str(worker.result_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(worker.worktree_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip() or stdout.decode(
                "utf-8", errors="replace"
            ).strip()
            return HiveWorkerResult(
                story_id=worker.story_id,
                success=False,
                exit_code=proc.returncode,
                error=detail or "worker failed",
            )

        if worker.result_path.exists():
            try:
                data = json.loads(worker.result_path.read_text(encoding="utf-8"))
                return HiveWorkerResult(**data)
            except Exception as exc:
                return HiveWorkerResult(
                    story_id=worker.story_id,
                    success=False,
                    exit_code=proc.returncode,
                    error=f"Invalid worker result: {exc}",
                )

        return HiveWorkerResult(
            story_id=worker.story_id,
            success=False,
            exit_code=proc.returncode,
            error="Worker did not emit a result file",
        )

    async def _create_worktree(self, path: Path, branch: str) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        result = await _run_git(
            "worktree",
            "add",
            "-b",
            branch,
            str(path),
            cwd=self.config.project_dir.parent,
        )
        if result.startswith("Error"):
            logger.warning(result)
            return False
        return True

    async def _apply_patch(self, worker: HiveWorker, files_modified: list[str], story_id: str) -> str:
        if files_modified:
            add_result = await _run_git(
                "add",
                "-N",
                *files_modified,
                cwd=worker.worktree_path,
            )
            if add_result.startswith("Error"):
                return add_result

        proc = await asyncio.create_subprocess_exec(
            "git",
            "diff",
            "--binary",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(worker.worktree_path),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip() or stdout.decode(
                "utf-8", errors="replace"
            ).strip()
            return f"Error: Failed to get patch for {story_id}: {detail}"
        if not stdout:
            return "Error: Worktree produced no patch to apply"

        apply_proc = await asyncio.create_subprocess_exec(
            "git",
            "apply",
            "--3way",
            "--whitespace=nowarn",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.config.project_dir.parent),
        )
        assert apply_proc.stdin is not None
        apply_stdout, apply_stderr = await apply_proc.communicate(stdout)
        if apply_proc.returncode != 0:
            detail = apply_stderr.decode("utf-8", errors="replace").strip() or apply_stdout.decode(
                "utf-8", errors="replace"
            ).strip()
            return f"Error: Failed to apply patch for {story_id}: {detail}"
        return "applied"

    async def _cleanup_worker(self, worker: HiveWorker) -> None:
        await _run_git(
            "worktree",
            "remove",
            "--force",
            str(worker.worktree_path),
            cwd=self.config.project_dir.parent,
        )
        await _run_git(
            "branch",
            "-D",
            worker.branch,
            cwd=self.config.project_dir.parent,
        )
        try:
            if worker.payload_path.exists():
                worker.payload_path.unlink()
        except OSError:
            pass

    async def _sync_worktree_config(self, worktree_path: Path) -> None:
        main_config_dir = self.config.project_dir
        worktree_config_dir = worktree_path / ".forgegod"
        worktree_config_dir.mkdir(parents=True, exist_ok=True)

        config_path = main_config_dir / "config.toml"
        if config_path.exists():
            shutil.copy2(config_path, worktree_config_dir / "config.toml")
        env_path = main_config_dir / ".env"
        if env_path.exists():
            shutil.copy2(env_path, worktree_config_dir / ".env")

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")

    def _export_hive_summary(self, prd: PRD) -> None:
        if not self._obsidian:
            return
        try:
            self._obsidian.export_hive_summary(prd=prd, state=self.state)
        except Exception as exc:  # pragma: no cover - optional integration
            logger.debug("Obsidian hive export skipped: %s", exc)

    @staticmethod
    def _save_prd(prd_path: Path, prd: PRD) -> None:
        prd_path.write_text(prd.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def _all_done(prd: PRD) -> bool:
        return all(
            story.status in (StoryStatus.DONE, StoryStatus.BLOCKED, StoryStatus.SKIPPED)
            for story in prd.stories
        )

    @staticmethod
    def _filter_conflicts(stories: list[Story], *, max_workers: int) -> list[Story]:
        selected: list[Story] = []
        seen_files: set[str] = set()
        for story in stories:
            if len(selected) >= max_workers:
                break
            story_files = set(story.files_touched or [])
            if story_files and seen_files & story_files:
                continue
            selected.append(story)
            seen_files.update(story_files)
        return selected

    @staticmethod
    def _get_ready_stories(prd: PRD, *, max_count: int) -> list[Story]:
        done_ids = {s.id for s in prd.stories if s.status == StoryStatus.DONE}
        in_progress_ids = {
            s.id for s in prd.stories if s.status == StoryStatus.IN_PROGRESS
        }
        ready = []
        for s in prd.stories:
            if s.status != StoryStatus.TODO:
                continue
            if s.depends_on and not all(d in done_ids for d in s.depends_on):
                continue
            if in_progress_ids and s.files_touched:
                in_progress_files = set()
                for ip in prd.stories:
                    if ip.status == StoryStatus.IN_PROGRESS:
                        in_progress_files.update(ip.files_touched)
                if in_progress_files & set(s.files_touched):
                    continue
            ready.append(s)
        ready.sort(key=lambda s: s.priority)
        return ready[:max_count]
