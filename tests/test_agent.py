"""Tests for ForgeGod Agent — tool call parsing, gutter detection, context management."""

import json
import tempfile
from pathlib import Path

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.models import ModelUsage, ToolCall, ToolResult


@pytest.fixture
def config():
    """Minimal config for agent tests."""
    return ForgeGodConfig()


@pytest.fixture
def agent(config):
    """Agent instance with custom system prompt (skips env detection)."""
    from forgegod.agent import Agent
    return Agent(config=config, system_prompt="You are a test agent.")


# ── Tool Call Parsing ──


class TestParseToolCalls:
    def test_openai_format(self, agent):
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "name": "read_file", "arguments": {"path": "test.py"}},
                {"id": "call_2", "name": "grep", "arguments": {"pattern": "def main"}},
            ]
        })
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 2
        assert calls[0].name == "read_file"
        assert calls[0].arguments == {"path": "test.py"}
        assert calls[1].name == "grep"

    def test_hermes_xml_format(self, agent):
        """Hermes/Teknium <tool_call> XML format."""
        response = (
            'Let me check the file.\n'
            '<tool_call>{"name": "read_file", "arguments": {"path": "main.py"}}</tool_call>'
        )
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].name == "read_file"
        assert calls[0].arguments == {"path": "main.py"}

    def test_hermes_multiple_tool_calls(self, agent):
        """Hermes format with multiple tool calls in one response."""
        response = (
            '<tool_call>{"name": "read_file", "arguments": {"path": "a.py"}}</tool_call>\n'
            '<tool_call>{"name": "read_file", "arguments": {"path": "b.py"}}</tool_call>'
        )
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 2
        assert calls[0].arguments["path"] == "a.py"
        assert calls[1].arguments["path"] == "b.py"

    def test_hermes_with_parameters_key(self, agent):
        """Some models use 'parameters' instead of 'arguments'."""
        response = '<tool_call>{"name": "glob", "parameters": {"pattern": "*.py"}}</tool_call>'
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].arguments == {"pattern": "*.py"}

    def test_single_json_block(self, agent):
        response = json.dumps({"name": "bash", "arguments": {"command": "ls"}})
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].name == "bash"

    def test_plain_text_no_tools(self, agent):
        response = "The function is defined at line 42 of main.py."
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 0

    def test_string_arguments_auto_parse(self, agent):
        """Arguments passed as JSON string should be auto-parsed."""
        response = json.dumps({
            "tool_calls": [{
                "id": "call_1",
                "name": "edit_file",
                "arguments": '{"path": "x.py", "old_string": "a", "new_string": "b"}',
            }]
        })
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].arguments["path"] == "x.py"


# ── Gutter Detection ──


class TestGutterDetection:
    def test_no_gutter_on_first_call(self, agent):
        tc = ToolCall(name="read_file", arguments={"path": "x.py"})
        result = ToolResult(name="read_file", content="file contents")
        assert agent._detect_gutter(tc, result) is False

    def test_gutter_on_third_repeat(self, agent):
        tc = ToolCall(name="bash", arguments={"command": "npm test"})
        result = ToolResult(name="bash", content="FAIL")
        assert agent._detect_gutter(tc, result) is False  # 1st
        assert agent._detect_gutter(tc, result) is False  # 2nd
        assert agent._detect_gutter(tc, result) is True   # 3rd → gutter

    def test_different_args_no_gutter(self, agent):
        result = ToolResult(name="read_file", content="ok")
        for i in range(5):
            tc = ToolCall(name="read_file", arguments={"path": f"file_{i}.py"})
            assert agent._detect_gutter(tc, result) is False


# ── Context Management ──


class TestContextManagement:
    def test_prune_tool_results(self, agent):
        """Large tool results should be pruned in-place."""
        agent.messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "tool", "name": "read_file", "content": "x" * 20000},
        ]
        agent._prune_tool_results()
        assert len(agent.messages[2]["content"]) < 20000
        assert "pruned" in agent.messages[2]["content"]

    def test_small_results_not_pruned(self, agent):
        """Small tool results should be left intact."""
        content = "short result"
        agent.messages = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "name": "grep", "content": content},
        ]
        agent._prune_tool_results()
        assert agent.messages[1]["content"] == content

    def test_context_size_estimate(self, agent):
        agent.messages = [
            {"role": "system", "content": "a" * 400},
            {"role": "user", "content": "b" * 400},
        ]
        # 800 chars / 4 = 200 tokens
        assert agent.context_size_estimate == 200


# ── Project Rules ──


class TestProjectRules:
    def test_load_rules_from_forgegod_dir(self):
        """Should load rules from .forgegod/rules.md."""
        from forgegod.agent import Agent
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".forgegod"
            rules_dir.mkdir()
            (rules_dir / "rules.md").write_text("Always use pytest for testing.\n")

            import os
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = Agent._load_project_rules()
                assert "Always use pytest" in result
                assert "rules.md" in result
            finally:
                os.chdir(old_cwd)

    def test_load_rules_empty_returns_empty(self):
        from forgegod.agent import Agent
        with tempfile.TemporaryDirectory() as tmpdir:
            import os
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = Agent._load_project_rules()
                assert result == ""
            finally:
                os.chdir(old_cwd)


class TestDesignSystem:
    def test_load_design_md_from_root(self):
        from forgegod.agent import Agent
        with tempfile.TemporaryDirectory() as tmpdir:
            design_md = Path(tmpdir) / "DESIGN.md"
            design_md.write_text("# DESIGN\nUse cyan accents.\n", encoding="utf-8")

            result = Agent._load_design_system(Path(tmpdir))
            assert "Use cyan accents." in result
            assert "<design_system>" in result

    def test_load_design_md_empty_returns_empty(self):
        from forgegod.agent import Agent
        with tempfile.TemporaryDirectory() as tmpdir:
            result = Agent._load_design_system(Path(tmpdir))
            assert result == ""


