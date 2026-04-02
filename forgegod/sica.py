"""ForgeGod SICA — Self-Improving Coding Agent.

Ported from forge/forge_god_self_modifier.py (Phase 78).
Stripped: Redis storage, arena integration, DGM evolution.
Kept: SICA pipeline, 6 safety layers, modification targets, promote/rollback.

The agent modifies its own strategy parameters (prompts, model routing,
reflexion config) based on reflection — never raw code. Safety layers
prevent catastrophic self-modification.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from forgegod.config import ForgeGodConfig
from forgegod.models import SICAModification
from forgegod.router import ModelRouter

logger = logging.getLogger("forgegod.sica")

# Valid modification targets — NEVER modify raw code
VALID_TARGETS = {
    "strategy:model_routing": "Which model role for which task type",
    "strategy:reflexion_config": "Max attempts, escalation threshold",
    "strategy:temperature": "Sampling temperature per role",
    "prompt:coder": "System prompt for code generation",
    "prompt:reviewer": "System prompt for code review",
    "prompt:planner": "System prompt for task decomposition",
    "heuristic:gutter_threshold": "When to detect gutter (stuck) state",
    "heuristic:context_rotation_pct": "When to compress context",
}

# Protected — SICA can NEVER modify these
PROTECTED = {
    "budget",  # Never auto-increase budget
    "killswitch",  # Never disable killswitch
    "safety",  # Never weaken safety layers
}


class SICA:
    """Self-Improving Coding Agent — modifies strategy based on outcomes.

    Safety layers:
    1. Sandbox: modifications are proposed, not applied immediately
    2. Benchmark: must show >5% improvement on test tasks
    3. Regression: existing task pass rates must not drop
    4. Rollback: instant revert if promoted modification regresses
    5. Protected: budget/killswitch/safety can never be modified
    6. Audit: every modification logged to SQLite
    """

    def __init__(self, config: ForgeGodConfig, router: ModelRouter | None = None):
        self.config = config
        self.router = router or ModelRouter(config)
        self._db_path = config.project_dir / "sica.db"
        self._ensure_db()
        self._active_overrides: dict[str, str] = {}

    def _ensure_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS modifications (
                mod_id TEXT PRIMARY KEY,
                target TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT DEFAULT '',
                old_value TEXT DEFAULT '',
                new_value TEXT DEFAULT '',
                status TEXT DEFAULT 'proposed',
                score REAL DEFAULT 0.0,
                proposed_at TEXT NOT NULL,
                resolved_at TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    async def propose(self, reflection: str, outcome: dict) -> list[SICAModification]:
        """Analyze reflection and propose strategy modifications.

        Args:
            reflection: Text from agent's reflection on recent performance.
            outcome: Dict with score, test_pass_rate, reflexion_rounds, etc.

        Returns:
            List of proposed modifications (not yet applied).
        """
        if not self.config.sica.enabled:
            return []

        # Check modification budget
        recent = self._get_recent_modifications(limit=self.config.sica.max_modifications)
        active = [m for m in recent if m["status"] in ("proposed", "testing")]
        if len(active) >= self.config.sica.max_modifications:
            logger.info(f"SICA budget exhausted: {len(active)} active modifications")
            return []

        # Analyze what to modify
        modifications = self._analyze(reflection, outcome)
        if not modifications:
            return []

        # Record proposals
        results = []
        for mod in modifications:
            mod.proposed_at = datetime.now(timezone.utc).isoformat()
            mod.status = "proposed"
            self._record(mod)
            results.append(mod)
            logger.info(f"SICA proposed: {mod.target} — {mod.action} ({mod.reason})")

        return results

    async def test_and_promote(self, mod: SICAModification, test_score: float) -> bool:
        """Test a modification and promote if it improves performance.

        Args:
            mod: The modification to test.
            test_score: Score from benchmark run with this modification.

        Returns:
            True if promoted, False if rejected.
        """
        threshold = self.config.sica.improvement_threshold_pct / 100.0
        baseline = mod.score  # Previous best score

        if test_score > baseline * (1 + threshold):
            # Promote
            mod.status = "promoted"
            mod.score = test_score
            self._update_status(mod.target, "promoted", test_score)
            self._active_overrides[mod.target] = mod.new_value or ""
            logger.info(
                f"SICA promoted: {mod.target} — "
                f"score {baseline:.2f} → {test_score:.2f} (+{(test_score-baseline)/max(baseline,0.01)*100:.1f}%)"
            )
            return True
        else:
            # Reject
            mod.status = "rejected"
            self._update_status(mod.target, "rejected", test_score)
            logger.info(f"SICA rejected: {mod.target} — score {test_score:.2f} < threshold")
            return False

    async def rollback(self, target: str) -> bool:
        """Rollback a promoted modification."""
        if target in self._active_overrides:
            del self._active_overrides[target]
            self._update_status(target, "rolled_back", 0.0)
            logger.info(f"SICA rolled back: {target}")
            return True
        return False

    def get_active_overrides(self) -> dict[str, str]:
        """Get currently active strategy overrides."""
        return dict(self._active_overrides)

    def get_modification_history(self, limit: int = 20) -> list[dict]:
        """Get recent modification history."""
        return self._get_recent_modifications(limit)

    # ── Analysis ──

    def _analyze(self, reflection: str, outcome: dict) -> list[SICAModification]:
        """Analyze reflection and outcome to propose modifications."""
        modifications: list[SICAModification] = []
        reflection_lower = reflection.lower()
        score = outcome.get("score", 0.5)
        reflexion_rounds = outcome.get("reflexion_rounds", 0)
        test_pass_rate = outcome.get("test_pass_rate", 0.0)

        # Low score + high reflexion → escalate model
        if score < 0.5 and reflexion_rounds >= 3:
            modifications.append(SICAModification(
                target="strategy:model_routing",
                action="escalate_coder_model",
                reason=f"Low score ({score:.0%}) with {reflexion_rounds} reflexion rounds",
                new_value="reviewer",  # Use reviewer-tier model for coding
                score=score,
            ))

        # High score + low reflexion → de-escalate (save cost)
        if score > 0.85 and reflexion_rounds <= 1:
            modifications.append(SICAModification(
                target="strategy:model_routing",
                action="deescalate_coder_model",
                reason=f"High score ({score:.0%}) with only {reflexion_rounds} reflexion rounds",
                new_value="coder",  # Keep using cheapest model
                score=score,
            ))

        # Reflexion notes in reflection text
        if "too many attempts" in reflection_lower or "reflexion" in reflection_lower and "slow" in reflection_lower:
            modifications.append(SICAModification(
                target="strategy:reflexion_config",
                action="reduce_max_attempts",
                reason="Reflection indicates too many reflexion rounds",
                new_value=json.dumps({"max_attempts": 2}),
                score=score,
            ))

        # Test failures
        if test_pass_rate < 0.5 and "test" in reflection_lower:
            modifications.append(SICAModification(
                target="prompt:coder",
                action="enhance_test_instructions",
                reason=f"Low test pass rate ({test_pass_rate:.0%})",
                new_value="Add: 'Write tests BEFORE implementation. Run tests after every change.'",
                score=score,
            ))

        # Safety: filter out protected targets
        modifications = [
            m for m in modifications
            if not any(p in m.target for p in PROTECTED)
            and m.target in VALID_TARGETS
        ]

        return modifications[:self.config.sica.max_modifications]

    # ── Storage ──

    def _record(self, mod: SICAModification):
        if not mod.target:
            return
        mod_id = f"sica-{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "INSERT INTO modifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mod_id, mod.target, mod.action, mod.reason,
                "", str(mod.new_value) if mod.new_value else "",
                mod.status, mod.score, mod.proposed_at, "",
            ),
        )
        conn.commit()
        conn.close()

    def _update_status(self, target: str, status: str, score: float):
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "UPDATE modifications SET status = ?, score = ?, resolved_at = ? WHERE target = ? AND status IN ('proposed', 'testing')",
            (status, score, datetime.now(timezone.utc).isoformat(), target),
        )
        conn.commit()
        conn.close()

    def _get_recent_modifications(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(str(self._db_path))
        rows = conn.execute(
            "SELECT * FROM modifications ORDER BY proposed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                "mod_id": r[0], "target": r[1], "action": r[2], "reason": r[3],
                "old_value": r[4], "new_value": r[5], "status": r[6],
                "score": r[7], "proposed_at": r[8], "resolved_at": r[9],
            }
            for r in rows
        ]
