"""Tests for ForgeGod 5-tier memory system."""

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


# ── Tier 1: Episodic ──

class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_record_episode(self, memory):
        ep_id = await memory.record_episode(
            task_id="task-1",
            task_description="Add /health endpoint",
            outcome={"score": 0.9, "reflexion_rounds": 1},
        )
        assert ep_id.startswith("ep-")

    @pytest.mark.asyncio
    async def test_get_recent_episodes(self, memory):
        await memory.record_episode("t1", "Task A", {"score": 0.8})
        await memory.record_episode("t2", "Task B", {"score": 0.5})
        episodes = await memory.get_recent_episodes(limit=5)
        assert len(episodes) == 2
        assert episodes[0]["task_id"] == "t2"  # Most recent first


# ── Tier 2: Semantic ──

class TestSemanticMemory:
    @pytest.mark.asyncio
    async def test_add_semantic(self, memory):
        mem_id = await memory.add_semantic(
            text="Always run tests before committing",
            category="testing",
            confidence=0.7,
        )
        assert mem_id.startswith("sm-")

    @pytest.mark.asyncio
    async def test_dedup_semantic(self, memory):
        id1 = await memory.add_semantic("Run tests before committing", category="testing")
        id2 = await memory.add_semantic("Run tests before committing code", category="testing")
        # Should reinforce, not duplicate (Jaccard similarity > 0.6)
        assert id2 == id1

    @pytest.mark.asyncio
    async def test_get_principles_compat(self, memory):
        await memory.add_semantic("Type hints reduce bugs", category="readability", confidence=0.8)
        principles = await memory.get_principles(category="readability", min_confidence=0.5)
        assert len(principles) == 1
        assert "Type hints" in principles[0].text

    @pytest.mark.asyncio
    async def test_learnings_text(self, memory):
        await memory.add_semantic(
            "Guard clauses prevent nesting",
            category="design",
            confidence=0.6,
        )
        text = await memory.get_learnings_text(limit=5)
        assert "Guard clauses" in text
        assert "design" in text


# ── Tier 3: Procedural ──

class TestProceduralMemory:
    @pytest.mark.asyncio
    async def test_add_procedure(self, memory):
        pid = await memory.add_procedure(
            name="Fix import errors",
            description="Check virtualenv and requirements.txt",
            pattern_type="fix",
            language="python",
        )
        assert pid.startswith("proc-")

    @pytest.mark.asyncio
    async def test_get_procedures(self, memory):
        await memory.add_procedure("Fix imports", pattern_type="fix", language="python")
        await memory.add_procedure("Add endpoint", pattern_type="pattern", language="python")
        procs = await memory.get_procedures(pattern_type="fix")
        assert len(procs) == 1
        assert procs[0]["name"] == "Fix imports"

    @pytest.mark.asyncio
    async def test_record_outcome(self, memory):
        pid = await memory.add_procedure("Test pattern", pattern_type="fix")
        await memory.record_procedure_outcome(pid, success=True)
        await memory.record_procedure_outcome(pid, success=True)
        await memory.record_procedure_outcome(pid, success=False)
        procs = await memory.get_procedures()
        assert procs[0]["usage_count"] == 3
        assert procs[0]["success_rate"] > 0.5


# ── Tier 4: Graph ──

class TestGraphMemory:
    @pytest.mark.asyncio
    async def test_causal_edges(self, memory):
        await memory.record_episode(
            "t1", "Add tests",
            {"score": 0.9, "test_pass_rate": 0.95},
        )
        edges = await memory.get_causal_edges()
        assert len(edges) > 0

    @pytest.mark.asyncio
    async def test_success_factors(self, memory):
        for i in range(5):
            await memory.record_episode(
                f"t{i}", f"Task {i}",
                {"score": 0.9, "test_pass_rate": 0.95},
            )
        factors = await memory.get_success_factors()
        assert "test_first" in factors


# ── Tier 5: Error-Solution ──

class TestErrorSolution:
    @pytest.mark.asyncio
    async def test_record_error_solution(self, memory):
        eid = await memory.record_error_solution(
            error_pattern="ModuleNotFoundError: No module named 'foo'",
            solution="pip install foo",
            error_context="import",
        )
        assert eid.startswith("err-")

    @pytest.mark.asyncio
    async def test_lookup_error(self, memory):
        await memory.record_error_solution(
            "ModuleNotFoundError", "pip install the module",
        )
        results = await memory.lookup_error("ModuleNotFoundError: No module named 'bar'")
        assert len(results) == 1
        assert "pip install" in results[0]["solution"]

    @pytest.mark.asyncio
    async def test_dedup_error_solution(self, memory):
        id1 = await memory.record_error_solution("ImportError", "fix imports")
        id2 = await memory.record_error_solution("ImportError", "fix imports v2")
        assert id2 == id1  # Deduped by pattern


# ── Recall ──

class TestRecall:
    @pytest.mark.asyncio
    async def test_recall_empty(self, memory):
        result = await memory.recall(query="anything")
        assert result == ""

    @pytest.mark.asyncio
    async def test_recall_with_data(self, memory):
        await memory.add_semantic("Always validate input", category="security", confidence=0.8)
        await memory.record_error_solution("ValidationError", "add input checks")
        result = await memory.recall(query="validate input", include_procedural=True)
        assert "validate" in result.lower()

    @pytest.mark.asyncio
    async def test_recall_categories(self, memory):
        await memory.add_semantic("Use pytest fixtures", category="testing", confidence=0.7)
        await memory.add_semantic("Guard clauses", category="design", confidence=0.7)
        result = await memory.recall(category="testing")
        assert "pytest" in result
        assert "Guard" not in result


# ── Maintenance ──

class TestMaintenance:
    @pytest.mark.asyncio
    async def test_consolidate(self, memory):
        # Add similar memories (high word overlap for Jaccard > 0.65)
        await memory.add_semantic("Always run tests before committing code changes", confidence=0.5)
        await memory.add_semantic("Always run tests before committing any changes", confidence=0.5)
        await memory.add_semantic("Something completely different and unrelated", confidence=0.5)
        await memory.consolidate()
        principles = await memory.get_principles()
        # Should have merged the very similar ones, keeping 2
        assert len(principles) <= 2

    @pytest.mark.asyncio
    async def test_decay(self, memory):
        await memory.add_semantic("Old memory", confidence=0.8)
        # Decay won't do much with fresh memories, but shouldn't error
        await memory.decay()

    @pytest.mark.asyncio
    async def test_health(self, memory):
        await memory.add_semantic("Test principle", confidence=0.7)
        await memory.record_error_solution("TestError", "fix it")
        report = await memory.health()
        assert report["semantic_memories"] == 1
        assert report["error_solutions"] == 1
        assert "health_score" in report


# ── Backwards Compat ──

class TestBackwardsCompat:
    @pytest.mark.asyncio
    async def test_extract_principles(self, memory):
        """Old API should still work."""
        principles = await memory.extract_principles(
            task_id="legacy-1",
            outcome={"score": 0.9, "test_pass_rate": 0.95, "description": "Legacy task"},
        )
        assert isinstance(principles, list)
