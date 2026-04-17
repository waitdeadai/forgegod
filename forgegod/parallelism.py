"""ForgeGod parallelism recommender for execution topology selection.

Recommends optimal parallelism strategy based on task complexity:
- Sequential: small tasks (overhead doesn't justify)
- Subagents: medium tasks with independent subtasks
- Hive: large tasks requiring multi-process coordination
- Research-first: architectural decisions requiring web research before execution
"""

from __future__ import annotations

import re

from forgegod.config import ForgeGodConfig
from forgegod.models import (
    ParallelismMode,
    ParallelismRecommendation,
    ResearchBrief,
)

# Architectural decision keywords
ARCHITECTURE_KEYWORDS = [
    "architecture",
    "architectural",
    "patrón",
    "pattern",
    "sota",
    "best practice",
    "design decision",
    "framework",
    "system design",
    "trade-off",
    "migration",
    "refactor to",
    "switch from",
]


def _estimate_task_complexity(task: str) -> tuple[int, int]:
    """Estimate task complexity from natural language.

    Returns:
        Tuple of (estimated_lines, estimated_files)

    Heuristics:
    - Mentions of specific files/modules add +1 file
    - Technical terms suggest larger scope
    - "simple", "quick" suggest smaller scope
    - "multiple", "several", "complex" suggest larger scope
    """
    task_lower = task.lower()

    # Estimate files
    files_estimate = 1
    if any(k in task_lower for k in ["multiple", "several", "multi", "several"]):
        files_estimate = 3
    if any(k in task_lower for k in ["microservices", "distributed", "multi-process"]):
        files_estimate = 5

    # Mentions of specific patterns suggest more files
    module_mentions = len(re.findall(r"\b(?:module|file|class|service|api)\b", task_lower))
    files_estimate += min(module_mentions, 5)

    # Estimate lines
    lines_estimate = 50  # baseline
    if any(k in task_lower for k in ["simple", "quick", "small", "tiny", "one"]):
        lines_estimate = 30
    if any(k in task_lower for k in ["complex", "large", "big", "extensive", "comprehensive"]):
        lines_estimate = 300
    if any(k in task_lower for k in ["entire", "full", "system", "rebuild"]):
        lines_estimate = 500

    # Add more lines for each technical term
    technical_terms = len(re.findall(
        r"\b(?:database|api|authentication|validation|cache|queue|async|concurrent)\b",
        task_lower
    ))
    lines_estimate += technical_terms * 20

    return lines_estimate, files_estimate


def _is_architectural_decision(task: str, brief: ResearchBrief | None = None) -> bool:
    """Check if task involves architectural decision requiring research-first."""
    task_lower = task.lower()

    # Check for architecture keywords
    for keyword in ARCHITECTURE_KEYWORDS:
        if keyword in task_lower:
            return True

    # If research brief indicates architecture patterns, flag it
    if brief and brief.architecture_patterns:
        return True

    return False


def recommend_parallelism(
    task: str,
    config: ForgeGodConfig,
    research_brief: ResearchBrief | None = None,
) -> ParallelismRecommendation:
    """Recommend parallelism strategy based on task complexity.

    Decision tree:
    1. Architectural decision or architecture-heavy research brief → RESEARCH_FIRST
    2. If estimated_lines >= 500 and estimated_files >= 5 → HIVE
    3. If estimated_lines >= 50 and estimated_files >= 2 → SUBAGENTS
    4. Otherwise → SEQUENTIAL

    Args:
        task: Natural language task description
        config: ForgeGod configuration
        research_brief: Optional existing research brief

    Returns:
        ParallelismRecommendation with mode, workers, reasoning
    """
    estimated_lines, estimated_files = _estimate_task_complexity(task)

    research_recommended = bool(config.agent.research_before_code)

    # Rule 1: Research-first is reserved for architecture-heavy decisions.
    if _is_architectural_decision(task, research_brief):
        return ParallelismRecommendation(
            mode=ParallelismMode.RESEARCH_FIRST,
            workers=1,
            reasoning=(
                f"Architectural decision detected. Research-backed design work should "
                f"finish before implementation starts. Task: {task[:80]}..."
            ),
            research_recommended=True,
            estimated_speedup="1.5-2x (quality improvement from SOTA research)",
        )

    # Rule 2: Hive for large tasks
    if estimated_lines >= 500 and estimated_files >= 5:
        workers = min(config.hive.max_workers, 8)
        return ParallelismRecommendation(
            mode=ParallelismMode.HIVE,
            workers=workers,
            reasoning=(
                f"Large task: ~{estimated_lines} lines across ~{estimated_files} files. "
                f"Multi-process coordination recommended."
                + (
                    " Run research first because research_before_code is enabled."
                    if research_recommended else ""
                )
            ),
            research_recommended=research_recommended,
            estimated_speedup=f"{workers}-8x faster",
        )

    # Rule 3: Subagents for medium tasks
    if estimated_lines >= 50 and estimated_files >= 2:
        workers = min(config.subagents.max_concurrency, estimated_files)
        return ParallelismRecommendation(
            mode=ParallelismMode.SUBAGENTS,
            workers=workers,
            reasoning=(
                f"Medium task: ~{estimated_lines} lines across ~{estimated_files} files. "
                f"Subagent parallelization with {workers} workers."
                + (
                    " Run research first because research_before_code is enabled."
                    if research_recommended else ""
                )
            ),
            research_recommended=research_recommended,
            estimated_speedup=f"{workers}-4x faster",
        )

    # Rule 4: Sequential for small tasks
    return ParallelismRecommendation(
        mode=ParallelismMode.SEQUENTIAL,
        workers=1,
        reasoning=(
            f"Small task: ~{estimated_lines} lines, ~{estimated_files} file. "
            f"Sequential execution avoids parallelism overhead."
            + (
                " Research is still recommended before code changes."
                if research_recommended else ""
            )
        ),
        research_recommended=research_recommended,
        estimated_speedup="1x (baseline)",
    )
