# ForgeGod Stress Test & Benchmark Results

**Date:** 2026-04-05  
**Version:** 0.1.0  
**System:** Windows 11 / Python 3.13.5 / 8 cores / 32GB RAM  
**Status:** 34 tests, all passing

## Methodology

- All tests run offline with mocked LLM responses (throughput measures engine overhead, not model inference)
- Timing: `time.perf_counter()` high-resolution clock, reported as p50/p95/p99
- Seeded randomness (`random.Random(42)`) for reproducibility
- SQLite write tests measure real I/O including fsync
- Security scan tests use balanced datasets (50% clean, 50% malicious)

## Router Performance

| Metric | Value |
|:-------|------:|
| Sequential throughput (mocked HTTP) | 2.7 calls/sec |
| Per-call latency p50 | 369 ms |
| Per-call latency p95 | 432 ms |
| Per-call latency p99 | 472 ms |
| Circuit breaker open latency | 0.12 ms |
| Circuit breaker recovery | <150 ms |
| Fallback chain exhaustion | 0.39 ms |
| Cost calculation (10K calls) | 11.6 ms |
| Cost calculations/sec | 865,464 |

> Note: Router throughput includes full `httpx.AsyncClient` creation per call. Real-world calls are bottlenecked by LLM inference (seconds), not routing overhead (milliseconds).

## Memory Performance

| Scale | Recall p50 | Recall p95 | Recall p99 |
|:------|:----------:|:----------:|:----------:|
| 100 entries | 12 ms | 15 ms | 15 ms |
| 1,000 entries | 20 ms | 29 ms | 29 ms |
| 10,000 entries | 133 ms | 186 ms | 186 ms |

| Metric | Value |
|:-------|------:|
| Episodic write throughput | 35 writes/sec |
| DB size (1K episodes) | 412 KB |
| Concurrent read/write errors | 0 |
| Consolidation (200 memories) | 8.6 ms |
| Decay (10K memories) | 241 ms |
| Entity extraction | 42,251/sec |

## Budget Tracker

| Metric | Value |
|:-------|------:|
| SQLite writes/sec | 199 |
| Mode transition accuracy | 100% |
| Float precision (10K records) | 0.0 drift |
| Model breakdown query (15 models) | 2.5 ms |

## Security Scanner

| Metric | Value |
|:-------|------:|
| Injection scans/sec | 72,014 |
| Injection detection rate | 100% |
| Injection false positives | 0 |
| Code validations/sec | 243,345 |
| Code detection rate | 100% |
| Canary token checks/sec | 258,184 |
| Canary accuracy | 100% |
| Secret redaction throughput | 58.8 MB/sec |

## Tool I/O

| Operation | Throughput |
|:----------|:---------:|
| File read (1KB) | 793/sec |
| File read (10KB) | 109/sec |
| File read (100KB) | 113/sec |
| File write | 1,416/sec |
| File edit | 496/sec (100% success) |
| Glob (100 files) | 3.6 ms |
| Glob (1K files) | 6.3 ms |
| Glob (10K files) | 53 ms |
| Grep (100 files) | 17 ms |
| Grep (1K files) | 23 ms |
| Grep (10K files) | 19 ms |

## Reliability

| Metric | Result |
|:-------|:------:|
| Circuit breaker recovery | <150 ms |
| Fallback chain graceful degradation | 100% |
| Budget enforcement accuracy | 100% |
| Multi-provider isolation | 100% |
| Concurrent memory read/write safety | 0 errors |
| Security detection accuracy | 100% |

## How to Run

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Full stress suite
python -m pytest tests/stress/ -v -m stress

# Single component
python -m pytest tests/stress/test_stress_memory.py -v -m stress

# With JSON report
python scripts/run_stress_tests.py --output stress_results.json

# With Markdown tables
python scripts/run_stress_tests.py --markdown
```

*Last updated: 2026-04-05. Run `python scripts/run_stress_tests.py` to regenerate.*
