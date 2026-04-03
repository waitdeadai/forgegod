"""ForgeGod Agent — core agentic loop with tool execution and context management.

The agent is the heart of ForgeGod: it takes a task, builds a message chain,
calls the LLM, parses tool calls, executes them, appends results, and repeats
until the LLM signals completion (no tool calls) or limits are hit.

Context compression kicks in at configurable % to keep running indefinitely.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path

from forgegod.budget import BudgetTracker
from forgegod.config import ForgeGodConfig
from forgegod.models import AgentResult, BudgetMode, ModelUsage, ToolCall, ToolResult
from forgegod.router import ModelRouter
from forgegod.tools import execute_tool, get_tool_defs, load_all_tools

logger = logging.getLogger("forgegod.agent")

# System prompt — engineered from SWE-bench top-scoring agent patterns:
# 1. Structured problem-solving workflow (understand → locate → plan → implement → verify)
# 2. Repo map orientation before any edits
# 3. Test-first verification loop
# 4. Error recovery with strategy rotation
# 5. Explicit anti-patterns to avoid common failure modes
SYSTEM_PROMPT = """You are ForgeGod, an autonomous coding agent that solves software engineering tasks.

## Workflow — SDLC State Machine (advance gates in ORDER)
1. **ORIENT** — Call `repo_map` to understand the codebase. Call `git_status` for current state.
2. **LOCATE** — Use `grep` and `glob` to find exact files and functions relevant to your task.
3. **READ** — Read the specific files you'll modify. Never edit what you haven't read.
4. **PLAN** — Think through your approach. Consider edge cases. Check for existing tests.
5. **IMPLEMENT** — Make changes using `edit_file` (prefer over `write_file`). Small, focused edits.
6. **VERIFY** — Run tests with `bash`. Check syntax/types. Run `git_diff` to review changes.
7. **COMMIT** — Once verified, commit with a clear message describing the change.

Gate rule: Do NOT advance to IMPLEMENT until PLAN is solid. Do NOT advance to COMMIT until VERIFY passes.

## Tools
- `repo_map(path)` — Codebase overview (file tree + signatures). **Use FIRST.**
- `read_file(path)` — Read file with line numbers
- `edit_file(path, old_string, new_string)` — Replace unique string. Preferred for modifications.
- `write_file(path, content)` — Write/create file. New files only.
- `glob(pattern)` — Find files by pattern
- `grep(pattern)` — Search file contents with regex
- `bash(command)` — Shell commands (tests, build, lint)
- `git_status()`, `git_diff()`, `git_commit(message)` — Git operations
- `mcp_connect/mcp_call` — External MCP tool servers
- `list_skills()`, `load_skill(name)` — Load task-specific skill instructions

## Critical Rules
- **Read before edit**: NEVER modify a file you haven't read in this session.
- **Verify changes**: ALWAYS run tests after modifications if a test suite exists.
- **One thing at a time**: Make one logical change, verify it, then move to the next.
- **Existing code wins**: Edit existing files rather than creating new ones.
- **No speculation**: Unsure about behavior? Read the code. Don't guess.
- **Forced reflection**: If an approach fails twice, answer: (1) What specifically failed? (2) What concrete change fixes it? (3) Is this truly a new approach?
- **Minimal changes**: Don't refactor code you weren't asked to change.
- **Escalate when stuck**: If genuinely blocked, explain what's blocking you.

## Anti-Patterns (AVOID)
- Editing without reading → broken code
- Same failing command 3x → gutter, change approach fundamentally
- write_file when edit_file works → wasteful, error-prone
- Error handling for impossible cases → trust the codebase
- Changing test assertions → fix the code, not the test
- Codebase overviews in your response → keep agent output concise, not narrated

