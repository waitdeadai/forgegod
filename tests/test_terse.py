"""Tests for ForgeGod Caveman / Terse mode."""

from forgegod.config import ForgeGodConfig
from forgegod.terse import (
    TERSE_PLANNER_PROMPT,
    TERSE_REVIEWER_PROMPT,
    TERSE_SYSTEM_PROMPT,
    TERSE_TOOL_DESCRIPTIONS,
    TokenSavingsTracker,
    apply_terse_tool_defs,
    compress_tool_output,
)


def test_terse_system_prompt_shorter():
    """TERSE_SYSTEM_PROMPT should be significantly shorter than verbose."""
    # Read SYSTEM_PROMPT from source to avoid heavy agent.py import chain
    import ast
    from pathlib import Path

    agent_src = Path(__file__).parent.parent / "forgegod" / "agent.py"
    tree = ast.parse(agent_src.read_text(encoding="utf-8"))
    verbose_prompt = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SYSTEM_PROMPT":
                    verbose_prompt = ast.literal_eval(node.value)
                    break

    assert verbose_prompt, "Could not find SYSTEM_PROMPT in agent.py"
    terse_len = len(TERSE_SYSTEM_PROMPT)
    verbose_len = len(verbose_prompt)
    # Terse should be < 60% of verbose
    assert terse_len < verbose_len * 0.6, (
        f"Terse ({terse_len}) should be < 60% of verbose ({verbose_len})"
    )


def test_terse_tool_descriptions_all_covered():
    """All expected tools should have a terse description."""
    # The 19 registered tools (verified by grep on tools/ module)
    expected_tools = {
        "read_file", "write_file", "edit_file", "glob", "grep",
        "repo_map", "bash", "git_status", "git_diff", "git_commit",
        "git_log", "git_worktree_create", "git_worktree_remove",
        "mcp_connect", "mcp_call", "mcp_list", "mcp_disconnect",
        "list_skills", "load_skill",
    }

    for name in expected_tools:
        assert name in TERSE_TOOL_DESCRIPTIONS, (
            f"Tool '{name}' missing from TERSE_TOOL_DESCRIPTIONS"
        )


def test_compress_tool_output_truncates():
    """Output respects max_chars limit."""
    long_output = "x" * 10000
    compressed = compress_tool_output(long_output, max_chars=500)
    assert len(compressed) <= 600  # Allow some overhead for truncation marker


def test_compress_tool_output_strips_tracebacks():
    """Verbose traceback should be compressed to last frame + exception."""
    verbose_tb = """Traceback (most recent call last):
  File "/app/main.py", line 100, in run
    result = await process()
  File "/app/process.py", line 50, in process
    data = load_data()
  File "/app/loader.py", line 20, in load_data
    return json.loads(raw)
  File "/usr/lib/python3.12/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)"""

    compressed = compress_tool_output(verbose_tb)
    # Should keep header + last 2 lines
    assert "Traceback" in compressed
    assert "json.JSONDecodeError" in compressed
    # Should be significantly shorter
    assert len(compressed) < len(verbose_tb)


def test_token_savings_tracker():
    """Correct % calculation."""
    tracker = TokenSavingsTracker()
    tracker.record(original=1000, terse=400)
    assert tracker.original_tokens == 250  # 1000 / 4
    assert tracker.terse_tokens == 100  # 400 / 4
    assert tracker.tokens_saved == 150
    assert tracker.savings_pct == 60.0
    assert "60%" in tracker.summary()


def test_token_savings_tracker_zero():
    """No division by zero when empty."""
    tracker = TokenSavingsTracker()
    assert tracker.savings_pct == 0.0
    assert tracker.tokens_saved == 0


def test_apply_terse_tool_defs():
    """Terse tool defs should replace descriptions."""
    tool_defs = [
        {
            "function": {
                "name": "read_file",
                "description": (
                    "Very long verbose description of reading"
                    " a file with line numbers and metadata"
                ),
            }
        },
        {
            "function": {
                "name": "bash",
                "description": (
                    "Execute a shell command in the project"
                    " directory with timeout support"
                ),
            }
        },
    ]
    result = apply_terse_tool_defs(tool_defs)
    assert result[0]["function"]["description"] == "Read file with line numbers"
    assert result[1]["function"]["description"] == "Run shell command"


def test_terse_tool_defs_shorter():
    """Terse descriptions produce fewer total chars than verbose ones."""
    import copy

    # Simulate verbose tool defs (representative sample)
    verbose_defs = [
        {
            "function": {
                "name": "read_file",
                "description": (
                    "Read a file from the filesystem with line"
                    " numbers displayed for easy reference"
                ),
            }
        },
        {
            "function": {
                "name": "edit_file",
                "description": (
                    "Replace a unique string in a file with a"
                    " new string, supporting precise modifications"
                ),
            }
        },
        {
            "function": {
                "name": "bash",
                "description": (
                    "Execute a shell command in the project"
                    " directory with configurable timeout"
                ),
            }
        },
        {
            "function": {
                "name": "repo_map",
                "description": (
                    "Generate a codebase overview showing file"
                    " tree with function and class signatures"
                ),
            }
        },
    ]
    original_chars = sum(len(td["function"]["description"]) for td in verbose_defs)

    terse_defs = apply_terse_tool_defs(copy.deepcopy(verbose_defs))
    terse_chars = sum(len(td["function"]["description"]) for td in terse_defs)

    assert terse_chars < original_chars, (
        f"Terse ({terse_chars}) should be < original ({original_chars})"
    )


def test_terse_planner_prompt_has_json_schema():
    """Terse planner prompt must preserve JSON schema."""
    assert '"project"' in TERSE_PLANNER_PROMPT
    assert '"stories"' in TERSE_PLANNER_PROMPT
    assert '"acceptance_criteria"' in TERSE_PLANNER_PROMPT


def test_terse_reviewer_prompt_has_json_schema():
    """Terse reviewer prompt must preserve JSON schema."""
    assert '"verdict"' in TERSE_REVIEWER_PROMPT
    assert '"confidence"' in TERSE_REVIEWER_PROMPT
    assert '"issues"' in TERSE_REVIEWER_PROMPT


def test_terse_config_defaults():
    """TerseConfig defaults are sensible."""
    config = ForgeGodConfig()
    assert config.terse.enabled is False
    assert config.terse.compress_tool_output is True
    assert config.terse.tool_output_max_chars == 4000
    assert config.terse.track_savings is True
