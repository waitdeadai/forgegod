"""Deterministic OpenAI-compatible mock service for CLI parity harnesses."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScriptedResponse:
    kind: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


TERMINAL_RESPONSE = ScriptedResponse(
    kind="text",
    content=(
        "The task cannot be completed under the current constraints. "
        "No further action is possible. Permission denied."
    ),
)


@dataclass(frozen=True)
class MockScenario:
    name: str
    description: str
    task: str
    permission_mode: str
    responses: tuple[ScriptedResponse, ...]
    terminal_response: ScriptedResponse = TERMINAL_RESPONSE


SCENARIOS: dict[str, MockScenario] = {
    "cli_read_file_roundtrip": MockScenario(
        name="cli_read_file_roundtrip",
        description="CLI run reads a file through the real OpenAI-compatible tool path.",
        task="Explain the contents of hello.txt",
        permission_mode="read-only",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_read_1",
                        "name": "read_file",
                        "arguments": {"path": "hello.txt"},
                    }
                ],
            ),
            ScriptedResponse(kind="text", content="The file says hello forgegod."),
        ),
    ),
    "cli_write_file_allowed": MockScenario(
        name="cli_write_file_allowed",
        description="CLI run writes a workspace file, reviews the diff, and completes.",
        task="Create notes.txt with the line hello forgegod",
        permission_mode="workspace-write",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_write_1",
                        "name": "write_file",
                        "arguments": {"path": "notes.txt", "content": "hello forgegod\n"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_diff_1",
                        "name": "git_diff",
                        "arguments": {},
                    }
                ],
            ),
            ScriptedResponse(kind="text", content="Created notes.txt successfully."),
        ),
    ),
    "cli_write_file_denied": MockScenario(
        name="cli_write_file_denied",
        description="CLI run attempts a forbidden write in read-only mode and surfaces the denial.",
        task="Create blocked.txt with the line denied",
        permission_mode="read-only",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_blocked_1",
                        "name": "write_file",
                        "arguments": {"path": "blocked.txt", "content": "denied\n"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="text",
                content=(
                    "ForgeGod blocked tool 'write_file': permission denied in read-only mode. "
                    "The file 'blocked.txt' cannot be created because write operations are not "
                    "permitted in the current permission mode. Task cannot proceed."
                ),
            ),
        ),
    ),
    "cli_completion_gate_roundtrip": MockScenario(
        name="cli_completion_gate_roundtrip",
        description="CLI run edits, verifies, completes (bash waives git_diff).",
        task="Implement src/app.py so it prints forgegod",
        permission_mode="workspace-write",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_code_1",
                        "name": "write_file",
                        "arguments": {"path": "src/app.py", "content": "print('forgegod')\n"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_verify_1",
                        "name": "bash",
                        "arguments": {"command": "python -m pytest --version"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="text",
                content="Implemented src/app.py and verified the change.",
            ),
        ),
    ),
    "cli_loop_story_success": MockScenario(
        name="cli_loop_story_success",
        description=(
            "CLI loop completes one story through write and verify "
            "(auto-closes after bash verification, no git_diff required)."
        ),
        task="Loop story: create src/app.py",
        permission_mode="workspace-write",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_loop_write_1",
                        "name": "write_file",
                        "arguments": {"path": "src/app.py", "content": "print('forgegod loop')\n"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_loop_verify_1",
                        "name": "bash",
                        "arguments": {"command": "python -m pytest --version"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="text",
                content="Implemented src/app.py with verification complete.",
            ),
        ),
    ),
    "cli_loop_story_denied": MockScenario(
        name="cli_loop_story_denied",
        description=(
            "CLI loop blocks a forbidden write, marks the story blocked, "
            "and exits cleanly."
        ),
        task="Loop story: blocked write",
        permission_mode="read-only",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_loop_blocked_1",
                        "name": "write_file",
                        "arguments": {"path": "blocked.txt", "content": "denied\n"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="text",
                content=(
                    "ForgeGod blocked tool 'write_file': permission denied in read-only mode. "
                    "The story cannot be completed because write operations are blocked. "
                    "Mark this story as blocked and exit cleanly."
                ),
            ),
        ),
    ),
    "cli_strict_bash_roundtrip": MockScenario(
        name="cli_strict_bash_roundtrip",
        description=(
            "CLI run executes an allowed strict-mode bash command through the "
            "real sandbox interface."
        ),
        task="Run python --version and report it.",
        permission_mode="read-only",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_strict_bash_1",
                        "name": "bash",
                        "arguments": {"command": "python --version"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="text",
                content="Strict sandbox reported Python 3.13.5.",
            ),
        ),
    ),
    "cli_strict_backend_blocked": MockScenario(
        name="cli_strict_backend_blocked",
        description=(
            "CLI run surfaces a strict sandbox backend failure back through "
            "the model and CLI."
        ),
        task="Check whether strict sandbox execution is available.",
        permission_mode="read-only",
        responses=(
            ScriptedResponse(
                kind="tool_calls",
                tool_calls=[
                    {
                        "id": "call_strict_blocked_1",
                        "name": "bash",
                        "arguments": {"command": "python --version"},
                    }
                ],
            ),
            ScriptedResponse(
                kind="text",
                content="Strict sandbox execution is blocked because the backend is unavailable.",
            ),
        ),
    ),
}


class MockOpenAIService(ThreadingHTTPServer):
    """Threaded HTTP server that replays scripted chat completion responses."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        scenario: MockScenario,
        request_log_path: Path | None = None,
    ) -> None:
        super().__init__(server_address, _MockOpenAIHandler)
        self.scenario = scenario
        self.request_log_path = request_log_path
        self.requests: list[dict[str, Any]] = []
        self._response_index = 0
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}/v1"

    def next_response(self) -> ScriptedResponse:
        with self._lock:
            if self._response_index >= len(self.scenario.responses):
                return self.scenario.terminal_response
            response = self.scenario.responses[self._response_index]
            self._response_index += 1
            return response

    def record_request(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["_captured_at"] = round(time.time(), 3)
        payload["_scenario"] = self.scenario.name
        self.requests.append(payload)
        if self.request_log_path:
            self.request_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.request_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) + "\n")


