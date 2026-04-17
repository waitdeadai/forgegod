"""ForgeGod MemoryAgent — LLM-powered post-task memory extraction.

Runs as a dedicated sub-agent after every coding and planning task.
Replaces heuristic extraction with intelligent LLM analysis to populate
all 5 memory tiers with high-quality, actionable learnings.
"""

from __future__ import annotations

import logging

from forgegod.config import ForgeGodConfig
from forgegod.json_utils import extract_json
from forgegod.memory import Memory
from forgegod.models import AgentResult
from forgegod.router import ModelRouter

logger = logging.getLogger("forgegod.memory_agent")

MEMORY_EXTRACTION_PROMPT = """Analyze this completed coding task and extract learnings.

## Task
{task_description}

## Outcome
Success: {success}
Files modified: {files}
Error: {error}
Output preview: {output_preview}
Model used: {model}
Cost: ${cost:.4f}
Duration: {duration:.1f}s

## Instructions
Extract structured learnings from this task outcome. Be specific and actionable.

Output ONLY valid JSON:
{{
  "semantic": [
    {{
      "text": "Specific principle learned",
      "category": "design|security|testing|architecture",
      "confidence": 0.5
    }}
  ],
  "procedural": [
    {{
      "name": "Pattern name",
      "trigger": "When to use this",
      "action": "What to do",
      "pattern_type": "fix|optimization|pattern|recipe"
    }}
  ],
  "error_solutions": [
    {{
      "error_pattern": "The error text pattern",
      "solution": "How to fix it",
      "context": "When this applies"
    }}
  ],
  "causal_edges": [
    {{
      "factor": "What caused the outcome",
      "outcome": "success|failure",
      "weight": 0.5
    }}
  ]
}}

Rules:
- Only extract learnings that are REUSABLE for future tasks
- Skip trivial observations ("code was written" is not a learning)
- Be specific: "Use aiosqlite for async SQLite" > "Use a database"
- If the task failed, focus on what went wrong and how to avoid it
- If the task succeeded, focus on what approach worked and why
- Empty arrays are fine if nothing is worth remembering
No markdown fences."""

PLANNING_MEMORY_PROMPT = """Analyze this completed planning/recon task and extract learnings.

## Task
{task_description}

## Research Brief
Libraries recommended: {libraries}
Patterns found: {patterns}
Warnings: {warnings}

## Plan Quality
Score: {score}/10
Converged: {converged}
Debate rounds: {rounds}

## Instructions
Extract learnings about the PLANNING PROCESS itself, not the code.

Output ONLY valid JSON:
{{
  "semantic": [
    {{
      "text": "Insight about planning approach",
      "category": "planning|research|architecture",
      "confidence": 0.5
    }}
  ],
  "procedural": [
    {{
      "name": "Planning pattern",
      "trigger": "When this planning approach works",
      "action": "Steps to follow",
      "pattern_type": "recipe"
    }}
  ]
}}

Focus on: which search queries found useful results, which libraries were
validated by the adversary, what the critic caught that the planner missed.
No markdown fences."""


