"""Tests for ForgeGod Planner — PRD generation and story decomposition."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.models import PRD, StoryStatus
from forgegod.planner import Planner
from forgegod.router import ModelRouter

# ── Test fixtures ──


@pytest.fixture
def config():
    """Create a minimal ForgeGodConfig for testing."""
    return ForgeGodConfig()


@pytest.fixture
def mock_router(config):
    """Create a mock router that returns deterministic responses."""
    router = MagicMock(spec=ModelRouter)
    router.call = AsyncMock()
    return router


# ── Test data ──


def SAMPLE_PRD_RESPONSE() -> str:
    """Sample LLM response for decompose()."""
    return '''{
  "project": "test-project",
  "description": "A test project with multiple stories",
  "stories": [
    {
      "id": "S001",
      "title": "Setup project structure",
      "description": "Create the basic project files and directories",
      "priority": 1,
      "acceptance_criteria": ["Project directory exists", "config.toml is created", "README.md is created"]
    },
    {
      "id": "S002",
      "title": "Implement core module",
      "description": "Create the main application module",
      "priority": 2,
      "acceptance_criteria": ["Module imports correctly", "Core functions work as expected"]
    },
    {
      "id": "S003",
      "title": "Add tests",
      "description": "Write unit tests for core module",
      "priority": 3,
      "acceptance_criteria": ["All tests pass", "Test coverage is adequate"]
    }
  ],
  "guardrails": ["Never delete main.py", "Always write tests first"]
}'''


def SAMPLE_PRD_RESPONSE_WITH_FALLBACK() -> str:
    """Sample LLM response that is not valid JSON (triggers fallback)."""
    return '''Here is the task description:
Build a simple CLI tool.

The tool should:
- Read a file
- Write to another file
- Handle errors gracefully

Please implement this.
'''


def SAMPLE_PRD_RESPONSE_WITH_EXTRA_JSON() -> str:
    """Sample LLM response with markdown fences around JSON."""
    return '''```json
{
  "project": "markdown-test",
  "description": "Test project with markdown",
  "stories": [
    {
      "id": "S001",
      "title": "First story",
      "description": "First story description",
      "priority": 1,
      "acceptance_criteria": ["Criterion 1"]
    }
  ],
  "guardrails": ["Rule 1"]
}
```
'''


# ── Test functions ──


@pytest.mark.asyncio
async def test_parse_prd_response_valid_json(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test parsing a valid JSON PRD response."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock to return valid JSON
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify PRD structure
    assert prd.project == "test-project"
    assert prd.description == "A test project with multiple stories"
    assert len(prd.stories) == 3
    assert len(prd.guardrails) == 2

    # Verify stories
    assert prd.stories[0].id == "S001"
    assert prd.stories[0].title == "Setup project structure"
    assert prd.stories[0].priority == 1
    assert prd.stories[0].acceptance_criteria == ["Project directory exists", "config.toml is created", "README.md is created"]

    assert prd.stories[1].id == "S002"
    assert prd.stories[1].priority == 2

    assert prd.stories[2].id == "S003"
    assert prd.stories[2].priority == 3


@pytest.mark.asyncio
async def test_parse_prd_response_with_markdown_fences(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test parsing JSON wrapped in markdown fences."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock to return JSON with markdown fences
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE_WITH_EXTRA_JSON(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify PRD was parsed correctly
    assert prd.project == "markdown-test"
    assert len(prd.stories) == 1
    assert prd.stories[0].id == "S001"


@pytest.mark.asyncio
async def test_parse_prd_response_invalid_json_fallback(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test fallback behavior when JSON parsing fails."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock to return invalid JSON
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE_WITH_FALLBACK(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify fallback PRD was created
    assert prd.project == "project"  # Uses default project_name when JSON parsing fails
    assert len(prd.stories) == 1
    assert prd.stories[0].id == "S001"
    assert prd.stories[0].title == "Implement task"
    assert prd.stories[0].acceptance_criteria == ["Task is complete"]


@pytest.mark.asyncio
async def test_story_priority_ordering(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test that stories are ordered by priority (dependency order)."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock with multiple stories
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify priority ordering
    assert prd.stories[0].priority == 1
    assert prd.stories[1].priority == 2
    assert prd.stories[2].priority == 3

    # Verify IDs are sequential
    assert prd.stories[0].id == "S001"
    assert prd.stories[1].id == "S002"
    assert prd.stories[2].id == "S003"


@pytest.mark.asyncio
async def test_prd_json_serialization_roundtrip(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test that PRD can be serialized to JSON and deserialized correctly."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Serialize to JSON
    json_str = prd.model_dump_json()

    # Deserialize from JSON
    prd2 = PRD.model_validate_json(json_str)

    # Verify round-trip
    assert prd2.project == prd.project
    assert prd2.description == prd.description
    assert len(prd2.stories) == len(prd.stories)
    assert len(prd2.guardrails) == len(prd.guardrails)

    # Verify stories match
    for i, (s1, s2) in enumerate(zip(prd.stories, prd2.stories)):
        assert s1.id == s2.id
        assert s1.title == s2.title
        assert s1.description == s2.description
        assert s1.priority == s2.priority
        assert s1.acceptance_criteria == s2.acceptance_criteria


@pytest.mark.asyncio
async def test_prd_empty_stories_fallback(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test PRD creation when LLM returns empty stories list."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock with empty stories
    empty_response = '''{
  "project": "empty-project",
  "description": "Empty stories test",
  "stories": [],
  "guardrails": []
}'''
    mock_router.call.return_value = (empty_response, "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify empty stories list is handled
    assert prd.project == "empty-project"
    assert len(prd.stories) == 0
    assert len(prd.guardrails) == 0


@pytest.mark.asyncio
async def test_prd_partial_stories(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test PRD creation when some story fields are missing."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock with partial story data
    partial_response = '''{
  "project": "partial-project",
  "description": "Partial stories test",
  "stories": [
    {
      "id": "S001",
      "title": "First story"
    },
    {
      "id": "S002",
      "description": "Second story description",
      "priority": 2
    }
  ],
  "guardrails": ["Rule 1"]
}'''
    mock_router.call.return_value = (partial_response, "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify default values are used for missing fields
    assert prd.stories[0].title == "First story"
    assert prd.stories[0].description == ""  # Default
    assert prd.stories[0].priority == 1  # Default

    assert prd.stories[1].title == "Untitled"  # Default
    assert prd.stories[1].description == "Second story description"
    assert prd.stories[1].priority == 2


@pytest.mark.asyncio
async def test_prd_guardrails_parsing(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test that guardrails are correctly parsed from LLM response."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock with guardrails
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify guardrails
    assert len(prd.guardrails) == 2
    assert "Never delete main.py" in prd.guardrails
    assert "Always write tests first" in prd.guardrails


@pytest.mark.asyncio
async def test_prd_default_project_name(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test that project name defaults when not provided in LLM response."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock without project field
    no_project_response = '''{
  "description": "No project name test",
  "stories": [
    {
      "id": "S001",
      "title": "First story",
      "description": "First story",
      "priority": 1,
      "acceptance_criteria": ["Test"]
    }
  ],
  "guardrails": []
}'''
    mock_router.call.return_value = (no_project_response, "usage")

    # Call decompose with explicit project name
    prd = await planner.decompose("Test task", project_name="explicit-project")

    # Verify project name from response is used if present, otherwise default
    assert prd.project == "explicit-project"


@pytest.mark.asyncio
async def test_prd_story_status_default(mock_router: ModelRouter, config: ForgeGodConfig):
    """Test that story status defaults to TODO."""
    planner = Planner(config=config, router=mock_router)

    # Setup mock
    mock_router.call.return_value = (SAMPLE_PRD_RESPONSE(), "usage")

    # Call decompose
    prd = await planner.decompose("Test task")

    # Verify story status
    assert prd.stories[0].status == StoryStatus.TODO
    assert prd.stories[1].status == StoryStatus.TODO
    assert prd.stories[2].status == StoryStatus.TODO
