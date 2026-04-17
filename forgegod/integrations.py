"""ForgeGod bridge helpers and first-party agent-runtime integration scaffolds."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from forgegod.models import BridgeResponse, BridgeSessionState, BridgeTurn, HiveWorkerResult

_SESSION_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_session_id(session_id: str) -> str:
    """Return a filesystem-safe bridge session id."""
    cleaned = _SESSION_ID_RE.sub("_", session_id.strip())
    return cleaned or "default"


def bridge_sessions_dir(project_dir: Path) -> Path:
    """Return the repo-local directory for bridge session state."""
    return project_dir / "integrations" / "chat_sessions"


def bridge_session_path(project_dir: Path, session_id: str) -> Path:
    """Return the file path for one bridge session."""
    return bridge_sessions_dir(project_dir) / f"{sanitize_session_id(session_id)}.json"


def load_bridge_session(
    project_dir: Path,
    session_id: str,
    *,
    platform: str = "generic",
) -> BridgeSessionState:
    """Load or initialize a bridge session."""
    path = bridge_session_path(project_dir, session_id)
    if not path.exists():
        return BridgeSessionState(session_id=session_id, platform=platform or "generic")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return BridgeSessionState(session_id=session_id, platform=platform or "generic")
    state = BridgeSessionState.model_validate(payload)
    if platform and state.platform == "generic":
        state.platform = platform
    return state


def save_bridge_session(project_dir: Path, state: BridgeSessionState) -> Path:
    """Persist bridge session state to disk."""
    path = bridge_session_path(project_dir, state.session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path


def reset_bridge_session(project_dir: Path, session_id: str) -> bool:
    """Delete a bridge session if present."""
    path = bridge_session_path(project_dir, session_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def _clip(text: str, limit: int = 1200) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def build_bridge_task(
    message: str,
    *,
    session: BridgeSessionState,
    system_prompt: str = "",
    images: list[str] | None = None,
    history_turns: int = 6,
) -> str:
    """Build a coherent ForgeGod task from an external chat message."""
    sections: list[str] = [
        "External agent runtime bridge",
        (
            "You are handling a request that came from an external chat runtime. "
            "Keep the reply coherent with the recent conversation, "
            "but optimize for doing the real repo work."
        ),
        f"Bridge platform: {session.platform}",
        f"Bridge session id: {session.session_id}",
    ]
    if system_prompt.strip():
        sections.append("External runtime system prompt:\n" + system_prompt.strip())
    recent = session.turns[-history_turns:] if history_turns > 0 else []
    if recent:
        transcript = "\n".join(
            f"- {turn.role}: {_clip(turn.content)}"
            for turn in recent
        )
        sections.append("Recent conversation context:\n" + transcript)
    if images:
        sections.append(
            "Attached local file/image paths:\n" + "\n".join(f"- {item}" for item in images)
        )
    sections.append("Latest user request:\n" + message.strip())
    sections.append(
        "If the request implies code changes, do the work. "
        "If the request is ambiguous, ask a short concrete question instead of inventing context."
    )
    return "\n\n".join(sections)


def append_bridge_turns(
    state: BridgeSessionState,
    *,
    user_message: str,
    assistant_message: str,
) -> BridgeSessionState:
    """Append one user/assistant exchange to the session."""
    state.turns.append(BridgeTurn(role="user", content=user_message))
    state.turns.append(BridgeTurn(role="assistant", content=assistant_message))
    state.updated_at = datetime.now(timezone.utc).isoformat()
    return state


def parse_bridge_result(path: Path, *, session_id: str) -> BridgeResponse:
    """Parse ForgeGod's run JSON artifact into a bridge response."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = HiveWorkerResult.model_validate(payload)
    return BridgeResponse(
        session_id=session_id,
        success=result.success,
        exit_code=result.exit_code,
        response=result.output if result.success else (result.error or result.output),
        files_modified=result.files_modified,
        verification_commands=result.verification_commands,
        review_verdict=result.review_verdict,
        error=result.error,
    )


