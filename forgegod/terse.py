"""ForgeGod Caveman Mode — terse prompts for 50-75% token savings.

Research backing (all confirm terse = same or better accuracy for coding):
- Mini-SWE-Agent: 100 lines, >74% SWE-bench Verified (github.com/SWE-agent/mini-swe-agent)
- Chain of Draft: 7.6% tokens, same accuracy (arxiv.org/abs/2502.18600)
- CCoT: 48.7% shorter, negligible impact (arxiv.org/abs/2401.05618)
- Long prompts HURT: degradation >2K tokens (gritdaily.com/impact-prompt-length-llm-performance)
- LLMLingua: 20x compression, 1.5% loss (llmlingua.com)
"""

from __future__ import annotations

import re

# ── Terse System Prompt (~80 tokens vs ~200 original) ──

TERSE_SYSTEM_PROMPT = """ForgeGod. Autonomous coder.

## Flow: ORIENT>LOCATE>READ>PLAN>IMPLEMENT>VERIFY>COMMIT
Gate: no IMPLEMENT til PLAN solid. No COMMIT til VERIFY pass.

## Tools
repo_map(path) — codebase overview. USE FIRST.
read_file(path) — file+line numbers
edit_file(path,old,new) — replace unique string. Preferred.
write_file(path,content) — new files only
glob(pattern) — find files
grep(pattern) — search contents (regex)
bash(cmd) — shell
git_status/git_diff/git_commit — git ops
mcp_connect/mcp_call — external MCP
list_skills/load_skill — task skills

## Rules
Read before edit. Verify after change. One thing at a time.
Existing code wins. No speculation. Minimal changes.
Fail 2x? (1)what failed (2)what fixes (3)new approach?

CWD: {cwd}
"""

# ── Terse Coder Prompt ──

TERSE_CODER_PROMPT = """ForgeGod Coder.

<sp>G:{task} F:{file_path}({lang}) A:{attempt}/{max_attempts} R:{reflection}</sp>

{conventions}
{context_block}
{existing_code_block}
{learnings_block}
{reflections_block}
{critical_block}
Output ONLY {lang} code in ```{lang} fences. No text."""

# ── Terse Planner Prompt ──

TERSE_PLANNER_PROMPT = """Decompose task into ordered stories. Each independently testable.

## Task
{task}

## Output (JSON only)
{{"project":"{project_name}","description":"...","stories":[{{"id":"S001","title":"...","description":"...","priority":1,"acceptance_criteria":["..."]}}],"guardrails":["..."]}}

Rules: dependency order. Small (1-3 files). Testable criteria. Max 20. IDs: S001+.

Output ONLY valid JSON, no markdown fences, no explanations."""

# ── Terse Reviewer Prompt ──

TERSE_REVIEWER_PROMPT = """Review code changes.

## Task
{task}

## Code
```
{code}
```

{test_block}
{files_block}

Criteria: correctness, security, quality, completeness.

Output JSON: {{"verdict":"approve|revise|reject","confidence":0.0-1.0,
"reasoning":"...","issues":["..."],"suggestions":["..."]}}

Output ONLY valid JSON."""

# ── Terse Story Prompt (loop) ──

TERSE_STORY_INSTRUCTIONS = """
## Do (in order)
1. repo_map → orient
2. read_file → relevant files
3. write_file/edit_file → MAKE CHANGES (MUST produce file changes)
4. bash → run tests
5. bash → git add . && git commit -m "story_id: description"

CRITICAL: Actually call tools. Don't describe — DO.
"""

# ── Terse Tool Descriptions ──

TERSE_TOOL_DESCRIPTIONS: dict[str, str] = {
    "read_file": "Read file with line numbers",
    "write_file": "Write/create file",
    "edit_file": "Replace unique string in file",
    "glob": "Find files by pattern",
    "grep": "Search file contents (regex)",
    "repo_map": "Codebase overview. Use FIRST.",
    "bash": "Run shell command",
    "git_status": "Git status (short)",
    "git_diff": "Git diff",
    "git_commit": "Stage + commit",
    "git_log": "Recent git log",
    "git_worktree_create": "Create worktree branch",
    "git_worktree_remove": "Remove worktree",
    "mcp_connect": "Connect MCP server",
    "mcp_call": "Call MCP tool",
    "mcp_list": "List MCP servers/tools",
    "mcp_disconnect": "Disconnect MCP server",
    "list_skills": "List available skills",
    "load_skill": "Load skill instructions",
}


def apply_terse_tool_defs(tool_defs: list[dict]) -> list[dict]:
    """Replace tool descriptions with terse versions in-place."""
    for td in tool_defs:
        func = td.get("function", {})
        name = func.get("name", "")
        if name in TERSE_TOOL_DESCRIPTIONS:
            func["description"] = TERSE_TOOL_DESCRIPTIONS[name]
    return tool_defs


# ── Tool Output Compression ──

_TRACEBACK_RE = re.compile(
    r"Traceback \(most recent call last\):.*?(?=\n\S|\Z)",
    re.DOTALL,
)


def compress_tool_output(content: str, max_chars: int = 4000) -> str:
    """Compress tool output for context re-injection.

    - Strip verbose tracebacks to last frame + exception message
    - Remove consecutive blank lines
    - Truncate keeping head + tail
    """
    # Compress Python tracebacks to last frame + exception
    def _compress_tb(match: re.Match) -> str:
        tb = match.group(0)
        lines = tb.strip().split("\n")
        if len(lines) <= 4:
            return tb
        # Keep "Traceback..." header + last 2 lines (frame + exception)
        return lines[0] + "\n  ...\n" + "\n".join(lines[-2:])

    content = _TRACEBACK_RE.sub(_compress_tb, content)

    # Remove consecutive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Truncate keeping head + tail
    if len(content) > max_chars:
        half = max_chars // 2
        content = content[:half] + "\n\n... (truncated) ...\n\n" + content[-half:]

    return content


# ── Token Savings Tracker ──


class TokenSavingsTracker:
    """Track estimated token savings from terse mode."""

    def __init__(self) -> None:
        self.original_chars: int = 0
        self.terse_chars: int = 0

    def record(self, original: int, terse: int) -> None:
        """Record a compression event."""
        self.original_chars += original
        self.terse_chars += terse

    @property
    def original_tokens(self) -> int:
        return self.original_chars // 4

    @property
    def terse_tokens(self) -> int:
        return self.terse_chars // 4

    @property
    def tokens_saved(self) -> int:
        return self.original_tokens - self.terse_tokens

    @property
    def savings_pct(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return (1 - self.terse_tokens / self.original_tokens) * 100

    def summary(self) -> str:
        return (
            f"Terse savings: {self.savings_pct:.0f}% "
            f"({self.tokens_saved:,} tokens saved)"
        )
