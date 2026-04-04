"""ForgeGod Budget Tracker — SQLite-backed cost tracking and budget modes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from forgegod.config import ForgeGodConfig
from forgegod.models import BudgetMode, BudgetStatus, CostRecord, ModelUsage


class BudgetTracker:
    """Tracks LLM costs in local SQLite. Enforces budget modes."""

    def __init__(self, config: ForgeGodConfig) -> None:
        """Initialize the BudgetTracker.

        Args:
            config: The ForgeGodConfig instance containing budget settings.

        Returns:
            None
        """
        self.config = config
        self._db_path = config.project_dir / "costs.db"
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure the SQLite database exists and is properly initialized.

        Creates the costs table with appropriate schema if it doesn't exist,
        and creates an index on the timestamp column for efficient querying.

        Args:
            None

        Returns:
            None
        """
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

    def record(self, usage: ModelUsage, role: str = "", task_id: str = "") -> None:
        """Record a cost event to the database.

        Args:
            usage: The ModelUsage object containing token counts and cost.
            role: The role that incurred the cost (e.g., 'user', 'assistant', 'system').
            task_id: Optional task identifier for grouping costs.

        Returns:
            None
        """
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
        """Get the current budget status.

        Retrieves the daily spend, total spend, budget mode, and remaining budget
        for the current day from the SQLite database.

        Args:
            None

        Returns:
            BudgetStatus: A BudgetStatus object containing the current budget information.
        """
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
        """Get per-model cost breakdown for today.

        Retrieves the call count and total cost for each model used today.

        Args:
            None

        Returns:
            dict[str, dict]: A dictionary mapping model names to dictionaries
                containing 'calls' (int) and 'cost' (float) for each model.
        """
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
        """Check if we should change budget mode based on current spend.

        Evaluates the current daily spend against configured limits and returns
        the effective budget mode. May auto-throttle or halt if approaching
        or exceeding the daily limit.

        Args:
            None

        Returns:
            BudgetMode: The effective budget mode (HALT, THROTTLE, NORMAL, or LOCAL_ONLY).
        """
        if self.config.budget.mode == BudgetMode.HALT:
            return BudgetMode.HALT

        # Local-only mode uses free models — skip spend checks entirely
        if self.config.budget.mode == BudgetMode.LOCAL_ONLY:
            return BudgetMode.LOCAL_ONLY

        status = self.get_status()

        # Auto-halt at 100% of daily limit (check FIRST — higher priority)
        if status.spent_today_usd >= status.daily_limit_usd:
            return BudgetMode.HALT

        # Auto-throttle at 80% of daily limit
        if status.spent_today_usd >= status.daily_limit_usd * 0.8:
            if self.config.budget.mode == BudgetMode.NORMAL:
                return BudgetMode.THROTTLE

        return self.config.budget.mode