def _write_files(base_dir: Path, files: dict[str, str], *, force: bool) -> list[Path]:
    written: list[Path] = []
    for relative_path, content in files.items():
        target = base_dir / relative_path
        if target.exists() and not force:
            raise FileExistsError(f"{target} already exists. Re-run with --force to overwrite.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def hermes_skill_files() -> dict[str, str]:
    """Return the first-party Hermes skill scaffold."""
    return {
        "forgegod-bridge/SKILL.md": """---
name: forgegod-bridge
description: Delegate repo coding tasks to the ForgeGod bridge.
version: 1.0.0
author: ForgeGod
license: Apache-2.0
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [coding, forgegod, bridge]
    requires_tools: [terminal]
---

# ForgeGod Bridge

Use this skill when the user explicitly wants repo coding or audit work routed through ForgeGod.

## Rules

- Use the helper script instead of hand-writing the shell invocation.
- Pass the full user request with `--message`.
- Default to `--session-id hermes-default` unless the operator gives you a stronger stable id.
- Keep `--research` enabled for code-changing work and troubleshooting.
- Add `--subagents` when the task benefits from parallel read-only analysis before coding.
- Return ForgeGod's final response plus any modified files or blockers.

## Command

```bash
python scripts/forgegod_bridge.py --message "Add a /health endpoint with tests"
```
""",
        "forgegod-bridge/scripts/forgegod_bridge.py": """from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ForgeGod bridge chat from Hermes.")
    parser.add_argument("--message", required=True)
    parser.add_argument("--session-id", default="hermes-default")
    parser.add_argument("--model", default="")
    parser.add_argument("--subagents", action="store_true")
    args = parser.parse_args()

    command = [
        "forgegod",
        "bridge",
        "chat",
        "--runtime",
        "hermes",
        "--session-id",
        args.session_id,
        "--format",
        "text",
    ]
    if args.model:
        command.extend(["--model", args.model])
    if args.subagents:
        command.append("--subagents")
    command.append(args.message)

    result = subprocess.run(command, text=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
    }


def openclaw_skill_files() -> dict[str, str]:
    """Return the first-party OpenClaw skill scaffold."""
    return {
        "forgegod-bridge/SKILL.md": """---
name: forgegod_bridge
description: Route repo coding tasks through ForgeGod's research-first bridge.
metadata:
  openclaw:
    requires.bins: ["forgegod", "python"]
---

# ForgeGod Bridge

Use this skill when the user explicitly wants a coding, audit, planning,
or repo-hardening task delegated to ForgeGod.

## Rules

- Use the helper script instead of composing raw `exec` commands.
- Pass the user's request via `--message`.
- Default to `--session-id openclaw-default` unless the operator gives you a stronger stable id.
- Keep research enabled for coding and troubleshooting tasks.
- Use `--subagents` when the work benefits from read-only parallel analysis before implementation.
- Summarize ForgeGod's final answer instead of dumping raw shell noise.

## Command

```bash
python scripts/forgegod_bridge.py --message "Audit this repo and fix the failing tests"
```
""",
        "forgegod-bridge/scripts/forgegod_bridge.py": """from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ForgeGod bridge chat from OpenClaw.")
    parser.add_argument("--message", required=True)
    parser.add_argument("--session-id", default="openclaw-default")
    parser.add_argument("--model", default="")
    parser.add_argument("--subagents", action="store_true")
    args = parser.parse_args()

    command = [
        "forgegod",
        "bridge",
        "chat",
        "--runtime",
        "openclaw",
        "--session-id",
        args.session_id,
        "--format",
        "text",
    ]
    if args.model:
        command.extend(["--model", args.model])
    if args.subagents:
        command.append("--subagents")
    command.append(args.message)

    result = subprocess.run(command, text=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
    }


def openclaw_cli_backend_config() -> str:
    """Return a safe starter config for running ForgeGod as an OpenClaw CLI backend."""
    payload = {
        "agents": {
            "defaults": {
                "cliBackends": {
                    "forgegod-cli": {
                        "command": "forgegod",
                        "args": ["bridge", "chat", "--runtime", "openclaw", "--format", "json"],
                        "output": "json",
                        "input": "arg",
                        "modelArg": "--model",
                        "sessionArg": "--session-id",
                        "sessionMode": "always",
                        "sessionIdFields": ["session_id"],
                        "systemPromptArg": "--system-prompt",
                        "imageArg": "--image",
                        "imageMode": "repeat",
                        "serialize": True,
                    }
                }
            }
        }
    }
    return json.dumps(payload, indent=2) + "\n"


def scaffold_hermes_skill(output_dir: Path, *, force: bool = False) -> list[Path]:
    """Write the Hermes skill scaffold."""
    return _write_files(output_dir, hermes_skill_files(), force=force)


def scaffold_openclaw_skill(output_dir: Path, *, force: bool = False) -> list[Path]:
    """Write the OpenClaw skill scaffold."""
    return _write_files(output_dir, openclaw_skill_files(), force=force)


def scaffold_openclaw_backend(output_file: Path, *, force: bool = False) -> Path:
    """Write the OpenClaw CLI backend config scaffold."""
    if output_file.exists() and not force:
        raise FileExistsError(f"{output_file} already exists. Re-run with --force to overwrite.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(openclaw_cli_backend_config(), encoding="utf-8")
    return output_file
