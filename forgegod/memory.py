"""ForgeGod Memory — cross-session learning with principles and causal graph.

Ported from forge/forge_god_metacognition.py (Phase 78).
Stripped: Redis storage → SQLite, Qdrant semantic search.
Kept: Principle extraction, heuristic rules, causal graph, confidence scoring.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from forgegod.config import ForgeGodConfig
from forgegod.models import CausalEdge, Principle

logger = logging.getLogger("forgegod.memory")

# Heuristic rules: (condition, principle_text, category)
HEURISTIC_RULES: list[tuple[str, str, str]] = [
    ("test_pass_rate >= 0.95", "Write tests before implementation to reduce reflexion rounds", "testing"),
    ("test_pass_rate < 0.5", "Complex logic requires more test coverage", "testing"),
    ("reflexion_rounds <= 1", "Type hints reduce ambiguity and cut reflexion rounds", "readability"),
    ("reflexion_rounds >= 3", "Break complex functions into smaller units to reduce debugging", "design"),
    ("file_count > 5", "Use dependency injection for services with external resources", "architecture"),
    ("review_score >= 0.85", "Single Responsibility: each function does one thing well", "design"),
    ("security_issues > 0", "Validate all inputs at service boundaries", "security"),
]

CAUSAL_FACTORS = [
    "type_hints", "test_first", "small_functions", "error_handling",
    "input_validation", "dependency_injection", "guard_clauses",
    "docstrings", "async_patterns", "model_tier",
]


class Memory:
    """Cross-session learning engine — SQLite-backed principles + causal graph."""

    def __init__(self, config: ForgeGodConfig):
        self.config = config
        self._db_path = config.project_dir / "memory.db"
        self._ensure_db()

    def _ensure_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS principles (
                principle_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                category TEXT DEFAULT '',
                confidence REAL DEFAULT 0.3,
                evidence_count INTEGER DEFAULT 1,
                source_tasks TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS causal_edges (
                factor TEXT NOT NULL,
                outcome TEXT NOT NULL,
                weight REAL DEFAULT 0.0,
                observations INTEGER DEFAULT 0,
                PRIMARY KEY (factor, outcome)
            )
        """)
        conn.commit()
        conn.close()

    # ── Principle Management ──

    async def get_principles(self, category: str = "", min_confidence: float = 0.0) -> list[Principle]:
        """Get stored principles, optionally filtered."""
        conn = sqlite3.connect(str(self._db_path))
        if category:
            rows = conn.execute(
                "SELECT * FROM principles WHERE category = ? AND confidence >= ? ORDER BY confidence DESC",
                (category, min_confidence),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM principles WHERE confidence >= ? ORDER BY confidence DESC",
                (min_confidence,),
            ).fetchall()
        conn.close()
        return [self._row_to_principle(r) for r in rows]

    async def get_learnings_text(self, limit: int = 10) -> str:
        """Get top principles as text for injection into prompts (Memory Spine)."""
        principles = await self.get_principles(min_confidence=0.3)
        if not principles:
            return ""

        lines = ["## Learned Principles (from past outcomes)"]
        for p in principles[:limit]:
            lines.append(f"- [{p.category}] {p.text} (confidence: {p.confidence:.0%})")
        return "\n".join(lines)

    async def extract_principles(
        self,
        task_id: str,
        outcome: dict,
        code_files: list[dict] | None = None,
    ) -> list[Principle]:
        """Extract principles from a completed task.

        Args:
            task_id: Unique identifier for the task.
            outcome: Dict with keys like test_pass_rate, reflexion_rounds,
                    review_score, security_issues, file_count.
            code_files: Optional list of dicts with 'path' and 'content'.
        """
        extracted: list[Principle] = []

        # 1. Heuristic extraction
        extracted.extend(self._extract_from_heuristics(outcome, task_id))

        # 2. Code pattern extraction
        if code_files:
            extracted.extend(self._extract_from_code(code_files, task_id))

        # 3. Deduplicate against existing
        existing = await self.get_principles()
        new_principles: list[Principle] = []

        for candidate in extracted:
            match = self._find_match(candidate, existing)
            if match:
                await self._reinforce(match.principle_id, task_id)
            else:
                candidate.principle_id = f"pr-{uuid.uuid4().hex[:8]}"
                candidate.evidence_count = 1
                candidate.confidence = self._initial_confidence(outcome)
                candidate.source_tasks = [task_id]
                candidate.created_at = datetime.now(timezone.utc).isoformat()
                new_principles.append(candidate)
                await self._store_principle(candidate)

        # 4. Update causal graph
        await self._update_causal_graph(outcome, code_files)

        logger.info(
            f"Memory: extracted {len(extracted)} principles from {task_id} — "
            f"{len(new_principles)} new, {len(extracted) - len(new_principles)} reinforced"
        )
        return new_principles

    # ── Causal Graph ──

    async def get_causal_edges(self) -> list[CausalEdge]:
        """Get all edges in the causal graph."""
        conn = sqlite3.connect(str(self._db_path))
        rows = conn.execute(
            "SELECT factor, outcome, weight, observations FROM causal_edges ORDER BY weight DESC"
        ).fetchall()
        conn.close()
        return [
            CausalEdge(factor=r[0], outcome=r[1], weight=r[2], observations=r[3])
            for r in rows
        ]

    async def get_success_factors(self) -> list[str]:
        """Get factors most correlated with success."""
        edges = await self.get_causal_edges()
        success_edges = [e for e in edges if e.outcome == "success" and e.observations >= 3]
        success_edges.sort(key=lambda e: e.weight, reverse=True)
        return [e.factor for e in success_edges[:5]]

    # ── Internal ──

    def _extract_from_heuristics(self, outcome: dict, task_id: str) -> list[Principle]:
        """Deterministic extraction from heuristic rules."""
        principles = []
        for condition, text, category in HEURISTIC_RULES:
            if self._evaluate_condition(condition, outcome):
                principles.append(Principle(text=text, category=category))
        return principles

    def _extract_from_code(self, code_files: list[dict], task_id: str) -> list[Principle]:
        """Extract principles by analyzing code structure (Python only)."""
        principles = []
        for f in code_files:
            content = f.get("content", "")
            if not content or not f.get("path", "").endswith(".py"):
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

            # Check type hint usage
            typed = sum(1 for fn in functions if fn.returns is not None)
            if functions and typed / len(functions) >= 0.8:
                principles.append(Principle(
                    text="High type hint coverage correlates with fewer reflexion rounds",
                    category="readability",
                ))

            # Check function size
            long_fns = sum(
                1 for fn in functions
                if hasattr(fn, "end_lineno") and fn.end_lineno
                and (fn.end_lineno - fn.lineno) > 50
            )
            if long_fns > 0:
                principles.append(Principle(
                    text="Functions over 50 lines should be decomposed",
                    category="design",
                ))

        return principles

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """Safely evaluate a condition string."""
        for op in [">=", "<=", ">", "<", "=="]:
            if op in condition:
                parts = condition.split(op, 1)
                if len(parts) != 2:
                    return False
                var = parts[0].strip()
                try:
                    val = float(context.get(var, 0))
                    threshold = float(parts[1].strip())
                except (ValueError, TypeError):
                    return False
                if op == ">=": return val >= threshold
                if op == "<=": return val <= threshold
                if op == ">": return val > threshold
                if op == "<": return val < threshold
                if op == "==": return val == threshold
        return False

    def _find_match(self, candidate: Principle, existing: list[Principle]) -> Principle | None:
        """Find an existing principle that matches the candidate (Jaccard similarity)."""
        candidate_words = set(candidate.text.lower().split())
        for p in existing:
            existing_words = set(p.text.lower().split())
            if not candidate_words or not existing_words:
                continue
            intersection = candidate_words & existing_words
            union = candidate_words | existing_words
            similarity = len(intersection) / len(union)
            if similarity > 0.6:
                return p
        return None

    def _initial_confidence(self, outcome: dict) -> float:
        """Calculate initial confidence based on outcome quality."""
        score = outcome.get("score", 0.5)
        return round(min(0.8, 0.3 + score * 0.3), 2)

    async def _reinforce(self, principle_id: str, task_id: str):
        """Reinforce an existing principle (increase confidence)."""
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute(
            "SELECT evidence_count, confidence, source_tasks FROM principles WHERE principle_id = ?",
            (principle_id,),
        ).fetchone()
        if row:
            evidence = row[0] + 1
            # Logarithmic growth: 0.3 + log(evidence) * 0.15
            confidence = min(0.95, 0.3 + math.log(evidence + 1) * 0.15)
            sources = json.loads(row[2] or "[]")
            if task_id not in sources:
                sources.append(task_id)
            conn.execute(
                "UPDATE principles SET evidence_count = ?, confidence = ?, source_tasks = ? WHERE principle_id = ?",
                (evidence, round(confidence, 3), json.dumps(sources), principle_id),
            )
            conn.commit()
        conn.close()

    async def _store_principle(self, p: Principle):
        """Store a new principle in SQLite."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "INSERT OR REPLACE INTO principles VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                p.principle_id,
                p.text,
                p.category,
                p.confidence,
                p.evidence_count,
                json.dumps(p.source_tasks),
                p.created_at,
            ),
        )
        conn.commit()
        conn.close()

    async def _update_causal_graph(self, outcome: dict, code_files: list[dict] | None):
        """Update causal edges based on outcome."""
        success = outcome.get("score", 0.5) >= 0.7
        outcome_label = "success" if success else "failure"

        # Detect which factors are present
        factors_present = self._detect_factors(outcome, code_files)

        conn = sqlite3.connect(str(self._db_path))
        for factor in factors_present:
            row = conn.execute(
                "SELECT weight, observations FROM causal_edges WHERE factor = ? AND outcome = ?",
                (factor, outcome_label),
            ).fetchone()

            if row:
                old_weight, obs = row
                new_obs = obs + 1
                # Running average
                new_weight = round(old_weight + (1.0 - old_weight) / new_obs, 4)
                conn.execute(
                    "UPDATE causal_edges SET weight = ?, observations = ? WHERE factor = ? AND outcome = ?",
                    (new_weight, new_obs, factor, outcome_label),
                )
            else:
                conn.execute(
                    "INSERT INTO causal_edges VALUES (?, ?, ?, ?)",
                    (factor, outcome_label, 0.5, 1),
                )
        conn.commit()
        conn.close()

    def _detect_factors(self, outcome: dict, code_files: list[dict] | None) -> list[str]:
        """Detect which causal factors are present in the outcome."""
        factors = []
        if outcome.get("test_pass_rate", 0) > 0.8:
            factors.append("test_first")
        if outcome.get("reflexion_rounds", 0) <= 1:
            factors.append("small_functions")
        if code_files:
            for f in code_files:
                content = f.get("content", "")
                if "-> " in content or ": str" in content or ": int" in content:
                    factors.append("type_hints")
                    break
        return factors

    def _row_to_principle(self, row: tuple) -> Principle:
        return Principle(
            principle_id=row[0],
            text=row[1],
            category=row[2],
            confidence=row[3],
            evidence_count=row[4],
            source_tasks=json.loads(row[5] or "[]"),
            created_at=row[6],
        )