# ── Skills ──


class TestSkills:
    @pytest.mark.asyncio
    async def test_list_skills_empty(self):
        """No skills dir → helpful message."""
        import os

        from forgegod.tools.skills import list_skills
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = await list_skills()
                assert "No skills directory" in result
            finally:
                os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_list_and_load_skill(self):
        """Create a skill and verify list + load."""
        import os

        from forgegod.tools.skills import list_skills, load_skill
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / ".forgegod" / "skills" / "testing"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "# Testing Skill\nAlways run pytest with -v flag.\n"
            )

            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                listed = await list_skills()
                assert "testing" in listed
                assert "Always run pytest" in listed

                loaded = await load_skill("testing")
                assert "Testing Skill" in loaded
                assert "-v flag" in loaded
            finally:
                os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_load_nonexistent_skill(self):
        import os

        from forgegod.tools.skills import load_skill
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = await load_skill("nonexistent")
                assert "Error" in result
            finally:
                os.chdir(old_cwd)

    def test_skills_summary_empty(self):
        """No skills → empty string."""
        import os

        from forgegod.tools.skills import get_skills_summary
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                assert get_skills_summary() == ""
            finally:
                os.chdir(old_cwd)


# ── Two-Stage Tool Validation ──


class TestToolValidation:
    @pytest.mark.asyncio
    async def test_unknown_tool_lists_available(self, agent):
        """Unknown tool should list available tools."""
        tc = ToolCall(name="nonexistent_tool", arguments={})
        result = await agent._execute_tool_call(tc)
        assert result.error is True
        assert "Unknown tool" in result.content
        assert "read_file" in result.content  # Should list available tools

    @pytest.mark.asyncio
    async def test_missing_required_args(self, agent):
        """Missing required args should be caught before execution."""
        tc = ToolCall(name="read_file", arguments={})  # Missing 'path'
        result = await agent._execute_tool_call(tc)
        assert result.error is True
        assert "Missing required" in result.content

    @pytest.mark.asyncio
    async def test_valid_tool_call_executes(self):
        """Valid tool call should execute normally."""
        from forgegod.agent import Agent

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = ForgeGodConfig()
            config.project_dir = workspace / ".forgegod"
            config.project_dir.mkdir()
            agent = Agent(config=config, system_prompt="You are a test agent.")

            target = workspace / "test.txt"
            target.write_text("test content\n")

            tc = ToolCall(name="read_file", arguments={"path": str(target)})
            result = await agent._execute_tool_call(tc)
            agent.budget.close()
            assert result.error is False
            assert "test content" in result.content


class FakeRouter:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0

    async def call(self, **_kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response, ModelUsage(provider="zai", model="glm-5.1")


class TestCompletionEvidence:
    def test_task_requires_code_changes(self, agent):
        assert agent._task_requires_code_changes("Implement the API handler") is True
        assert agent._task_requires_code_changes("## Acceptance Criteria\n- add tests") is True
        assert agent._task_requires_code_changes("Explain the current architecture") is False
        assert agent._task_requires_code_changes("Run python --version and report it.") is False
        assert agent._task_requires_code_changes(
            "Check whether strict sandbox execution is available."
        ) is False
        assert agent._task_requires_code_changes("Run tests and fix failures") is True

    def test_completion_blockers_for_code_changes(self, agent):
        agent.files_modified = ["src/app.py"]
        blockers = agent._completion_blockers(requires_code_changes=True)
        assert any("git_diff" in blocker for blocker in blockers)
        assert any("verification command" in blocker for blocker in blockers)

    def test_docs_only_change_does_not_require_runtime_verification(self, agent):
        agent.files_modified = ["README.md"]
        blockers = agent._completion_blockers(requires_code_changes=True)
        assert blockers == ["Review the final patch with git_diff after your last code change."]

    @pytest.mark.asyncio
    async def test_agent_run_requires_post_edit_verification_and_diff(self, tmp_path):
        from forgegod.agent import Agent

        project_dir = tmp_path / ".forgegod"
        project_dir.mkdir()
        router = FakeRouter([
            json.dumps({
                "tool_calls": [{
                    "id": "call_1",
                    "name": "write_file",
                    "arguments": {"path": "src/app.py", "content": "print('hi')\n"},
                }]
            }),
            "Implemented the change.",
            json.dumps({
                "tool_calls": [{
                    "id": "call_2",
                    "name": "bash",
                    "arguments": {"command": "python -m pytest -q"},
                }]
            }),
            json.dumps({
                "tool_calls": [{
                    "id": "call_3",
                    "name": "git_diff",
                    "arguments": {},
                }]
            }),
            (
                "Implemented src/app.py.\n"
                "Files changed: src/app.py\n"
                "Verification commands run: python -m pytest -q"
            ),
        ])

        config = ForgeGodConfig()
        config.project_dir = project_dir
        agent = Agent(
            config=config,
            router=router,
            system_prompt="You are a test agent.",
            max_turns=8,
        )
        agent.memory = None

        async def fake_execute(tool_calls):
            results = []
            for tc in tool_calls:
                results.append(
                    ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content="ok",
                        error=False,
                    )
                )
            return results

        agent._execute_tool_batch = fake_execute  # type: ignore[method-assign]

        result = await agent.run("Implement the API handler")
        agent.budget.close()

        assert result.success is True
        assert result.files_modified == ["src/app.py"]
        assert result.verification_commands == ["python -m pytest -q"]
        assert result.reviewed_final_diff is True
        assert router.calls == 5
