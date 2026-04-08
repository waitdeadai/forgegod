from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "mock_parity_scenarios.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenarios = data.get("scenarios", [])
    if not scenarios:
        print("No parity scenarios configured.")
        return 1

    print("ForgeGod Mock Parity Harness")
    print(f"Manifest: {MANIFEST}")
    print(f"Scenarios: {len(scenarios)}")
    for scenario in scenarios:
        print(f"- {scenario['id']}: {scenario['description']}")

    nodeids = [scenario["nodeid"] for scenario in scenarios]
    cmd = [sys.executable, "-m", "pytest", "-q", *nodeids]
    print("\nRunning:")
    print(" ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
