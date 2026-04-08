from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from forgegod.testing.mock_openai_service import SCENARIOS, start_mock_openai_server


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic OpenAI-compatible mock service for ForgeGod parity tests."
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        required=True,
        help="Scripted scenario to replay",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=0, help="Bind port (0 = auto)")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Optional JSONL request capture path",
    )
    args = parser.parse_args()

    started = start_mock_openai_server(
        args.scenario,
        host=args.host,
        port=args.port,
        request_log_path=args.log,
    )
    scenario = SCENARIOS[args.scenario]
    print(f"MOCK_OPENAI_BASE_URL={started.base_url}", flush=True)
    print(f"MOCK_SCENARIO={scenario.name}", flush=True)
    print(f"MOCK_DESCRIPTION={scenario.description}", flush=True)

    def _stop(_signum, _frame):
        started.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        while True:
            time.sleep(0.25)
    finally:
        started.stop()


if __name__ == "__main__":
    raise SystemExit(main())