## Context
Working directory: {cwd}
"""


class Agent:
    """Core agent loop — LLM + tools + context management."""

    def __init__(
        self,
        config: ForgeGodConfig,
        router: ModelRouter | None = None,
        budget: BudgetTracker | None = None,
        role: str = "coder",
        system_prompt: str = "",
        max_turns: int = 200,
        max_tool_calls: int = 1000,
    ):
        self.config = config
        self.router = router or ModelRouter(config)
        self.budget = budget or BudgetTracker(config)
        self.role = role
        self.max_turns = max_turns
        self.max_tool_calls = max_tool_calls

        # Build system prompt with environment detection + project rules + skills
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            env_info = self._detect_environment()
            rules = self._load_project_rules()
            skills_summary = self._load_skills_summary()
            self.system_prompt = (
                SYSTEM_PROMPT.format(cwd=Path.cwd())
                + env_info + rules + skills_summary
            )

        # State
        self.messages: list[dict] = []
        self.total_usage = ModelUsage()
        self.tool_calls_count = 0
        self.files_modified: list[str] = []
        self._turn = 0
        self._gutter_tracker: dict[str, int] = {}  # action_hash → repeat count

        # Load tools
        load_all_tools()
        self._tool_defs = get_tool_defs()

    async def run(self, task: str) -> AgentResult:
        """Execute a task through the agent loop.

        The loop:
        1. Send messages + tools to LLM
        2. Parse response for tool calls
        3. If no tool calls → done (LLM gave final answer)
        4. Execute each tool call
        5. Append results to messages
        6. Check context size → compress if needed
        7. Check budget → halt if exceeded
        8. Repeat
        """
        start = time.time()

        # Initialize message chain
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        try:
            while self._turn < self.max_turns:
                self._turn += 1
                await self._run_hooks("pre_turn", {"turn": self._turn})

                # Budget check
                effective_mode = self.budget.check_budget()
                if effective_mode == BudgetMode.HALT:
                    logger.warning("Budget HALT — stopping agent")
                    return self._build_result(
                        success=False,
                        output="[Budget limit reached. Agent halted.]",
                        elapsed=time.time() - start,
                    )

                # Call LLM
                response_text, usage = await self.router.call(
                    prompt=self.messages,
                    role=self.role,
                    tools=self._tool_defs,
                    max_tokens=4096,
                    temperature=0.3,
                )
                self._accumulate_usage(usage)
                self.budget.record(usage, role=self.role)

                # Strip <think> tags from reasoning models (Hermes/Qwen pattern)
                response_text = re.sub(
                    r"<think>.*?</think>", "", response_text, flags=re.DOTALL
                ).strip()

                # Parse tool calls from response
                tool_calls = self._parse_tool_calls(response_text)

                if not tool_calls:
                    # No tool calls → agent is done
                    logger.info(f"Agent done after {self._turn} turns, {self.tool_calls_count} tool calls")
                    await self._run_hooks("on_complete", {
                        "turns": self._turn,
                        "tool_calls": self.tool_calls_count,
                        "files": self.files_modified,
                    })
                    return self._build_result(
                        success=True,
                        output=response_text,
                        elapsed=time.time() - start,
                    )

                # Add assistant message
                self.messages.append({
                    "role": "assistant",
                    "content": response_text,
                })

                # Execute tool calls — parallel for read-only, sequential for writes
                results = await self._execute_tool_batch(tool_calls)

                for tc, result in zip(tool_calls, results):
                    self.tool_calls_count += 1

                    # Track file modifications
                    if tc.name in ("write_file", "edit_file") and not result.error:
                        path = tc.arguments.get("path", "")
                        if path and path not in self.files_modified:
                            self.files_modified.append(path)

                    # Append tool result to messages
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result.content,
                    })

                    # Gutter detection with forced structured reflection (SOTA pattern)
                    if self._detect_gutter(tc, result):
                        logger.warning(f"Gutter detected: {tc.name} repeated 3x with same args")
                        self.messages.append({
                            "role": "user",
                            "content": (
                                "[FORCED REFLECTION — GUTTER DETECTED]\n"
                                "You've repeated the same action 3+ times with the same result.\n"
                                "Before your next action, answer these 3 questions:\n"
                                "1. **What specifically failed?** (exact error or symptom)\n"
                                "2. **What specific change would fix it?** (not 'try harder')\n"
                                "3. **Am I repeating the same approach?** (if yes, what's fundamentally different now?)\n\n"
                                "If you cannot answer #3 with a genuinely new approach, "
                                "STOP and explain what's blocking you."
                            ),
                        })

                await self._run_hooks("post_turn", {"turn": self._turn})

                # Context management: prune bloated results, then compress if needed
                self._prune_tool_results()
                self._maybe_compress_context()

            # Max turns reached
            return self._build_result(
                success=False,
                output=f"[Max turns ({self.max_turns}) reached]",
                elapsed=time.time() - start,
            )

        except Exception as e:
            logger.exception(f"Agent error: {e}")
            return self._build_result(
                success=False,
                output="",
                elapsed=time.time() - start,
                error=str(e),
            )

    def _parse_tool_calls(self, response: str) -> list[ToolCall]:
        """Parse tool calls from LLM response.

        Handles:
        1. OpenAI-style: JSON with {"tool_calls": [...]}
        2. Hermes-style: <tool_call>{"name": ..., "arguments": ...}</tool_call>
        3. Raw function call JSON blocks
        """
        tool_calls: list[ToolCall] = []

        # 1. Try OpenAI tool_calls format
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "tool_calls" in data:
                for tc in data["tool_calls"]:
                    args = tc.get("arguments", {})
                    if isinstance(args, str):
                        args = json.loads(args)
                    tool_calls.append(ToolCall(
                        id=tc.get("id", f"call_{self.tool_calls_count}"),
                        name=tc["name"],
                        arguments=args,
                    ))
                return tool_calls
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # 2. Try Hermes <tool_call> XML format (Teknium/NousResearch convention)
        hermes_pattern = re.compile(
            r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL
        )
        hermes_matches = hermes_pattern.findall(response)
        if hermes_matches:
            for i, match in enumerate(hermes_matches):
                try:
                    data = json.loads(match)
                    args = data.get("arguments", data.get("parameters", {}))
                    if isinstance(args, str):
                        args = json.loads(args)
                    tool_calls.append(ToolCall(
                        id=f"hermes_{self.tool_calls_count}_{i}",
                        name=data["name"],
                        arguments=args,
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue
            if tool_calls:
                return tool_calls

        # 3. Try individual function call JSON blocks
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                args = data["arguments"]
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(ToolCall(
                    id=f"call_{self.tool_calls_count}",
                    name=data["name"],
                    arguments=args,
                ))
                return tool_calls
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        return tool_calls

    # Read-only tools safe for parallel execution
    _READONLY_TOOLS = {
        "read_file", "glob", "grep", "repo_map", "git_status",
        "git_diff", "git_log", "mcp_list",
    }

    async def _execute_tool_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute tool calls — parallel for read-only, sequential for writes.

        Read-only tools (read_file, grep, glob, repo_map, git_status, git_diff)
        run concurrently. Write tools (edit_file, write_file, bash, git_commit)
        run sequentially to prevent race conditions.
        """
        if not tool_calls:
            return []

        # Check if ALL tools are read-only → fully parallel
        all_readonly = all(tc.name in self._READONLY_TOOLS for tc in tool_calls)
        if all_readonly and len(tool_calls) > 1:
            logger.debug(f"Parallel execution: {len(tool_calls)} read-only tools")
            return await asyncio.gather(
                *(self._execute_tool_call(tc) for tc in tool_calls)
            )

        # Mixed or write-only → sequential
        results = []
        for tc in tool_calls:
            results.append(await self._execute_tool_call(tc))
        return results

    async def _execute_tool_call(self, tc: ToolCall) -> ToolResult:
        """Execute a single tool call with two-stage validation (Hermes pattern).

        Stage 1: Validate tool name exists and arguments match schema
        Stage 2: Execute the tool
        This catches malformed calls before execution, providing better error feedback.
        """
        logger.debug(f"Executing tool: {tc.name}({list(tc.arguments.keys())})")

        # Stage 1: Validate tool exists
        from forgegod.tools import _TOOLS
        if tc.name not in _TOOLS:
            return ToolResult(
                tool_call_id=tc.id,
                name=tc.name,
                content=f"Error: Unknown tool '{tc.name}'. Available: {', '.join(sorted(_TOOLS.keys()))}",
                error=True,
            )

        # Stage 1b: Validate required arguments
        tool_def, _ = _TOOLS[tc.name]
        required = tool_def.parameters.get("required", [])
        missing = [r for r in required if r not in tc.arguments]
        if missing:
            return ToolResult(
                tool_call_id=tc.id,
                name=tc.name,
                content=f"Error: Missing required arguments for {tc.name}: {', '.join(missing)}",
                error=True,
            )

        # Stage 2: Execute
        try:
            result = await execute_tool(tc.name, tc.arguments)
            is_error = result.startswith("Error")
            return ToolResult(
                tool_call_id=tc.id,
                name=tc.name,
                content=result,
                error=is_error,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tc.id,
                name=tc.name,
                content=f"Error: {e}",
                error=True,
            )

    async def spawn_subagent(
        self,
        task: str,
        role: str = "coder",
        max_turns: int = 50,
    ) -> AgentResult:
        """Spawn a sub-agent as a context firewall (OpenClaw pattern).

        The sub-agent gets its own fresh context window. The parent only
        sees the condensed result, not the intermediate tool calls.
        This prevents context rot and keeps the parent's context clean.

        Uses a cheaper model role by default (coder vs sentinel).
        """
        subagent = Agent(
            config=self.config,
            router=self.router,
            budget=self.budget,
            role=role,
            max_turns=max_turns,
        )
        result = await subagent.run(task)

        # Accumulate sub-agent usage into parent
        self._accumulate_usage(subagent.total_usage)
        self.files_modified.extend(
            f for f in subagent.files_modified if f not in self.files_modified
        )
        return result

    def _prune_tool_results(self):
        """Prune bloated tool results without rewriting the transcript.

        OpenClaw's 3-tier persistence: history → compaction → pruning.
        Pruning trims large tool results in-place, keeping the tool call
        record but reducing content to a summary.
        """
        MAX_TOOL_RESULT_CHARS = 8000
        for msg in self.messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > MAX_TOOL_RESULT_CHARS:
                    # Keep first and last portions
                    head = content[:3000]
                    tail = content[-1000:]
                    trimmed = len(content) - 4000
                    msg["content"] = (
                        f"{head}\n\n[... {trimmed} chars pruned ...]\n\n{tail}"
                    )

    async def _run_hooks(self, event: str, context: dict | None = None):
        """Run lifecycle hooks — user-defined scripts at agent events.

        Hook files are shell scripts at .forgegod/hooks/{event}.sh
        They run silently on success, surface errors only.

        Events: pre_tool, post_tool, pre_turn, post_turn, on_error, on_complete
        """
        hook_dir = Path.cwd() / ".forgegod" / "hooks"
        hook_file = hook_dir / f"{event}.sh"
        if not hook_file.exists():
            return

        try:
            env_vars = {"FORGEGOD_EVENT": event}
            if context:
                env_vars["FORGEGOD_CONTEXT"] = json.dumps(context)[:4000]

            proc = await asyncio.create_subprocess_exec(
                "bash", str(hook_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**__import__("os").environ, **env_vars},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=30
            )
            if proc.returncode != 0:
                logger.warning(
                    f"Hook {event} failed (rc={proc.returncode}): "
                    f"{stderr.decode('utf-8', errors='replace')[:500]}"
                )
        except asyncio.TimeoutError:
            logger.warning(f"Hook {event} timed out after 30s")
        except Exception as e:
            logger.debug(f"Hook {event} error: {e}")

    def _detect_gutter(self, tc: ToolCall, result: ToolResult) -> bool:
        """Detect when agent is stuck in a loop (gutter).

        Returns True if the same tool+args combo has been seen 3+ times.
        """
        if not self.config.loop.gutter_detection:
            return False

        # Hash the tool call
        key = f"{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}"
        self._gutter_tracker[key] = self._gutter_tracker.get(key, 0) + 1
        return self._gutter_tracker[key] >= self.config.loop.gutter_threshold

    def _maybe_compress_context(self):
        """Compress context if it's getting too large.

        Strategy: Keep system prompt + first user message + last N messages.
        Summarize everything in between into a single "context summary" message.
        """
        # Estimate context size by character count (rough proxy for tokens)
        total_chars = sum(len(m.get("content", "")) for m in self.messages)
        # Rough: 4 chars ≈ 1 token, most models have 128K context
        estimated_tokens = total_chars / 4
        max_tokens = getattr(self.config.loop, "max_context_tokens", 100_000)

        threshold = max_tokens * (self.config.loop.context_rotation_pct / 100)
        if estimated_tokens < threshold:
            return

        logger.info(f"Compressing context: ~{int(estimated_tokens)} tokens → trimming")

        # Keep: system (0), first user (1), last 20 messages
        keep_last = 20
        if len(self.messages) <= keep_last + 2:
            return

        system = self.messages[0]
        first_user = self.messages[1]
        recent = self.messages[-keep_last:]

        # Build summary of dropped messages
        dropped = self.messages[2:-keep_last]
        tool_calls_summary = []
        for m in dropped:
            if m.get("role") == "tool":
                name = m.get("name", "unknown")
                content_preview = m.get("content", "")[:100]
                tool_calls_summary.append(f"  - {name}: {content_preview}")

        summary_text = (
            f"[Context compressed — {len(dropped)} messages summarized]\n"
            f"Tools executed: {len(tool_calls_summary)}\n"
        )
        if tool_calls_summary:
            summary_text += "\n".join(tool_calls_summary[:10])
            if len(tool_calls_summary) > 10:
                summary_text += f"\n  ... and {len(tool_calls_summary) - 10} more"

        self.messages = [
            system,
            first_user,
            {"role": "user", "content": summary_text},
            *recent,
        ]

        new_chars = sum(len(m.get("content", "")) for m in self.messages)
        logger.info(f"Context compressed: {total_chars} → {new_chars} chars")

    def _accumulate_usage(self, usage: ModelUsage):
        """Add usage from a single call to running totals."""
        self.total_usage.input_tokens += usage.input_tokens
        self.total_usage.output_tokens += usage.output_tokens
        self.total_usage.cost_usd += usage.cost_usd
        self.total_usage.model = usage.model
        self.total_usage.provider = usage.provider

    def _build_result(
        self, success: bool, output: str, elapsed: float, error: str = ""
    ) -> AgentResult:
        """Build the final AgentResult."""
        self.total_usage.elapsed_s = round(elapsed, 2)
        return AgentResult(
            success=success,
            output=output,
            files_modified=self.files_modified,
            tool_calls_count=self.tool_calls_count,
            total_usage=self.total_usage,
            error=error,
        )

    @property
    def context_size_estimate(self) -> int:
        """Rough token estimate of current context."""
        return sum(len(m.get("content", "")) for m in self.messages) // 4

    @staticmethod
    def _detect_environment() -> str:
        """Detect project environment: language, test framework, package manager."""
        cwd = Path.cwd()
        info: list[str] = ["\n## Detected Environment"]

        # Python
        if (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
            info.append("Language: Python")
            if (cwd / "pyproject.toml").exists():
                try:
                    content = (cwd / "pyproject.toml").read_text()
                    if "pytest" in content:
                        info.append("Test runner: `pytest`")
                    if "ruff" in content:
                        info.append("Linter: `ruff check .`")
                except OSError:
                    pass
            if any(cwd.rglob("test_*.py")):
                info.append("Tests exist: yes (run with `pytest`)")

        # JavaScript/TypeScript
        elif (cwd / "package.json").exists():
            info.append("Language: JavaScript/TypeScript")
            try:
                import json as _json
                pkg = _json.loads((cwd / "package.json").read_text())
                scripts = pkg.get("scripts", {})
                if "test" in scripts:
                    info.append(f"Test runner: `npm test` ({scripts['test']})")
                if "lint" in scripts:
                    info.append(f"Linter: `npm run lint`")
            except (OSError, ValueError):
                pass

        # Go
        elif (cwd / "go.mod").exists():
            info.append("Language: Go")
            info.append("Test runner: `go test ./...`")

        # Rust
        elif (cwd / "Cargo.toml").exists():
            info.append("Language: Rust")
            info.append("Test runner: `cargo test`")

        # Git info
        if (cwd / ".git").exists():
            info.append("Git: initialized")

        return "\n".join(info) if len(info) > 1 else ""

    @staticmethod
    def _load_skills_summary() -> str:
        """Load compact skills list for system prompt (OpenClaw pattern).

        Only injects name + one-line description. Full content is loaded
        on-demand via the load_skill() tool, saving context.
        """
        try:
            from forgegod.tools.skills import get_skills_summary
            return get_skills_summary()
        except ImportError:
            return ""

    @staticmethod
    def _load_project_rules(max_chars: int = 10_000) -> str:
        """Load project-specific rules from .forgegod/rules.md.

        Security: Rules files are injected into the system prompt, making them
        a prompt injection vector in cloned repos. Mitigations:
        1. Cap content size (default 10K chars) to limit injection surface
        2. Strip obvious injection patterns
        3. Wrap in clear boundary markers so the model knows it's user content
        """
        cwd = Path.cwd()
        rules_paths = [
            cwd / ".forgegod" / "rules.md",
            cwd / ".forgegod" / "RULES.md",
            cwd / "AGENTS.md",  # Convention from other tools
        ]

        # Patterns that suggest prompt injection attempts
        INJECTION_PATTERNS = [
            "ignore previous instructions",
            "ignore all previous",
            "disregard above",
            "new system prompt",
            "you are now",
            "act as root",
            "sudo",
            "override safety",
        ]

        for p in rules_paths:
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    if not content.strip():
                        continue

                    # Cap content size
                    if len(content) > max_chars:
                        content = content[:max_chars] + "\n[... truncated at security limit ...]"

                    # Check for injection patterns
                    content_lower = content.lower()
                    for pattern in INJECTION_PATTERNS:
                        if pattern in content_lower:
                            logger.warning(
                                f"Potential prompt injection in {p.name}: "
                                f"found '{pattern}'. File ignored."
                            )
                            return (
                                f"\n\n## WARNING: {p.name} was skipped — "
                                f"contains suspicious content (possible prompt injection)"
                            )

                    # Wrap in boundary markers
                    return (
                        f"\n\n## Project Rules (from {p.name})\n"
                        f"<project_rules>\n{content}\n</project_rules>"
                    )
                except OSError:
                    continue
        return ""
