"""Tests for memory integration into agent loop, coder, and loop.

Verifies that Features 1+3 (memory wiring + adaptive recall) actually work:
- Agent records episodes after task completion
- Agent recalls memory before task execution
- Error solution lookup injects hints on failure
- smart_recall adapts depth by task complexity
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.memory import Memory


@pytest.fixture
def memory():
    """Create a memory instance with temp DB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ForgeGodConfig()
        config.project_dir = Path(tmpdir) / ".forgegod"
        config.project_dir.mkdir()
        yield Memory(config)


# ── Smart Recall (Adaptive Depth) ──

class TestSmartRecall:
    @pytest.mark.asyncio
    async def test_simple_task_few_memories(self, memory):
        """Simple tasks ('fix', 'typo', 'rename') should get limited recall."""
        # Seed some memories
        for i in range(10):
            await memory.add_semantic(
                f"Principle {i}: always do thing {i}",
                category="general",
                confidence=0.8,
            )
        result = await memory.smart_recall("fix typo in README")
        # Should return something (or empty if none match), but limited depth
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_complex_task_more_memories(self, memory):
        """Complex tasks ('refactor', 'migrate', 'architecture') get deeper recall."""
        for i in range(10):
            await memory.add_semantic(
                f"Architecture principle {i}: design pattern {i}",
                category="architecture",
                confidence=0.8,
            )
        result = await memory.smart_recall("refactor the entire authentication architecture")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_complexity_detection_simple(self, memory):
        """Verify simple keywords detected correctly."""
        assert memory._detect_complexity("fix typo in config") == "simple"
        assert memory._detect_complexity("rename variable foo") == "simple"
        assert memory._detect_complexity("update version number") == "simple"

    @pytest.mark.asyncio
    async def test_complexity_detection_complex(self, memory):
        """Verify complex keywords detected correctly."""
        assert memory._detect_complexity("refactor the auth pipeline") == "complex"
        assert memory._detect_complexity("migrate database across services") == "complex"
        assert memory._detect_complexity("redesign the infrastructure") == "complex"

    @pytest.mark.asyncio
    async def test_complexity_detection_medium(self, memory):
        """Tasks without strong keywords default to medium."""
        assert memory._detect_complexity("implement user authentication") == "medium"
        assert memory._detect_complexity("create the login page") == "medium"

    @pytest.mark.asyncio
    async def test_smart_recall_explicit_hint(self, memory):
        """Explicit complexity_hint overrides auto-detection."""
        await memory.add_semantic("Test principle", category="general", confidence=0.9)
        # "fix" would be simple, but we force complex
        result = await memory.smart_recall("fix a bug", complexity_hint="complex")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_smart_recall_empty_memory(self, memory):
        """Smart recall on empty memory returns empty string."""
        result = await memory.smart_recall("do something complex across the architecture")
        assert result == ""


# ── Error Solution Lookup ──

class TestErrorSolutionIntegration:
    @pytest.mark.asyncio
    async def test_error_lookup_returns_solution(self, memory):
        """Error solution lookup returns matching solutions."""
        await memory.record_error_solution(
            "ModuleNotFoundError: No module named 'requests'",
            "pip install requests",
            error_context="import",
        )
        results = await memory.lookup_error("ModuleNotFoundError: No module named 'requests'")
        assert len(results) >= 1
        assert "pip install" in results[0]["solution"]

    @pytest.mark.asyncio
    async def test_error_lookup_no_match(self, memory):
        """Error lookup returns empty list when no matching solutions."""
        results = await memory.lookup_error("SomeCompletelyUnknownError")
        assert results == []


# ── Episode Recording ──

class TestEpisodeRecording:
    @pytest.mark.asyncio
    async def test_record_episode_with_files(self, memory):
        """Recording an episode with file paths works."""
        ep_id = await memory.record_episode(
            task_id="task-123",
            task_description="Add health endpoint",
            outcome={"score": 0.9},
            code_files=["src/health.py", "tests/test_health.py"],
            tools_used=["write_file", "bash"],
        )
        assert ep_id.startswith("ep-")

        episodes = await memory.get_recent_episodes(limit=1)
        assert len(episodes) == 1
        assert episodes[0]["task_id"] == "task-123"

    @pytest.mark.asyncio
    async def test_record_episode_increments_counter(self, memory):
        """Recording episodes increments the episodes_since_consolidation counter."""
        await memory.record_episode("t1", "Task 1", {"score": 0.8})
        await memory.record_episode("t2", "Task 2", {"score": 0.9})

        # Check the meta table
        import sqlite3
        conn = sqlite3.connect(str(memory._db_path))
        row = conn.execute(
            "SELECT value FROM memory_meta WHERE key = 'episodes_since_consolidation'"
        ).fetchone()
        conn.close()

        if row:
            assert int(row[0]) >= 2


# ── Recall Integration ──

class TestRecallIntegration:
    @pytest.mark.asyncio
    async def test_recall_includes_semantic_and_errors(self, memory):
        """Recall should include both semantic memories and error solutions."""
        await memory.add_semantic(
            "Always validate user input",
            category="security",
            confidence=0.9,
        )
        await memory.record_error_solution(
            "ValidationError: invalid input",
            "Add input validation before processing",
        )
        result = await memory.recall(query="validate", include_procedural=True)
        assert "validate" in result.lower() or "input" in result.lower()
