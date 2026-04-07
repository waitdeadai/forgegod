"""ForgeGod Memory — 4-tier cognitive memory system for autonomous coding agents.

Architecture (inspired by Mem0 + MemGPT/Letta + cognitive science):

Tier 1: EPISODIC — What happened? Per-task records with full context.
         Retained: 90 days. Consolidates into semantic memories.

Tier 2: SEMANTIC — What do I know? Extracted principles, patterns, facts.
         Retained: indefinitely. Confidence decays without reinforcement.

Tier 3: PROCEDURAL — How do I do things? Code patterns, fix recipes, templates.
         Retained: indefinitely. Ranked by success rate.

Tier 4: GRAPH — How are things connected? Entities + causal edges.
         Retained: indefinitely. Pruned by observation count.

Key innovations:
- Importance scoring: recency * frequency * impact (not just confidence)
- Exponential decay with reinforcement resets
- Automatic consolidation: merge similar memories, deduplicate
- Multi-signal retrieval: keyword match + recency + importance + category
- Entity extraction: files, functions, errors, patterns auto-indexed
- Project-scoped + global memories (cross-project learning)
- Memory health: staleness detection, contradiction resolution
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import math
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from forgegod.config import ForgeGodConfig
from forgegod.models import CausalEdge, Principle

logger = logging.getLogger("forgegod.memory")

# ── Constants ──

EPISODIC_RETENTION_DAYS = 90
DECAY_HALFLIFE_DAYS = 30  # Default; see DECAY_HALFLIFE_BY_CATEGORY for per-category
DECAY_HALFLIFE_BY_CATEGORY = {
    "architecture": 90,   # Long-lived design decisions
    "security": 60,       # Important but evolves with new threats
    "testing": 45,        # Testing patterns moderately durable
    "design": 45,         # Design principles moderately durable
    "process": 30,        # Process guidance changes with team
    "readability": 30,    # Code style conventions
    "debugging": 14,      # Debugging tips decay fast (context-specific)
    "strategy": 21,       # Strategy tips decay moderately
}
MIN_CONFIDENCE = 0.05  # Below this, memory is prunable
MAX_SEMANTIC_MEMORIES = 500  # Per project
MAX_PROCEDURAL_MEMORIES = 200
CONSOLIDATION_SIMILARITY_THRESHOLD = 0.80

# Heuristic extraction rules: (condition, principle_text, category)
HEURISTIC_RULES: list[tuple[str, str, str]] = [
    ("test_pass_rate >= 0.95", "Write tests before implementation to reduce reflexion rounds", "testing"),
    ("test_pass_rate < 0.5", "Complex logic requires more test coverage", "testing"),
    ("reflexion_rounds <= 1", "Type hints reduce ambiguity and cut reflexion rounds", "readability"),
    ("reflexion_rounds >= 3", "Break complex functions into smaller units to reduce debugging", "design"),
    ("file_count > 5", "Use dependency injection for services with external resources", "architecture"),
    ("review_score >= 0.85", "Single Responsibility: each function does one thing well", "design"),
    ("security_issues > 0", "Validate all inputs at service boundaries", "security"),
    ("lines_changed > 200", "Large changes need incremental commits for safer rollback", "process"),
    ("error_count == 0", "Guard clauses at function entry prevent deep nesting", "readability"),
    ("retry_count >= 2", "When stuck, change approach fundamentally rather than retrying", "strategy"),
]

CAUSAL_FACTORS = [
    "type_hints", "test_first", "small_functions", "error_handling",
    "input_validation", "dependency_injection", "guard_clauses",
    "docstrings", "async_patterns", "model_tier", "incremental_commits",
    "read_before_edit", "repo_map_first",
]

# ── Entity types for graph memory ──
ENTITY_PATTERNS = {
    "file": re.compile(r"[\w./\\-]+\.(py|js|ts|tsx|go|rs|java|rb|cpp|c|h|css|html|md|toml|yaml|yml|json)"),
    "function": re.compile(r"(?:def|func|function|fn)\s+(\w+)"),
    "class": re.compile(r"(?:class|struct|interface|type)\s+(\w+)"),
    "error": re.compile(r"(?:Error|Exception|Traceback|FAIL|error\[)[\w.:]+"),
    "package": re.compile(r"(?:import|from|require|use)\s+[\w.]+"),
}


class Memory:
    """4-tier cognitive memory system for autonomous coding agents.

    Usage:
        memory = Memory(config)

        # After completing a task
        await memory.record_episode(task_id, task_desc, outcome, code_files)

        # Before starting a task (inject into prompt)
        context = await memory.recall(query="Add auth endpoint", limit=10)

        # Periodic maintenance
        await memory.consolidate()
        await memory.decay()
    """

    def __init__(self, config: ForgeGodConfig):
        self.config = config
        self._db_path = config.project_dir / "memory.db"
        self._global_db_path = Path.home() / ".forgegod" / "memory.db"
        self._ensure_db(self._db_path)
        self._ensure_db(self._global_db_path)

    def _open_conn(self, path: Path | None = None) -> sqlite3.Connection:
        """Open a SQLite connection with performance PRAGMAs.

        WAL mode + tuned PRAGMAs give ~10x write throughput and allow
        concurrent readers during writes.
        """
        conn = sqlite3.connect(str(path or self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB page cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        conn.execute("PRAGMA busy_timeout=5000")  # 5s retry on lock
        return conn

    def _ensure_db(self, path: Path):
        """Initialize SQLite schema for all 4 memory tiers."""
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        # Enable WAL mode for concurrent read/write performance
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        # Tier 1: Episodic Memory
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                episode_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_description TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT '{}',
                files_touched TEXT DEFAULT '[]',
                tools_used TEXT DEFAULT '[]',
                success INTEGER DEFAULT 0,
                reflexion_rounds INTEGER DEFAULT 0,
                model_used TEXT DEFAULT '',
                cost_usd REAL DEFAULT 0.0,
                duration_s REAL DEFAULT 0.0,
                error_log TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                project TEXT DEFAULT ''
            )
        """)

        # Tier 2: Semantic Memory (evolved from old 'principles' table)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic (
                memory_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                category TEXT DEFAULT '',
                confidence REAL DEFAULT 0.3,
                importance REAL DEFAULT 0.5,
                evidence_count INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                source_episodes TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                last_recalled TEXT DEFAULT '',
                last_reinforced TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                project TEXT DEFAULT '',
                superseded_by TEXT DEFAULT NULL
            )
        """)

        # Tier 3: Procedural Memory (code patterns, fix recipes)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS procedural (
                pattern_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                pattern_type TEXT DEFAULT '',
                trigger TEXT DEFAULT '',
                action TEXT DEFAULT '',
                code_template TEXT DEFAULT '',
                language TEXT DEFAULT '',
                success_rate REAL DEFAULT 0.5,
                usage_count INTEGER DEFAULT 0,
                source_episodes TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                project TEXT DEFAULT ''
            )
        """)

        # Tier 4: Graph Memory — Entities
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                mention_count INTEGER DEFAULT 1,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(name, entity_type)
            )
        """)

        # Tier 4: Graph Memory — Causal Edges
        conn.execute("""
            CREATE TABLE IF NOT EXISTS causal_edges (
                factor TEXT NOT NULL,
                outcome TEXT NOT NULL,
                weight REAL DEFAULT 0.0,
                observations INTEGER DEFAULT 0,
                PRIMARY KEY (factor, outcome)
            )
        """)

        # Tier 4: Graph Memory — Entity Relations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                source_entity TEXT NOT NULL,
                target_entity TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                evidence_count INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                PRIMARY KEY (source_entity, target_entity, relation_type)
            )
        """)

        # Tier 5: Error-Solution Index (highest-value for coding agents)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_solutions (
                error_id TEXT PRIMARY KEY,
                error_pattern TEXT NOT NULL,
                error_context TEXT DEFAULT '',
                solution TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                occurrences INTEGER DEFAULT 1,
                project_specific INTEGER DEFAULT 0,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Metadata
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Indexes for fast retrieval
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_confidence ON semantic(confidence DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_importance ON semantic(importance DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_task ON episodes(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_procedural_type ON procedural(pattern_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_procedural_success ON procedural(success_rate DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_pattern ON error_solutions(error_pattern)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_context ON error_solutions(error_context)")

        # Tier 6: Research Cache (Recon pipeline)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                results TEXT NOT NULL,
                provider TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                expires_at TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_query ON research_cache(query)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_expires ON research_cache(expires_at)")

        # ── FTS5 Full-Text Search indexes (100x faster text retrieval) ──
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS semantic_fts USING fts5(
                memory_id, text, category,
                content=semantic, content_rowid=rowid
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS error_solutions_fts USING fts5(
                error_id, error_pattern, solution,
                content=error_solutions, content_rowid=rowid
            )
        """)

        # Sync triggers: keep FTS indexes in sync with base tables
        conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS semantic_fts_ai AFTER INSERT ON semantic BEGIN
                INSERT INTO semantic_fts(rowid, memory_id, text, category)
                VALUES (new.rowid, new.memory_id, new.text, new.category);
            END;
            CREATE TRIGGER IF NOT EXISTS semantic_fts_ad AFTER DELETE ON semantic BEGIN
                INSERT INTO semantic_fts(semantic_fts, rowid, memory_id, text, category)
                VALUES ('delete', old.rowid, old.memory_id, old.text, old.category);
            END;
            CREATE TRIGGER IF NOT EXISTS semantic_fts_au AFTER UPDATE ON semantic BEGIN
                INSERT INTO semantic_fts(semantic_fts, rowid, memory_id, text, category)
                VALUES ('delete', old.rowid, old.memory_id, old.text, old.category);
                INSERT INTO semantic_fts(rowid, memory_id, text, category)
                VALUES (new.rowid, new.memory_id, new.text, new.category);
            END;
            CREATE TRIGGER IF NOT EXISTS errors_fts_ai AFTER INSERT ON error_solutions BEGIN
                INSERT INTO error_solutions_fts(rowid, error_id, error_pattern, solution)
                VALUES (new.rowid, new.error_id, new.error_pattern, new.solution);
            END;
            CREATE TRIGGER IF NOT EXISTS errors_fts_ad AFTER DELETE ON error_solutions BEGIN
                INSERT INTO error_solutions_fts(error_solutions_fts, rowid, error_id, error_pattern, solution)
                VALUES ('delete', old.rowid, old.error_id, old.error_pattern, old.solution);
            END;
        """)

        # Rebuild FTS indexes from existing data (idempotent)
        try:
            conn.execute("INSERT INTO semantic_fts(semantic_fts) VALUES ('rebuild')")
            conn.execute("INSERT INTO error_solutions_fts(error_solutions_fts) VALUES ('rebuild')")
        except sqlite3.OperationalError:
            pass  # Tables may be empty

        conn.commit()

        # Add superseded_by column if missing (v0.2 migration)
        try:
            conn.execute("SELECT superseded_by FROM semantic LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute(
                    "ALTER TABLE semantic ADD COLUMN superseded_by TEXT DEFAULT NULL"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Migrate old 'principles' table if it exists
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "principles" in tables and "semantic" in tables:
            existing = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
            if existing == 0:
                conn.execute("""
                    INSERT OR IGNORE INTO semantic
                        (memory_id, text, category, confidence, evidence_count,
                         source_episodes, created_at)
                    SELECT principle_id, text, category, confidence, evidence_count,
                           source_tasks, created_at
                    FROM principles
                """)
                logger.info("Migrated principles → semantic memory")

        conn.commit()
        conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # TIER 1: EPISODIC MEMORY — What happened?
    # ═══════════════════════════════════════════════════════════════════

    async def record_episode(
        self,
        task_id: str,
        task_description: str,
        outcome: dict,
        code_files: list[dict] | None = None,
        tools_used: list[str] | None = None,
    ) -> str:
        """Record a complete task episode. This is the primary write path.

        After recording, automatically:
        1. Extracts semantic memories (principles)
        2. Extracts procedural memories (patterns)
        3. Updates graph memory (entities + edges)
        4. Runs mini-consolidation
        """
        now = datetime.now(timezone.utc).isoformat()
        episode_id = f"ep-{uuid.uuid4().hex[:12]}"

        conn = self._open_conn()
        conn.execute(
            """INSERT INTO episodes
               (episode_id, task_id, task_description, outcome, files_touched,
                tools_used, success, reflexion_rounds, model_used, cost_usd,
                duration_s, error_log, created_at, project)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                episode_id,
                task_id,
                task_description,
                json.dumps(outcome),
                json.dumps([
                    f.get("path", "") if isinstance(f, dict) else str(f)
                    for f in (code_files or [])
                ]),
                json.dumps(tools_used or []),
                1 if outcome.get("score", 0) >= 0.7 else 0,
                outcome.get("reflexion_rounds", 0),
                outcome.get("model", ""),
                outcome.get("cost_usd", 0.0),
                outcome.get("duration_s", 0.0),
                outcome.get("error", ""),
                now,
                self._project_name(),
            ),
        )
        # Track episodes since last consolidation (AutoDream trigger)
        row = conn.execute(
            "SELECT value FROM memory_meta "
            "WHERE key = 'episodes_since_consolidation'"
        ).fetchone()
        count = int(row[0]) + 1 if row else 1
        conn.execute(
            "INSERT OR REPLACE INTO memory_meta (key, value, updated_at) "
            "VALUES ('episodes_since_consolidation', ?, ?)",
            (str(count), now),
        )

        conn.commit()
        conn.close()

        # Auto-extract into higher tiers
        await self._extract_semantic(episode_id, task_description, outcome, code_files)
        await self._extract_procedural(episode_id, task_description, outcome, code_files)
        await self._update_graph(task_description, outcome, code_files)

        logger.info(f"Memory: recorded episode {episode_id} for task {task_id}")
        return episode_id

    async def get_recent_episodes(self, limit: int = 10) -> list[dict]:
        """Get most recent episodes."""
        conn = self._open_conn()
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        cols = [
            "episode_id", "task_id", "task_description", "outcome",
            "files_touched", "tools_used", "success", "reflexion_rounds",
            "model_used", "cost_usd", "duration_s", "error_log",
            "created_at", "project",
        ]
        return [dict(zip(cols, r)) for r in rows]

    # ═══════════════════════════════════════════════════════════════════
    # TIER 2: SEMANTIC MEMORY — What do I know?
    # ═══════════════════════════════════════════════════════════════════

    async def get_principles(
        self, category: str = "", min_confidence: float = 0.0
    ) -> list[Principle]:
        """Get semantic memories as Principle objects (backwards compatible)."""
        conn = self._open_conn()
        if category:
            rows = conn.execute(
                """SELECT memory_id, text, category, confidence, evidence_count,
                          source_episodes, created_at
                   FROM semantic WHERE category = ? AND confidence >= ?
                     AND superseded_by IS NULL
                   ORDER BY importance DESC, confidence DESC""",
                (category, min_confidence),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT memory_id, text, category, confidence, evidence_count,
                          source_episodes, created_at
                   FROM semantic WHERE confidence >= ?
                     AND superseded_by IS NULL
                   ORDER BY importance DESC, confidence DESC""",
                (min_confidence,),
            ).fetchall()
        conn.close()
        return [
            Principle(
                principle_id=r[0], text=r[1], category=r[2],
                confidence=r[3], evidence_count=r[4],
                source_tasks=json.loads(r[5] or "[]"), created_at=r[6],
            )
            for r in rows
        ]

    async def get_learnings_text(self, limit: int = 10) -> str:
        """Get top memories formatted for prompt injection (Memory Spine)."""
        conn = self._open_conn()
        rows = conn.execute(
            """SELECT text, category, confidence, evidence_count
               FROM semantic WHERE confidence >= 0.3
                 AND superseded_by IS NULL
               ORDER BY importance DESC, confidence DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()

        if not rows:
            return ""

        lines = ["## Learned Principles (from past outcomes)"]
        for text, category, conf, evidence in rows:
            strength = "strong" if conf >= 0.7 else "moderate" if conf >= 0.4 else "tentative"
            lines.append(f"- [{category}] {text} ({strength}, {evidence} observations)")
        return "\n".join(lines)

    async def add_semantic(
        self,
        text: str,
        category: str = "",
        confidence: float = 0.5,
        source_episode: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Add or reinforce a semantic memory."""
        existing = await self._find_similar_semantic(text)
        if existing:
            await self._reinforce_semantic(existing, source_episode)
            return existing

        memory_id = f"sm-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        importance = self._calculate_importance(confidence, 1, now)

        conn = self._open_conn()
        conn.execute(
            """INSERT INTO semantic
               (memory_id, text, category, confidence, importance, evidence_count,
                source_episodes, tags, last_reinforced, created_at, project)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory_id, text, category, confidence, importance, 1,
                json.dumps([source_episode] if source_episode else []),
                json.dumps(tags or []),
                now, now, self._project_name(),
            ),
        )
        conn.commit()
        conn.close()
        return memory_id

    # ═══════════════════════════════════════════════════════════════════
    # TIER 3: PROCEDURAL MEMORY — How do I do things?
    # ═══════════════════════════════════════════════════════════════════

    async def add_procedure(
        self,
        name: str,
        description: str = "",
        pattern_type: str = "fix",
        trigger: str = "",
        action: str = "",
        code_template: str = "",
        language: str = "",
        source_episode: str = "",
    ) -> str:
        """Add a procedural memory (code pattern, fix recipe, template)."""
        pattern_id = f"proc-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        conn = self._open_conn()
        conn.execute(
            """INSERT INTO procedural
               (pattern_id, name, description, pattern_type, trigger, action,
                code_template, language, source_episodes, tags, created_at, project)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern_id, name, description, pattern_type, trigger, action,
                code_template, language,
                json.dumps([source_episode] if source_episode else []),
                "[]", now, self._project_name(),
            ),
        )
        conn.commit()
        conn.close()
        return pattern_id

    async def get_procedures(
        self, pattern_type: str = "", language: str = "", limit: int = 20,
    ) -> list[dict]:
        """Get procedural memories, optionally filtered."""
        conn = self._open_conn()
        query = "SELECT * FROM procedural WHERE 1=1"
        params: list = []
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        if language:
            query += " AND language = ?"
            params.append(language)
        query += " ORDER BY success_rate DESC, usage_count DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        cols = [
            "pattern_id", "name", "description", "pattern_type", "trigger",
            "action", "code_template", "language", "success_rate", "usage_count",
            "source_episodes", "tags", "created_at", "project",
        ]
        return [dict(zip(cols, r)) for r in rows]

    async def record_procedure_outcome(self, pattern_id: str, success: bool):
        """Record whether a procedure worked when applied."""
        conn = self._open_conn()
        row = conn.execute(
            "SELECT success_rate, usage_count FROM procedural WHERE pattern_id = ?",
            (pattern_id,),
        ).fetchone()
        if row:
            old_rate, count = row
            new_count = count + 1
            # Running average
            new_rate = old_rate + ((1.0 if success else 0.0) - old_rate) / new_count
            conn.execute(
                "UPDATE procedural SET success_rate = ?, usage_count = ? WHERE pattern_id = ?",
                (round(new_rate, 4), new_count, pattern_id),
            )
            conn.commit()
        conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # TIER 4: GRAPH MEMORY — How are things connected?
    # ═══════════════════════════════════════════════════════════════════

    async def get_causal_edges(self) -> list[CausalEdge]:
        """Get all edges in the causal graph."""
        conn = self._open_conn()
        rows = conn.execute(
            "SELECT factor, outcome, weight, observations FROM causal_edges ORDER BY weight DESC"
        ).fetchall()
        conn.close()
        return [
            CausalEdge(factor=r[0], outcome=r[1], weight=r[2], observations=r[3])
            for r in rows
        ]

    async def add_causal_edge(
        self, factor: str, outcome: str, weight: float = 0.5,
    ) -> None:
        """Add or update a causal edge in the graph."""
        conn = self._open_conn()
        existing = conn.execute(
            "SELECT weight, observations FROM causal_edges "
            "WHERE factor = ? AND outcome = ?",
            (factor, outcome),
        ).fetchone()
        if existing:
            new_weight = (existing[0] * existing[1] + weight) / (existing[1] + 1)
            conn.execute(
                "UPDATE causal_edges SET weight = ?, observations = ? "
                "WHERE factor = ? AND outcome = ?",
                (new_weight, existing[1] + 1, factor, outcome),
            )
        else:
            conn.execute(
                "INSERT INTO causal_edges VALUES (?, ?, ?, ?)",
                (factor, outcome, weight, 1),
            )
        conn.commit()
        conn.close()

    async def get_success_factors(self) -> list[str]:
        """Get factors most correlated with success."""
        edges = await self.get_causal_edges()
        success_edges = [e for e in edges if e.outcome == "success" and e.observations >= 3]
        success_edges.sort(key=lambda e: e.weight, reverse=True)
        return [e.factor for e in success_edges[:5]]

    async def get_related_entities(self, entity_name: str, limit: int = 10) -> list[dict]:
        """Get entities related to a given entity."""
        conn = self._open_conn()
        rows = conn.execute(
            """SELECT target_entity, relation_type, weight, evidence_count
               FROM relations WHERE source_entity = ?
               UNION ALL
               SELECT source_entity, relation_type, weight, evidence_count
               FROM relations WHERE target_entity = ?
               ORDER BY weight DESC LIMIT ?""",
            (entity_name, entity_name, limit),
        ).fetchall()
        conn.close()
        return [
            {"entity": r[0], "relation": r[1], "weight": r[2], "evidence": r[3]}
            for r in rows
        ]

    # ═══════════════════════════════════════════════════════════════════
    # TIER 5: ERROR-SOLUTION INDEX — What fixes what?
    # ═══════════════════════════════════════════════════════════════════

    async def record_error_solution(
        self,
        error_pattern: str,
        solution: str,
        error_context: str = "",
        project_specific: bool = False,
    ) -> str:
        """Record an error-solution pair. Auto-deduplicates."""
        now = datetime.now(timezone.utc).isoformat()

        # Check for existing match
        conn = self._open_conn()
        existing = conn.execute(
            "SELECT error_id, occurrences FROM error_solutions WHERE error_pattern = ?",
            (error_pattern,),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE error_solutions
                   SET occurrences = occurrences + 1, last_seen = ?, solution = ?
                   WHERE error_id = ?""",
                (now, solution, existing[0]),
            )
            conn.commit()
            conn.close()
            return existing[0]

        error_id = f"err-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO error_solutions
               (error_id, error_pattern, error_context, solution, confidence,
                occurrences, project_specific, last_seen, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (error_id, error_pattern, error_context, solution, 0.5,
             1, 1 if project_specific else 0, now, now),
        )
        conn.commit()
        conn.close()
        return error_id

    async def lookup_error(self, error_text: str, limit: int = 3) -> list[dict]:
        """Look up solutions for an error. Uses FTS5 + fuzzy fallback."""
        conn = self._open_conn()

        # Try FTS5 first for fast lookup
        fts_ids = set()
        fts_terms = " OR ".join(
            w for w in error_text.lower().split() if len(w) > 2
        )
        if fts_terms:
            try:
                fts_rows = conn.execute(
                    """SELECT es.error_id FROM error_solutions_fts
                       JOIN error_solutions es ON es.rowid = error_solutions_fts.rowid
                       WHERE error_solutions_fts MATCH ?
                       LIMIT 20""",
                    (fts_terms,),
                ).fetchall()
                fts_ids = {r[0] for r in fts_rows}
            except sqlite3.OperationalError:
                pass  # FTS5 may not exist

        rows = conn.execute(
            "SELECT error_id, error_pattern, error_context, solution, confidence, occurrences FROM error_solutions"
        ).fetchall()
        conn.close()

        if not rows:
            return []

        error_lower = error_text.lower()
        matches: list[tuple[float, dict]] = []
        for r in rows:
            pattern = r[1].lower()
            # Simple substring + word overlap scoring
            if pattern in error_lower:
                score = 1.0
            else:
                pattern_words = set(pattern.split())
                error_words = set(error_lower.split())
                overlap = len(pattern_words & error_words)
                score = overlap / max(len(pattern_words), 1)

            # FTS5 boost: matched entries get a score floor
            if r[0] in fts_ids:
                score = max(score, 0.3)

            if score > 0.2:
                matches.append((score * r[4], {  # score * confidence
                    "error_id": r[0], "error_pattern": r[1],
                    "error_context": r[2], "solution": r[3],
                    "confidence": r[4], "occurrences": r[5],
                }))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:limit]]

    # ═══════════════════════════════════════════════════════════════════
    # RECALL — Multi-signal retrieval
    # ═══════════════════════════════════════════════════════════════════

    async def recall(
        self,
        query: str = "",
        category: str = "",
        limit: int = 15,
        include_procedural: bool = True,
        include_episodes: bool = False,
        min_confidence: float = 0.2,
    ) -> str:
        """Smart recall — multi-signal retrieval for prompt injection.

        Retrieval signals (scored and combined):
        1. Keyword overlap with query (Jaccard similarity)
        2. Recency (recently reinforced memories score higher)
        3. Importance (compound of confidence, evidence, recency)
        4. Category match (if category specified)

        Returns formatted text ready for system prompt injection.
        """
        sections: list[str] = []

        # 1. Semantic memories (principles)
        semantic = await self._recall_semantic(
            query, category, limit, min_confidence
        )
        if semantic:
            lines = ["## Learned Principles"]
            for mem in semantic:
                strength = (
                    "strong" if mem["confidence"] >= 0.7
                    else "moderate" if mem["confidence"] >= 0.4
                    else "tentative"
                )
                lines.append(
                    f"- [{mem['category']}] {mem['text']} "
                    f"({strength}, {mem['evidence_count']}x)"
                )
            sections.append("\n".join(lines))

        # 2. Procedural memories (if relevant)
        if include_procedural and query:
            procedures = await self._recall_procedural(query, limit=5)
            if procedures:
                lines = ["## Known Patterns"]
                for proc in procedures:
                    rate = f"{proc['success_rate']:.0%}" if proc['usage_count'] > 0 else "new"
                    lines.append(
                        f"- **{proc['name']}** ({proc['pattern_type']}, {rate} success): "
                        f"{proc['description'][:100]}"
                    )
                    if proc.get("trigger"):
                        lines.append(f"  Trigger: {proc['trigger']}")
                sections.append("\n".join(lines))

        # 3. Error-solution pairs (highest priority in debugging)
        if query:
            error_matches = await self.lookup_error(query, limit=3)
            if error_matches:
                lines = ["## Known Error Solutions"]
                for em in error_matches:
                    lines.append(
                        f"- **{em['error_pattern'][:60]}** → {em['solution'][:100]} "
                        f"({em['occurrences']}x seen)"
                    )
                sections.append("\n".join(lines))

        # 4. Success factors from causal graph
        factors = await self.get_success_factors()
        if factors:
            sections.append(
                "## Success Factors (from causal analysis)\n"
                + ", ".join(factors)
            )

        # 5. Recent episodes (optional, for context)
        if include_episodes:
            episodes = await self.get_recent_episodes(limit=3)
            if episodes:
                lines = ["## Recent Tasks"]
                for ep in episodes:
                    status = "pass" if ep["success"] else "fail"
                    lines.append(
                        f"- [{status}] {ep['task_description'][:80]} "
                        f"(reflexion: {ep['reflexion_rounds']})"
                    )
                sections.append("\n".join(lines))

        if not sections:
            return ""

        # Mark recalled memories (for recency tracking)
        await self._mark_recalled(semantic)

        return "\n\n".join(sections)

    async def _recall_semantic(
        self, query: str, category: str, limit: int, min_confidence: float
    ) -> list[dict]:
        """Retrieve semantic memories ranked by multi-signal score.

        Uses FTS5 for fast candidate retrieval when a query is provided,
        then re-ranks with importance + recency signals (hybrid retrieval).
        Falls back to full scan when FTS5 is unavailable or query is empty.
        """
        conn = self._open_conn()

        # Build FTS5 query: convert words to OR-joined terms
        fts5_candidates = set()
        if query:
            # Try FTS5 first for fast candidate retrieval
            fts_terms = " OR ".join(
                w for w in query.lower().split() if len(w) > 2
            )
            if fts_terms:
                try:
                    fts_rows = conn.execute(
                        """SELECT s.memory_id FROM semantic_fts
                           JOIN semantic s ON s.rowid = semantic_fts.rowid
                           WHERE semantic_fts MATCH ?
                           LIMIT 50""",
                        (fts_terms,),
                    ).fetchall()
                    fts5_candidates = {r[0] for r in fts_rows}
                except sqlite3.OperationalError:
                    pass  # FTS5 table may not exist yet

        # Fetch candidate rows (FTS5 narrowed or full scan)
        params: list = [min_confidence]
        where = "WHERE confidence >= ? AND superseded_by IS NULL"
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""SELECT memory_id, text, category, confidence, importance,
                       evidence_count, last_reinforced, created_at, tags
                FROM semantic {where}""",
            params,
        ).fetchall()
        conn.close()

        if not rows:
            return []

        # Score each memory
        query_words = set(query.lower().split()) if query else set()
        scored: list[tuple[float, dict]] = []

        for r in rows:
            mem = {
                "memory_id": r[0], "text": r[1], "category": r[2],
                "confidence": r[3], "importance": r[4],
                "evidence_count": r[5], "last_reinforced": r[6],
                "created_at": r[7], "tags": json.loads(r[8] or "[]"),
            }

            # Signal 1: Keyword relevance (0-1)
            if query_words:
                mem_words = set(mem["text"].lower().split())
                tag_words = set(w.lower() for t in mem["tags"] for w in t.split())
                all_words = mem_words | tag_words
                if all_words:
                    relevance = len(query_words & all_words) / max(len(query_words), 1)
                else:
                    relevance = 0.0
                # FTS5 boost: memories found by FTS5 get a relevance floor
                if fts5_candidates and mem["memory_id"] in fts5_candidates:
                    relevance = max(relevance, 0.3)
            else:
                relevance = 0.5  # No query = all equally relevant

            # Signal 2: Recency (0-1, exponential decay)
            recency = self._recency_score(mem.get("last_reinforced") or mem["created_at"])

            # Signal 3: Importance (already computed, 0-1)
            importance = mem["importance"]

            # Combine signals (weighted)
            score = (relevance * 0.4) + (importance * 0.35) + (recency * 0.25)
            scored.append((score, mem))

        # Sort by score, return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:limit]]

    async def _recall_procedural(self, query: str, limit: int = 5) -> list[dict]:
        """Retrieve procedural memories relevant to query."""
        conn = self._open_conn()
        rows = conn.execute(
            """SELECT pattern_id, name, description, pattern_type, trigger,
                      action, code_template, language, success_rate, usage_count
               FROM procedural ORDER BY success_rate DESC, usage_count DESC""",
        ).fetchall()
        conn.close()

        if not rows or not query:
            return []

        query_words = set(query.lower().split())
        scored: list[tuple[float, dict]] = []
        cols = [
            "pattern_id", "name", "description", "pattern_type", "trigger",
            "action", "code_template", "language", "success_rate", "usage_count",
        ]

        for r in rows:
            proc = dict(zip(cols, r))
            # Match against name, description, trigger
            proc_text = f"{proc['name']} {proc['description']} {proc['trigger']}".lower()
            proc_words = set(proc_text.split())
            relevance = len(query_words & proc_words) / max(len(query_words), 1)
            if relevance > 0.1:
                scored.append((relevance * proc["success_rate"], proc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [proc for _, proc in scored[:limit]]

    async def _mark_recalled(self, memories: list[dict]):
        """Update last_recalled timestamp for retrieved memories."""
        if not memories:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn = self._open_conn()
        for mem in memories:
            conn.execute(
                "UPDATE semantic SET last_recalled = ? WHERE memory_id = ?",
                (now, mem["memory_id"]),
            )
        conn.commit()
        conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # EXTRACTION — Auto-derive memories from episodes
    # ═══════════════════════════════════════════════════════════════════

    async def _extract_semantic(
        self, episode_id: str, task_desc: str, outcome: dict,
        code_files: list[dict] | None,
    ):
        """Extract semantic memories from a completed episode."""
        extracted_count = 0

        # 1. Heuristic extraction
        for condition, text, category in HEURISTIC_RULES:
            if self._evaluate_condition(condition, outcome):
                await self.add_semantic(
                    text=text, category=category,
                    confidence=self._initial_confidence(outcome),
                    source_episode=episode_id,
                )
                extracted_count += 1

        # 2. Code pattern extraction (Python AST analysis)
        if code_files:
            for f in code_files:
                if isinstance(f, str):
                    continue  # Path-only entries have no content to analyze
                content = f.get("content", "")
                if not content or not f.get("path", "").endswith(".py"):
                    continue
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue

                functions = [
                    n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]

                # Type hint coverage
                if functions:
                    typed = sum(1 for fn in functions if fn.returns is not None)
                    if typed / len(functions) >= 0.8:
                        await self.add_semantic(
                            text="High type hint coverage correlates with fewer reflexion rounds",
                            category="readability",
                            source_episode=episode_id,
                        )
                        extracted_count += 1

                # Long functions
                long_fns = sum(
                    1 for fn in functions
                    if hasattr(fn, "end_lineno") and fn.end_lineno
                    and (fn.end_lineno - fn.lineno) > 50
                )
                if long_fns > 0:
                    await self.add_semantic(
                        text="Functions over 50 lines should be decomposed",
                        category="design",
                        source_episode=episode_id,
                    )
                    extracted_count += 1

        # 3. Error-driven extraction
        error = outcome.get("error", "")
        if error and not outcome.get("score", 0) >= 0.7:
            # Extract the error pattern as a negative memory
            error_summary = error[:200].strip()
            await self.add_semantic(
                text=f"Watch out for: {error_summary}",
                category="debugging",
                confidence=0.4,
                source_episode=episode_id,
                tags=["error", "negative"],
            )
            extracted_count += 1

        logger.debug(f"Memory: extracted {extracted_count} semantic memories from {episode_id}")

    async def _extract_procedural(
        self, episode_id: str, task_desc: str, outcome: dict,
        code_files: list[dict] | None,
    ):
        """Extract procedural memories (code patterns) from successful episodes."""
        if not outcome.get("score", 0) >= 0.7 or not code_files:
            return

        for f in code_files:
            if isinstance(f, str):
                continue  # Path-only entries have no content to analyze
            content = f.get("content", "")
            path = f.get("path", "")
            if not content:
                continue

            # Detect language
            lang = ""
            if path.endswith(".py"):
                lang = "python"
            elif path.endswith((".js", ".ts", ".tsx")):
                lang = "javascript"
            elif path.endswith(".go"):
                lang = "go"
            elif path.endswith(".rs"):
                lang = "rust"

            # Extract patterns from successful code
            if lang == "python" and len(content) < 5000:
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        # Detect decorator patterns
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.decorator_list:
                                decos = [
                                    ast.get_source_segment(content, d)
                                    for d in node.decorator_list
                                    if ast.get_source_segment(content, d)
                                ]
                                if decos:
                                    await self.add_procedure(
                                        name=f"Pattern: {node.name} with decorators",
                                        description=f"Function with {', '.join(str(d)[:30] for d in decos)}",
                                        pattern_type="pattern",
                                        language=lang,
                                        source_episode=episode_id,
                                    )
                except (SyntaxError, TypeError):
                    pass

    async def _update_graph(
        self, task_desc: str, outcome: dict, code_files: list[dict] | None,
    ):
        """Update graph memory: extract entities, add relations, update causal edges."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._open_conn()

        # 1. Extract entities from task description
        all_text = task_desc
        if code_files:
            all_text += " " + " ".join(
                f.get("path", "") if isinstance(f, dict) else str(f)
                for f in code_files
            )

        entities_found: list[tuple[str, str]] = []  # (name, type)
        for entity_type, pattern in ENTITY_PATTERNS.items():
            matches = pattern.findall(all_text)
            for match in matches[:10]:  # Cap per type
                name = match if isinstance(match, str) else match
                if len(name) > 2:  # Skip tiny matches
                    entities_found.append((name, entity_type))

        # Upsert entities
        for name, etype in entities_found:
            conn.execute(
                """INSERT INTO entities (entity_id, name, entity_type, last_seen, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name, entity_type)
                   DO UPDATE SET mention_count = mention_count + 1, last_seen = ?""",
                (f"ent-{hashlib.md5(f'{name}:{etype}'.encode()).hexdigest()[:10]}",
                 name, etype, now, now, now),
            )

        # 2. Update causal edges
        success = outcome.get("score", 0.5) >= 0.7
        outcome_label = "success" if success else "failure"
        factors_present = self._detect_factors(outcome, code_files)

        for factor in factors_present:
            row = conn.execute(
                "SELECT weight, observations FROM causal_edges WHERE factor = ? AND outcome = ?",
                (factor, outcome_label),
            ).fetchone()

            if row:
                old_weight, obs = row
                new_obs = obs + 1
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

    # ═══════════════════════════════════════════════════════════════════
    # MAINTENANCE — Consolidation, decay, health
    # ═══════════════════════════════════════════════════════════════════

    async def consolidate(self):
        """Consolidate similar memories, prune weak ones.

        This should run periodically (e.g., after every 10 episodes or daily).
        1. Merge similar semantic memories (Jaccard > threshold)
        2. Prune memories below MIN_CONFIDENCE
        3. Prune old episodes beyond retention period
        4. Cap total memories at limits
        """
        conn = self._open_conn()
        now = datetime.now(timezone.utc)

        # 1. Merge similar semantic memories (category-bucketed for O(n*k) instead of O(n^2))
        rows = conn.execute(
            "SELECT memory_id, text, confidence, evidence_count, category FROM semantic"
        ).fetchall()

        # Bucket by category — only compare within same category
        from collections import defaultdict
        buckets: dict[str, list] = defaultdict(list)
        for r in rows:
            buckets[r[4] or ""].append(r)

        # Pre-compute word sets once per memory (avoid recomputation in inner loop)
        word_cache: dict[str, set] = {}
        for r in rows:
            word_cache[r[0]] = set(r[1].lower().split())

        merged = set()
        for _cat, bucket in buckets.items():
            for i, (id_a, text_a, conf_a, ev_a, _) in enumerate(bucket):
                if id_a in merged:
                    continue
                words_a = word_cache[id_a]
                if not words_a:
                    continue
                for j in range(i + 1, len(bucket)):
                    id_b, text_b, conf_b, ev_b, _ = bucket[j]
                    if id_b in merged:
                        continue
                    words_b = word_cache[id_b]
                    if not words_b:
                        continue
                    union_len = len(words_a | words_b)
                    if union_len == 0:
                        continue
                    similarity = len(words_a & words_b) / union_len
                    if similarity > CONSOLIDATION_SIMILARITY_THRESHOLD:
                        # Merge into the one with more evidence
                        if ev_b > ev_a:
                            merged.add(id_a)
                            conn.execute(
                                "UPDATE semantic SET evidence_count = evidence_count + ? WHERE memory_id = ?",
                                (ev_a, id_b),
                            )
                        else:
                            merged.add(id_b)
                            conn.execute(
                                "UPDATE semantic SET evidence_count = evidence_count + ? WHERE memory_id = ?",
                                (ev_b, id_a),
                            )

        if merged:
            placeholders = ",".join("?" * len(merged))
            conn.execute(
                f"DELETE FROM semantic WHERE memory_id IN ({placeholders})",
                list(merged),
            )
            logger.info(f"Memory consolidation: merged {len(merged)} similar memories")

        # 2. Prune weak memories
        pruned = conn.execute(
            "DELETE FROM semantic WHERE confidence < ?", (MIN_CONFIDENCE,)
        ).rowcount
        if pruned:
            logger.info(f"Memory consolidation: pruned {pruned} weak memories")

        # 3. Prune old episodes
        import datetime as dt
        cutoff = (now - dt.timedelta(days=EPISODIC_RETENTION_DAYS)).isoformat()
        old_eps = conn.execute(
            "DELETE FROM episodes WHERE created_at < ?", (cutoff,)
        ).rowcount
        if old_eps:
            logger.info(f"Memory consolidation: pruned {old_eps} old episodes")

        # 4. Cap semantic memories
        count = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
        if count > MAX_SEMANTIC_MEMORIES:
            # Delete lowest importance
            excess = count - MAX_SEMANTIC_MEMORIES
            conn.execute(
                """DELETE FROM semantic WHERE memory_id IN (
                       SELECT memory_id FROM semantic
                       ORDER BY importance ASC, confidence ASC
                       LIMIT ?
                   )""",
                (excess,),
            )
            logger.info(f"Memory consolidation: capped semantic memories, removed {excess}")

        conn.commit()
        conn.close()

    async def decay(self):
        """Apply confidence decay to all semantic memories.

        Memories that haven't been reinforced lose confidence over time.
        Decay function: confidence * 2^(-days_since_reinforcement / halflife)
        """
        conn = self._open_conn()
        now = datetime.now(timezone.utc)

        rows = conn.execute(
            "SELECT memory_id, confidence, last_reinforced, evidence_count, category FROM semantic"
        ).fetchall()

        updated = 0
        for memory_id, confidence, last_reinforced, evidence, category in rows:
            if not last_reinforced:
                continue
            try:
                last_dt = datetime.fromisoformat(last_reinforced.replace("Z", "+00:00"))
                days_since = (now - last_dt).total_seconds() / 86400
            except (ValueError, TypeError):
                continue

            if days_since < 1:
                continue

            # Category-specific base halflife (architecture 90d, debugging 14d, etc.)
            base_halflife = DECAY_HALFLIFE_BY_CATEGORY.get(
                category or "", DECAY_HALFLIFE_DAYS
            )
            # Exponential decay, moderated by evidence count
            # More evidence = slower decay (better established memories last longer)
            effective_halflife = base_halflife * (1 + math.log(evidence + 1) * 0.3)
            decayed = confidence * (2 ** (-days_since / effective_halflife))
            decayed = round(max(MIN_CONFIDENCE, decayed), 4)

            if abs(decayed - confidence) > 0.001:
                # Recalculate importance with decayed confidence
                importance = self._calculate_importance(decayed, evidence, last_reinforced)
                conn.execute(
                    "UPDATE semantic SET confidence = ?, importance = ? WHERE memory_id = ?",
                    (decayed, importance, memory_id),
                )
                updated += 1

        if updated:
            conn.commit()
            logger.info(f"Memory decay: updated {updated} memories")
        conn.close()

    async def health(self) -> dict:
        """Get memory system health report."""
        conn = self._open_conn()

        episodes = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        semantic = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
        procedural = conn.execute("SELECT COUNT(*) FROM procedural").fetchone()[0]
        entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        edges = conn.execute("SELECT COUNT(*) FROM causal_edges").fetchone()[0]
        relations = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

        error_solutions = conn.execute("SELECT COUNT(*) FROM error_solutions").fetchone()[0]

        avg_confidence = conn.execute(
            "SELECT AVG(confidence) FROM semantic"
        ).fetchone()[0] or 0

        strong = conn.execute(
            "SELECT COUNT(*) FROM semantic WHERE confidence >= 0.7"
        ).fetchone()[0]
        weak = conn.execute(
            "SELECT COUNT(*) FROM semantic WHERE confidence < 0.3"
        ).fetchone()[0]

        conn.close()

        total = semantic + procedural + error_solutions
        return {
            "episodes": episodes,
            "semantic_memories": semantic,
            "procedural_memories": procedural,
            "error_solutions": error_solutions,
            "entities": entities,
            "causal_edges": edges,
            "entity_relations": relations,
            "avg_confidence": round(avg_confidence, 3),
            "strong_memories": strong,
            "weak_memories": weak,
            "health_score": min(1.0, total / 50) if total > 0 else 0,
        }

    # ═══════════════════════════════════════════════════════════════════
    # SMART RECALL — Adaptive depth based on task complexity
    # ═══════════════════════════════════════════════════════════════════

    # Complexity keywords for adaptive retrieval
    _COMPLEX_KEYWORDS = {
        "refactor", "across", "integrate", "migrate", "redesign",
        "architecture", "rewrite", "overhaul", "multi-file",
        "system", "pipeline", "framework", "infrastructure",
    }
    _SIMPLE_KEYWORDS = {
        "fix", "typo", "rename", "update", "bump", "remove",
        "delete", "add", "change", "set", "tweak", "patch",
    }

    async def smart_recall(
        self, task: str, complexity_hint: str = "auto"
    ) -> str:
        """Adaptive memory recall — right amount of context per task.

        Research (March 2026): Memory is pure overhead on simple tasks
        (< 200 lines), but provides 22-32% efficiency gains on complex ones.

        Args:
            task: Task description to recall context for.
            complexity_hint: "simple", "medium", "complex", or "auto" (detect).

        Returns:
            Formatted text ready for prompt injection.
        """
        if complexity_hint == "auto":
            complexity_hint = self._detect_complexity(task)

        if complexity_hint == "simple":
            return await self.recall(
                query=task, limit=3,
                include_procedural=False, include_episodes=False,
            )
        elif complexity_hint == "complex":
            return await self.recall(
                query=task, limit=15,
                include_procedural=True, include_episodes=True,
            )
        else:  # medium
            return await self.recall(
                query=task, limit=8,
                include_procedural=True, include_episodes=False,
            )

    def _detect_complexity(self, task: str) -> str:
        """Estimate task complexity from description keywords."""
        words = set(task.lower().split())
        complex_hits = len(words & self._COMPLEX_KEYWORDS)
        simple_hits = len(words & self._SIMPLE_KEYWORDS)

        if complex_hits >= 2 or len(task) > 200:
            return "complex"
        if simple_hits >= 1 and complex_hits == 0 and len(task) < 80:
            return "simple"
        return "medium"

    # ═══════════════════════════════════════════════════════════════════
    # AUTODREAM — Automatic consolidation triggers
    # ═══════════════════════════════════════════════════════════════════

    async def maybe_consolidate(self):
        """Check triggers and run consolidation if needed.

        Dual trigger (inspired by Claude Code's AutoDream):
        - Trigger A: 10+ episodes since last consolidation
        - Trigger B: 24+ hours since last consolidation
        Either trigger fires consolidation + decay.
        """
        conn = self._open_conn()

        # Read metadata
        last_ts = None
        episodes_since = 0
        row = conn.execute(
            "SELECT value FROM memory_meta WHERE key = 'last_consolidation_ts'"
        ).fetchone()
        if row:
            try:
                last_ts = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        row = conn.execute(
            "SELECT value FROM memory_meta WHERE key = 'episodes_since_consolidation'"
        ).fetchone()
        if row:
            try:
                episodes_since = int(row[0])
            except (ValueError, TypeError):
                pass

        conn.close()

        now = datetime.now(timezone.utc)
        should_consolidate = False

        # Trigger A: episode count
        if episodes_since >= 10:
            should_consolidate = True
            logger.info(f"AutoDream: {episodes_since} episodes trigger")

        # Trigger B: time-based (24h)
        if last_ts and (now - last_ts).total_seconds() > 86400:
            should_consolidate = True
            logger.info("AutoDream: 24h time trigger")

        # First ever consolidation
        if not last_ts and episodes_since > 0:
            should_consolidate = True

        if not should_consolidate:
            return

        # Run consolidation + decay
        lock_path = self._db_path.parent / ".consolidation.lock"
        if lock_path.exists():
            logger.debug("AutoDream: consolidation lock exists, skipping")
            return

        try:
            lock_path.write_text(str(now.isoformat()))
            await self.consolidate()
            await self._detect_contradictions()
            await self.decay()

            # Update metadata
            conn = self._open_conn()
            conn.execute(
                "INSERT OR REPLACE INTO memory_meta (key, value, updated_at) "
                "VALUES ('last_consolidation_ts', ?, ?)",
                (now.isoformat(), now.isoformat()),
            )
            conn.execute(
                "INSERT OR REPLACE INTO memory_meta (key, value, updated_at) "
                "VALUES ('episodes_since_consolidation', '0', ?)",
                (now.isoformat(),),
            )
            conn.commit()
            conn.close()
            logger.info("AutoDream: consolidation complete")
        finally:
            if lock_path.exists():
                lock_path.unlink()

    async def _detect_contradictions(self):
        """Detect and resolve contradictory memories.

        Scans for pairs with high word similarity but opposing sentiment
        (e.g., "always use X" vs "never use X"). Keeps the more recent one.
        """
        conn = self._open_conn()
        negation_words = {"never", "don't", "avoid", "stop", "not", "no"}
        affirmation_words = {"always", "must", "should", "use", "prefer"}

        rows = conn.execute(
            "SELECT memory_id, text, confidence, created_at, "
            "superseded_by FROM semantic WHERE superseded_by IS NULL"
        ).fetchall()

        superseded = []
        for i, (id_a, text_a, conf_a, created_a, _) in enumerate(rows):
            words_a = set(text_a.lower().split())
            has_neg_a = bool(words_a & negation_words)
            has_aff_a = bool(words_a & affirmation_words)
            if not (has_neg_a or has_aff_a):
                continue

            for j in range(i + 1, len(rows)):
                id_b, text_b, conf_b, created_b, _ = rows[j]
                words_b = set(text_b.lower().split())
                has_neg_b = bool(words_b & negation_words)
                has_aff_b = bool(words_b & affirmation_words)

                # Check for opposing sentiment with similar topic
                if not ((has_neg_a and has_aff_b) or (has_aff_a and has_neg_b)):
                    continue

                # Check topic similarity (words minus sentiment words)
                topic_a = words_a - negation_words - affirmation_words
                topic_b = words_b - negation_words - affirmation_words
                if not topic_a or not topic_b:
                    continue
                overlap = len(topic_a & topic_b) / len(topic_a | topic_b)
                if overlap < 0.4:
                    continue

                # Contradiction found — supersede the older one
                if created_a < created_b:
                    superseded.append((id_a, id_b))
                else:
                    superseded.append((id_b, id_a))

        for old_id, new_id in superseded:
            conn.execute(
                "UPDATE semantic SET superseded_by = ? WHERE memory_id = ?",
                (new_id, old_id),
            )

        if superseded:
            conn.commit()
            logger.info(
                f"AutoDream: {len(superseded)} contradictions resolved"
            )
        conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # BACKWARDS COMPATIBILITY — Old API surface
    # ═══════════════════════════════════════════════════════════════════

    async def extract_principles(
        self, task_id: str, outcome: dict, code_files: list[dict] | None = None,
    ) -> list[Principle]:
        """Extract principles from a completed task (backwards compatible).

        Wraps the new record_episode + extraction pipeline.
        """
        await self.record_episode(
            task_id=task_id,
            task_description=outcome.get("description", task_id),
            outcome=outcome,
            code_files=code_files,
        )
        return await self.get_principles(min_confidence=0.2)

    # ═══════════════════════════════════════════════════════════════════
    # INTERNALS
    # ═══════════════════════════════════════════════════════════════════

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """Safely evaluate a condition string against outcome context."""
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
                if op == ">=":
                    return val >= threshold
                if op == "<=":
                    return val <= threshold
                if op == ">":
                    return val > threshold
                if op == "<":
                    return val < threshold
                if op == "==":
                    return val == threshold
        return False

    def _initial_confidence(self, outcome: dict) -> float:
        """Calculate initial confidence based on outcome quality."""
        score = outcome.get("score", 0.5)
        return round(min(0.8, 0.3 + score * 0.3), 2)

    def _calculate_importance(
        self, confidence: float, evidence_count: int, last_reinforced: str
    ) -> float:
        """Calculate importance score (0-1) from multiple signals.

        importance = confidence * evidence_factor * recency_factor
        """
        # Evidence factor: log scale, caps at ~2x for 50+ observations
        evidence_factor = min(2.0, 1.0 + math.log(evidence_count + 1) * 0.2)

        # Recency factor
        recency = self._recency_score(last_reinforced)

        importance = confidence * evidence_factor * (0.5 + 0.5 * recency)
        return round(min(1.0, importance), 4)

    def _recency_score(self, timestamp: str) -> float:
        """Calculate recency score (0-1) from timestamp. Recent = higher."""
        if not timestamp:
            return 0.3
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            days_ago = (datetime.now(timezone.utc) - ts).total_seconds() / 86400
            # Exponential decay: 1.0 at 0 days, 0.5 at 7 days, ~0.1 at 30 days
            return max(0.05, math.exp(-days_ago / 10))
        except (ValueError, TypeError):
            return 0.3

    async def _find_similar_semantic(self, text: str) -> str | None:
        """Find an existing semantic memory similar to the given text.

        Returns memory_id if found, None otherwise.
        Uses Jaccard similarity on word sets.
        """
        candidate_words = set(text.lower().split())
        if not candidate_words:
            return None

        conn = self._open_conn()
        rows = conn.execute("SELECT memory_id, text FROM semantic").fetchall()
        conn.close()

        for memory_id, existing_text in rows:
            existing_words = set(existing_text.lower().split())
            if not existing_words:
                continue
            similarity = len(candidate_words & existing_words) / len(
                candidate_words | existing_words
            )
            if similarity > 0.6:
                return memory_id
        return None

    async def _reinforce_semantic(self, memory_id: str, source_episode: str):
        """Reinforce an existing semantic memory."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._open_conn()
        row = conn.execute(
            "SELECT evidence_count, confidence, source_episodes FROM semantic WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if row:
            evidence = row[0] + 1
            # Logarithmic confidence growth, caps at 0.95
            confidence = min(0.95, 0.3 + math.log(evidence + 1) * 0.15)
            importance = self._calculate_importance(confidence, evidence, now)
            sources = json.loads(row[2] or "[]")
            if source_episode and source_episode not in sources:
                sources.append(source_episode)
                # Cap source list
                sources = sources[-50:]
            conn.execute(
                """UPDATE semantic
                   SET evidence_count = ?, confidence = ?, importance = ?,
                       source_episodes = ?, last_reinforced = ?
                   WHERE memory_id = ?""",
                (evidence, round(confidence, 3), importance,
                 json.dumps(sources), now, memory_id),
            )
            conn.commit()
        conn.close()

    def _detect_factors(self, outcome: dict, code_files: list[dict] | None) -> list[str]:
        """Detect which causal factors are present."""
        factors = []
        if outcome.get("test_pass_rate", 0) > 0.8:
            factors.append("test_first")
        if outcome.get("reflexion_rounds", 0) <= 1:
            factors.append("small_functions")
        if outcome.get("read_before_edit", False):
            factors.append("read_before_edit")
        if outcome.get("repo_map_used", False):
            factors.append("repo_map_first")
        if code_files:
            for f in code_files:
                if isinstance(f, str):
                    continue
                content = f.get("content", "")
                if "-> " in content or ": str" in content or ": int" in content:
                    factors.append("type_hints")
                    break
        return factors

    def _project_name(self) -> str:
        """Get current project name from directory."""
        return self.config.project_dir.parent.name
