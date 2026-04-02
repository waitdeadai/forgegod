"""ForgeGod Budget Tracker — SQLite-backed cost tracking and budget modes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from forgegod.config import ForgeGodConfig
from forgegod.models import BudgetMode, BudgetStatus, CostRecord, ModelUsage


class BudgetTracker:
    """Tracks LLM costs in local SQLite. Enforces budget modes."""

    def __init__(self, config: ForgeGodConfig):
        self.config = config
        self._db_path = config.project_dir / "costs.db"
        self._ensure_db()

    def _ensure_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL,
                role TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                task_id TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_costs_date
            ON costs (timestamp)
        """)
        conn.commit()
        conn.close()

    def record(self, usage: ModelUsage, role: str = "", task_id: str = ""):
        """Record a cost event."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "INSERT INTO costs (timestamp, model, provider, role, input_tokens, output_tokens, cost_usd, task_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                usage.model,
                usage.provider,
                role,
                usage.input_tokens,
                usage.output_tokens,
                usage.cost_usd,
                task_id,
            ),
        )
        conn.commit()
        conn.close()

    def get_status(self) -> BudgetStatus:
        """Get current budget status."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = sqlite3.connect(str(self._db_path))

        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0), COUNT(*) FROM costs WHERE timestamp LIKE ?",
            (f"{today}%",),
        ).fetchone()
        spent_today = row[0]
        calls_today = row[1]

        total_row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM costs").fetchone()
        spent_total = total_row[0]
        conn.close()

        limit = self.config.budget.daily_limit_usd
        return BudgetStatus(
            mode=self.config.budget.mode,
            daily_limit_usd=limit,
            spent_today_usd=round(spent_today, 6),
            spent_total_usd=round(spent_total, 6),
            remaining_today_usd=round(max(0, limit - spent_today), 6),
            calls_today=calls_today,
        )

    def get_model_breakdown(self) -> dict[str, dict]:
        """Get per-model cost breakdown for today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = sqlite3.connect(str(self._db_path))
        rows = conn.execute(
            "SELECT model, COUNT(*), COALESCE(SUM(cost_usd), 0) "
            "FROM costs WHERE timestamp LIKE ? GROUP BY model",
            (f"{today}%",),
        ).fetchall()
        conn.close()
        return {row[0]: {"calls": row[1], "cost": round(row[2], 6)} for row in rows}

    def check_budget(self) -> BudgetMode:
        """Check if we should change budget mode based on spend.

        Returns the effective mode (may auto-throttle if approaching limit).
        """
        if self.config.budget.mode == BudgetMode.HALT:
            return BudgetMode.HALT

        status = self.get_status()

        # Auto-halt at 100% of daily limit (check FIRST — higher priority)
        if status.spent_today_usd >= status.daily_limit_usd:
            return BudgetMode.HALT

        # Auto-throttle at 80% of daily limit
        if status.spent_today_usd >= status.daily_limit_usd * 0.8:
            if self.config.budget.mode == BudgetMode.NORMAL:
                return BudgetMode.THROTTLE

        return self.config.budget.mode
