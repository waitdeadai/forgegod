"""Tests for ForgeGod tool system."""

import tempfile
from pathlib import Path

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.tools import (
    execute_tool,
    get_tool_defs,
    load_all_tools,
    reset_tool_context,
    set_tool_context,
)
from forgegod.tools.filesystem import edit_file, glob_files, grep_files, read_file, write_file


@pytest.fixture(autouse=True)
def _load_tools():
    load_all_tools()


def test_tool_registry():
    defs = get_tool_defs()
    names = [d["function"]["name"] for d in defs]
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "glob" in names
    assert "grep" in names
    assert "bash" in names
    assert "git_status" in names
    assert "mcp_connect" in names
    # Skills tools (OpenClaw pattern)
    assert "list_skills" in names
    assert "load_skill" in names
    # Repo map tool (Aider pattern)
    assert "repo_map" in names


def test_tool_defs_format():
    defs = get_tool_defs()
    for d in defs:
        assert d["type"] == "function"
        assert "name" in d["function"]
        assert "description" in d["function"]
        assert "parameters" in d["function"]


@pytest.mark.asyncio
async def test_read_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line1\nline2\nline3\n")
        f.flush()
        result = await read_file(f.name)
        assert "line1" in result
        assert "line2" in result
        assert "3" in result  # total lines


@pytest.mark.asyncio
async def test_read_file_not_found():
    result = await read_file("/nonexistent/file.txt")
    assert "Error" in result


@pytest.mark.asyncio
async def test_write_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "test.txt")
        write_result = await write_file(path, "hello world")
        assert "Written" in write_result

        read_result = await read_file(path)
        assert "hello world" in read_result


@pytest.mark.asyncio
async def test_edit_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("old_value = 1\n")
        f.flush()
        result = await edit_file(f.name, "old_value = 1", "new_value = 2")
        assert "Edited" in result

        content = Path(f.name).read_text()
        assert "new_value = 2" in content


@pytest.mark.asyncio
async def test_edit_file_not_unique():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("x = 1\nx = 1\n")
        f.flush()
        result = await edit_file(f.name, "x = 1", "x = 2")
        assert "Error" in result
        assert "2 times" in result


@pytest.mark.asyncio
async def test_glob_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("pass")
        (Path(tmpdir) / "test.txt").write_text("hello")
        result = await glob_files("*.py", tmpdir)
        assert "test.py" in result
        assert "test.txt" not in result


@pytest.mark.asyncio
async def test_grep_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "code.py").write_text("def hello():\n    return 'world'\n")
        result = await grep_files("hello", tmpdir)
        assert "hello" in result
        assert "code.py" in result


@pytest.mark.asyncio
async def test_edit_file_fuzzy_whitespace():
    """Fuzzy matching should handle trailing whitespace differences."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello():  \n    return 'world'\n")
        f.flush()
        # LLM sends without trailing spaces — fuzzy match should find it
        result = await edit_file(
            f.name,
            "def hello():\n    return 'world'",
            "def hello():\n    return 'earth'",
        )
        assert "Edited" in result or "fuzzy" in result
        content = Path(f.name).read_text()
        assert "earth" in content


@pytest.mark.asyncio
async def test_repo_map():
    """repo_map should generate file tree with Python signatures."""
    from forgegod.tools.filesystem import repo_map
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("class App:\n    def run(self):\n        pass\n")
        (Path(tmpdir) / "utils.py").write_text("def helper(x: int) -> str:\n    return str(x)\n")
        result = await repo_map(tmpdir)
        assert "main.py" in result
        assert "class App" in result
        assert "def run" in result
        assert "utils.py" in result
        assert "def helper" in result


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    result = await execute_tool("nonexistent_tool", {})
    assert "Error" in result
    assert "Unknown" in result


@pytest.mark.asyncio
async def test_read_file_blocks_workspace_escape_when_scoped():
    with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as outside:
        workspace_path = Path(workspace)
        config = ForgeGodConfig()
        config.project_dir = workspace_path / ".forgegod"
        config.project_dir.mkdir()

        inside_file = workspace_path / "inside.txt"
        outside_file = Path(outside) / "outside.txt"
        inside_file.write_text("inside")
        outside_file.write_text("outside")

        token = set_tool_context(config)
        try:
            inside = await read_file(str(inside_file))
            blocked = await read_file(str(outside_file))
        finally:
            reset_tool_context(token)

        assert "inside" in inside
        assert "escapes workspace root" in blocked