class _MockOpenAIHandler(BaseHTTPRequestHandler):
    server: MockOpenAIService

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.endswith("/chat/completions"):
            self._write_json(404, {"error": {"message": f"Unhandled path: {self.path}"}})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
            self.server.record_request(payload)
            response = self.server.next_response()
        except Exception as exc:  # pragma: no cover - fatal server path
            self._write_json(500, {"error": {"message": str(exc)}})
            return

        model = payload.get("model", "mock-model")
        self._write_json(200, _render_chat_completion(model, response))

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _render_chat_completion(model: str, scripted: ScriptedResponse) -> dict[str, Any]:
    if scripted.kind == "tool_calls":
        tool_calls = []
        for i, call in enumerate(scripted.tool_calls or []):
            tool_calls.append(
                {
                    "id": call.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("arguments", {})),
                    },
                }
            )
        message = {"role": "assistant", "content": None, "tool_calls": tool_calls}
        finish_reason = "tool_calls"
        completion_tokens = 12
    else:
        message = {"role": "assistant", "content": scripted.content or ""}
        finish_reason = "stop"
        completion_tokens = max(4, len((scripted.content or "").split()))

    return {
        "id": "chatcmpl-forgegod-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 24,
            "completion_tokens": completion_tokens,
            "total_tokens": 24 + completion_tokens,
        },
    }


@dataclass(frozen=True)
class StartedMockServer:
    server: MockOpenAIService
    thread: threading.Thread

    @property
    def base_url(self) -> str:
        return self.server.base_url

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def start_mock_openai_server(
    scenario_name: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    request_log_path: Path | None = None,
) -> StartedMockServer:
    """Start a deterministic OpenAI-compatible mock service for a scenario."""
    if scenario_name not in SCENARIOS:
        raise KeyError(f"Unknown mock scenario: {scenario_name}")
    server = MockOpenAIService((host, port), SCENARIOS[scenario_name], request_log_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return StartedMockServer(server=server, thread=thread)
