from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "docs" / "cli_mock_parity_scenarios.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodeids = [entry["nodeid"] for entry in manifest]

    print("ForgeGod CLI Mock Parity Harness", flush=True)
    print(flush=True)
    for entry in manifest:
        print(f"- {entry['name']}: {entry['description']}", flush=True)
    print(flush=True)

    cmd = [sys.executable, "-m", "pytest", "-q", *nodeids]
    return subprocess.run(cmd, cwd=str(repo_root), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
