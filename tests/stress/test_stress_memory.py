"""Stress tests for ForgeGod 4-tier Memory — throughput, scaling, concurrency."""

from __future__ import annotations

import asyncio
import json
import os
import random
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from forgegod.memory import Memory

from .conftest import adjusted_max_latency, adjusted_min_rate, percentiles, record_metric, timed

pytestmark = pytest.mark.stress

CATEGORIES = ["testing", "security", "design", "architecture", "process",
              "readability", "performance", "debugging", "deployment", "api"]


def _seed_semantic_bulk(memory: Memory, n: int, rng: random.Random):
    """Directly insert N semantic memories via SQLite (bypasses LLM extraction)."""
    conn = sqlite3.connect(str(memory._db_path))
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(n):
        age_days = rng.randint(0, 90)
        created = (now - timedelta(days=age_days)).isoformat()
        reinforced = (now - timedelta(days=rng.randint(0, age_days))).isoformat()
        rows.append((
            f"sem-{uuid.uuid4().hex[:12]}",
            f"Principle {i}: {rng.choice(CATEGORIES)} guideline for pattern {rng.randint(1,999)}",
            rng.choice(CATEGORIES),
            round(rng.uniform(0.1, 1.0), 3),  # confidence
            round(rng.uniform(0.1, 1.0), 3),  # importance
            rng.randint(1, 20),  # evidence_count
            rng.randint(0, 15),  # success_count
            rng.randint(0, 5),  # failure_count
            "[]",  # source_episodes
            "[]",  # tags
            reinforced,  # last_recalled
            reinforced,  # last_reinforced
            created,
            "stress_test",
        ))
    conn.executemany(
        """INSERT INTO semantic
           (memory_id, text, category, confidence, importance, evidence_count,
            success_count, failure_count, source_episodes, tags,
            last_recalled, last_reinforced, created_at, project)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()


def _seed_episodes_bulk(memory: Memory, n: int, rng: random.Random):
    """Directly insert N episodic records via SQLite."""
    conn = sqlite3.connect(str(memory._db_path))
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(n):
        age_days = rng.randint(0, 90)
        created = (now - timedelta(days=age_days)).isoformat()
        rows.append((
            f"ep-{uuid.uuid4().hex[:12]}",
            f"task-{i}",
            f"Implement {rng.choice(CATEGORIES)} feature #{i}",
            json.dumps({"score": round(rng.uniform(0.3, 1.0), 2)}),
            "[]", "[]",
            1 if rng.random() > 0.3 else 0,
            rng.randint(0, 3),
            "test-model",
            round(rng.uniform(0.001, 0.5), 4),
            round(rng.uniform(5, 120), 1),
            "",
            created,
            "stress_test",
        ))
    conn.executemany(
        """INSERT INTO episodes
           (episode_id, task_id, task_description, outcome, files_touched,
            tools_used, success, reflexion_rounds, model_used, cost_usd,
            duration_s, error_log, created_at, project)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()


class TestEpisodicWriteThroughput:
    @pytest.mark.asyncio
    async def test_write_1000_episodes(self, memory_instance):
        """1,000 record_episode() calls — measure throughput."""
        n = 1000
        with timed() as t:
            for i in range(n):
                await memory_instance.record_episode(
                    task_id=f"stress-{i}",
                    task_description=f"Stress task {i}: add endpoint",
                    outcome={"score": 0.85, "reflexion_rounds": 1},
                )

        wps = n / (t.elapsed / 1000)
        db_size = os.path.getsize(str(memory_instance._db_path))

        record_metric("memory", "episodic_writes_per_sec", round(wps, 1))
        record_metric("memory", "db_size_1k_episodes_kb", round(db_size / 1024, 1))

        min_rate = adjusted_min_rate(10, profile="memory_write")
        assert wps > min_rate, f"Expected >{min_rate:.1f} writes/sec, got {wps:.1f}"


class TestConcurrentReadWrite:
    @pytest.mark.asyncio
    async def test_concurrent_rw(self, memory_instance, seeded_rng):
        """50 writers + 50 readers simultaneously — no crashes."""
        # Seed some data first
        _seed_semantic_bulk(memory_instance, 200, seeded_rng)
        errors = []

        async def writer(i):
            try:
                await memory_instance.record_episode(
                    f"conc-w-{i}", f"Concurrent write {i}", {"score": 0.7}
                )
            except Exception as e:
                errors.append(f"write-{i}: {e}")

        async def reader(i):
            try:
                await memory_instance.recall(query=f"test query {i}", limit=5)
            except Exception as e:
                errors.append(f"read-{i}: {e}")

        with timed() as t:
            tasks = [writer(i) for i in range(50)] + [reader(i) for i in range(50)]
            await asyncio.gather(*tasks, return_exceptions=True)

        error_count = len(errors)
        record_metric("memory", "concurrent_rw_errors", error_count)
        record_metric("memory", "concurrent_rw_elapsed_ms", round(t.elapsed, 1))

        # SQLite on Windows may have some lock contention — tolerate up to 5%
        assert error_count <= 5, f"Too many concurrent errors: {error_count}"


class TestRecallLatencyAtScale:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("scale", [100, 1000, 10000])
    async def test_recall_latency(self, memory_instance, seeded_rng, scale):
        """Recall latency at various scales."""
        _seed_semantic_bulk(memory_instance, scale, seeded_rng)

        queries = [f"{seeded_rng.choice(CATEGORIES)} pattern" for _ in range(20)]
        latencies = []

        for q in queries:
            start = time.perf_counter()
            await memory_instance.recall(query=q, limit=10)
            latencies.append((time.perf_counter() - start) * 1000)

        p = percentiles(latencies)
        record_metric("memory", f"recall_at_{scale}_p50_ms", round(p["p50"], 2))
        record_metric("memory", f"recall_at_{scale}_p95_ms", round(p["p95"], 2))
        record_metric("memory", f"recall_at_{scale}_p99_ms", round(p["p99"], 2))

        # Recall should be reasonable even at scale
        max_ok = adjusted_max_latency(
            500 if scale <= 1000 else 3000,
            profile="memory_recall",
        )
        assert p["p95"] < max_ok, f"Recall p95 too slow at {scale}: {p['p95']:.1f}ms"


class TestConsolidationUnderLoad:
    @pytest.mark.asyncio
    async def test_consolidation_stress(self, memory_instance, seeded_rng):
        """200 similar semantic memories — consolidate while querying."""
        # Create memories with overlapping text to trigger merges
        conn = sqlite3.connect(str(memory_instance._db_path))
        now = datetime.now(timezone.utc).isoformat()
        for i in range(200):
            variant = seeded_rng.randint(0, 9)
            conn.execute(
                """INSERT INTO semantic
                   (memory_id, text, category, confidence, importance,
                    evidence_count, success_count, failure_count,
                    source_episodes, tags, last_recalled, last_reinforced,
                    created_at, project)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"consol-{i}",
                    f"Always validate input at service boundaries variant-{variant}",
                    "security",
                    round(seeded_rng.uniform(0.3, 0.9), 2),
                    0.5, 1, 1, 0, "[]", "[]", now, now, now, "stress_test",
                ),
            )
        conn.commit()
        conn.close()

        with timed() as t:
            await memory_instance.consolidate()

        record_metric("memory", "consolidation_200_ms", round(t.elapsed, 1))

        # Verify some consolidation happened (or at least it ran without error)
        conn = sqlite3.connect(str(memory_instance._db_path))
        count = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
        conn.close()
        record_metric("memory", "post_consolidation_count", count)


class TestDecayAtScale:
    @pytest.mark.asyncio
    async def test_decay_10k(self, memory_instance, seeded_rng):
        """10,000 semantic memories — measure decay performance."""
        _seed_semantic_bulk(memory_instance, 10000, seeded_rng)

        with timed() as t:
            await memory_instance.decay()

        record_metric("memory", "decay_10k_ms", round(t.elapsed, 1))
        assert t.elapsed < 30000, f"Decay took too long: {t.elapsed:.0f}ms"


class TestEntityExtractionThroughput:
    def test_entity_extract_1k(self):
        """1,000 code snippets — measure regex entity extraction speed."""
        from forgegod.memory import ENTITY_PATTERNS

        snippets = [
            f"from app.services.auth import validate_token\n"
            f"class UserHandler{i}(BaseHandler):\n"
            f"    async def get(self):\n"
            f"        raise ValueError('invalid token #{i}')\n"
            for i in range(1000)
        ]

        with timed() as t:
            for snippet in snippets:
                for _etype, pattern in ENTITY_PATTERNS.items():
                    pattern.findall(snippet)

        rate = 1000 / (t.elapsed / 1000)
        record_metric("memory", "entity_extract_per_sec", round(rate, 0))
        assert rate > 100, f"Entity extraction too slow: {rate:.0f}/sec"
