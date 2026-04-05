"""Stress tests for ForgeGod Tools — file I/O, glob, grep throughput."""

from __future__ import annotations

import time

import pytest

from forgegod.tools.filesystem import edit_file, glob_files, grep_files, read_file, write_file

from .conftest import percentiles, record_metric, timed

pytestmark = pytest.mark.stress


class TestFileReadThroughput:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("size_kb", [1, 10, 100])
    async def test_read_throughput(self, tmp_path, size_kb):
        """Read 500 files at various sizes — measure throughput."""
        n = 500
        # Create files
        content = "x" * (size_kb * 1024)
        for i in range(n):
            (tmp_path / f"file_{i}.txt").write_text(content, encoding="utf-8")

        latencies = []
        with timed() as t:
            for i in range(n):
                start = time.perf_counter()
                await read_file(str(tmp_path / f"file_{i}.txt"))
                latencies.append((time.perf_counter() - start) * 1000)

        rps = n / (t.elapsed / 1000)
        p = percentiles(latencies)

        record_metric("tools", f"read_{size_kb}kb_per_sec", round(rps, 0))
        record_metric("tools", f"read_{size_kb}kb_p50_ms", round(p["p50"], 2))

        assert rps > 50, f"Read {size_kb}KB too slow: {rps:.0f}/sec"


class TestFileWriteThroughput:
    @pytest.mark.asyncio
    async def test_write_1000_files(self, tmp_path):
        """Write 1,000 files — measure throughput."""
        n = 1000
        content = "def hello():\n    return 'world'\n" * 10  # ~300 bytes

        with timed() as t:
            for i in range(n):
                await write_file(str(tmp_path / f"out_{i}.py"), content)

        wps = n / (t.elapsed / 1000)
        record_metric("tools", "write_per_sec", round(wps, 0))

        # Verify files exist
        assert len(list(tmp_path.glob("out_*.py"))) == n
        assert wps > 100, f"Write too slow: {wps:.0f}/sec"


class TestEditFileThroughput:
    @pytest.mark.asyncio
    async def test_edit_500_files(self, tmp_path):
        """500 edit operations — measure throughput and success rate."""
        n = 500
        original = "def process(data):\n    return data.upper()\n"
        for i in range(n):
            (tmp_path / f"edit_{i}.py").write_text(original, encoding="utf-8")

        successes = 0
        with timed() as t:
            for i in range(n):
                result = await edit_file(
                    str(tmp_path / f"edit_{i}.py"),
                    "data.upper()",
                    "data.lower()",
                )
                if "Error" not in result:
                    successes += 1

        eps = n / (t.elapsed / 1000)
        success_rate = successes / n

        record_metric("tools", "edit_per_sec", round(eps, 0))
        record_metric("tools", "edit_success_rate", round(success_rate, 4))

        assert success_rate >= 0.95, f"Edit success rate too low: {success_rate:.2%}"
        assert eps > 50, f"Edit too slow: {eps:.0f}/sec"


class TestGlobAtScale:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("scale", [100, 1000, 10000])
    async def test_glob_py_files(self, large_codebase_dir, scale):
        """Glob **/*.py on N files — measure time.

        Note: glob_files() caps output at 100 results by design.
        We measure how fast it scans the full directory, not how many it returns.
        """
        codebase = large_codebase_dir(scale)

        with timed() as t:
            result = await glob_files("*.py", codebase)

        # glob_files returns "Found N files:\n..." with max 100 entries
        rows = [r for r in result.strip().split("\n") if r.strip()]
        # First line is "Found N files:" header
        found = len(rows) - 1 if rows and rows[0].startswith("Found") else len(rows)

        record_metric("tools", f"glob_{scale}_ms", round(t.elapsed, 1))
        record_metric("tools", f"glob_{scale}_found", found)

        # At 100+ files, glob caps at 100 — verify it returns the max
        expected_min = min(scale, 100) * 0.9
        assert found >= expected_min, f"Expected ~{min(scale, 100)} files, found {found}"


class TestGrepAtScale:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("scale", [100, 1000, 10000])
    async def test_grep_def(self, large_codebase_dir, scale):
        """Grep 'def ' on N files — measure time."""
        codebase = large_codebase_dir(scale)

        with timed() as t:
            result = await grep_files("def ", codebase)

        # Count matches (each file has ~3 def statements)
        rows = [r for r in result.strip().split("\n") if r.strip() and ":" in r]
        matches = len(rows)

        record_metric("tools", f"grep_{scale}_ms", round(t.elapsed, 1))
        record_metric("tools", f"grep_{scale}_matches", matches)

        assert matches > 0, "Grep should find matches"