class MemoryAgent:
    """Dedicated agent for intelligent post-task memory extraction.

    Runs after every coding/planning task to analyze outcomes and
    populate all 5 memory tiers with high-quality learnings.
    """

    def __init__(
        self,
        config: ForgeGodConfig,
        router: ModelRouter,
        memory: Memory,
    ):
        self.config = config
        self.router = router
        self.memory = memory
        self._obsidian = None
        if self.config.obsidian.enabled:
            try:
                from forgegod.obsidian import ObsidianAdapter

                adapter = ObsidianAdapter(config)
                if adapter.is_configured():
                    self._obsidian = adapter
            except Exception as exc:  # pragma: no cover - optional integration
                logger.debug("Obsidian adapter unavailable: %s", exc)

    async def process_coding_task(
        self,
        task_description: str,
        result: AgentResult,
        task_id: str = "",
    ) -> dict:
        """Extract and store memories from a completed coding task."""
        logger.info("MemoryAgent: analyzing coding task outcome")

        prompt = MEMORY_EXTRACTION_PROMPT.format(
            task_description=task_description[:500],
            success=result.success,
            files=", ".join(result.files_modified[:10]) or "none",
            error=(result.error or "none")[:300],
            output_preview=(result.output or "")[:300],
            model=result.total_usage.model,
            cost=result.total_usage.cost_usd,
            duration=result.total_usage.elapsed_s,
        )

        response, usage = await self.router.call(
            prompt=prompt,
            role="researcher",  # cheap model, fast
            json_mode=True,
            max_tokens=1024,
            temperature=0.2,
        )

        extractions = self._parse_extractions(response)
        await self._store_extractions(extractions, task_id)
        if self._obsidian:
            try:
                self._obsidian.export_memory_extraction_summary(
                    task_id=task_id or "coding-task",
                    task_description=task_description,
                    task_type="coding",
                    extractions=extractions,
                )
            except Exception as exc:  # pragma: no cover - optional integration
                logger.debug("Obsidian coding memory export skipped: %s", exc)

        logger.info(
            "MemoryAgent: stored %d semantic, %d procedural, "
            "%d error solutions, %d causal edges",
            len(extractions.get("semantic", [])),
            len(extractions.get("procedural", [])),
            len(extractions.get("error_solutions", [])),
            len(extractions.get("causal_edges", [])),
        )
        return extractions

    async def process_planning_task(
        self,
        task_description: str,
        libraries: list[str] | None = None,
        patterns: list[str] | None = None,
        warnings: list[str] | None = None,
        score: float = 0.0,
        converged: bool = False,
        rounds: int = 0,
    ) -> dict:
        """Extract and store memories from a planning/recon task."""
        logger.info("MemoryAgent: analyzing planning task outcome")

        prompt = PLANNING_MEMORY_PROMPT.format(
            task_description=task_description[:500],
            libraries=", ".join(libraries or [])[:300] or "none",
            patterns=", ".join(patterns or [])[:300] or "none",
            warnings=", ".join(warnings or [])[:300] or "none",
            score=score,
            converged=converged,
            rounds=rounds,
        )

        response, _ = await self.router.call(
            prompt=prompt,
            role="researcher",
            json_mode=True,
            max_tokens=1024,
            temperature=0.2,
        )

        extractions = self._parse_extractions(response)
        await self._store_extractions(extractions, f"plan_{task_description[:30]}")
        if self._obsidian:
            try:
                self._obsidian.export_memory_extraction_summary(
                    task_id=f"plan_{task_description[:30]}",
                    task_description=task_description,
                    task_type="planning",
                    extractions=extractions,
                )
            except Exception as exc:  # pragma: no cover - optional integration
                logger.debug("Obsidian planning memory export skipped: %s", exc)

        logger.info(
            "MemoryAgent: stored %d semantic, %d procedural from planning",
            len(extractions.get("semantic", [])),
            len(extractions.get("procedural", [])),
        )
        return extractions

    def _parse_extractions(self, response: str) -> dict:
        """Parse LLM extraction response."""
        try:
            data = extract_json(response)
        except ValueError:
            logger.warning("MemoryAgent: failed to parse extraction")
            return {}

        return {
            "semantic": data.get("semantic", []),
            "procedural": data.get("procedural", []),
            "error_solutions": data.get("error_solutions", []),
            "causal_edges": data.get("causal_edges", []),
        }

    async def _store_extractions(self, extractions: dict, task_id: str):
        """Store extracted learnings into memory tiers."""
        # Tier 2: Semantic memories
        for mem in extractions.get("semantic", []):
            text = mem.get("text", "")
            if not text or len(text) < 10:
                continue
            try:
                await self.memory.add_semantic(
                    text=text,
                    category=mem.get("category", "general"),
                    confidence=min(1.0, max(0.1, mem.get("confidence", 0.5))),
                    source_episode=task_id,
                )
            except Exception as e:
                logger.debug("Semantic store failed: %s", e)

        # Tier 3: Procedural memories
        for proc in extractions.get("procedural", []):
            name = proc.get("name", "")
            if not name:
                continue
            try:
                await self.memory.add_procedure(
                    name=name,
                    description=proc.get("action", ""),
                    pattern_type=proc.get("pattern_type", "pattern"),
                    trigger=proc.get("trigger", ""),
                    action=proc.get("action", ""),
                    source_episode=task_id,
                )
            except Exception as e:
                logger.debug("Procedural store failed: %s", e)

        # Tier 5: Error-Solution pairs
        for es in extractions.get("error_solutions", []):
            pattern = es.get("error_pattern", "")
            solution = es.get("solution", "")
            if not pattern or not solution:
                continue
            try:
                await self.memory.record_error_solution(
                    error_pattern=pattern,
                    error_context=es.get("context", ""),
                    solution=solution,
                )
            except Exception as e:
                logger.debug("Error-solution store failed: %s", e)

        # Tier 4: Causal edges
        for edge in extractions.get("causal_edges", []):
            factor = edge.get("factor", "")
            outcome = edge.get("outcome", "")
            if not factor or not outcome:
                continue
            try:
                await self.memory.add_causal_edge(
                    factor=factor,
                    outcome=outcome,
                    weight=min(1.0, max(0.1, edge.get("weight", 0.5))),
                )
            except Exception as e:
                logger.debug("Causal edge store failed: %s", e)
