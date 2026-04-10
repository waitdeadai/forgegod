from __future__ import annotations

import json

import pytest

from forgegod.config import ForgeGodConfig
from forgegod.planner import Planner


class FakeRouter:
    def __init__(self, response: dict[str, object]):
        self.response = response
        self.prompt = ""

    async def call(self, prompt: str, **_: object):
        self.prompt = prompt
        return json.dumps(self.response), None


def _write(tmp_path, relative: str, content: str) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.asyncio
async def test_planner_prefers_repository_backlog_when_docs_exist(tmp_path):
    _write(
        tmp_path,
        "docs/PRD.md",
        """# Tarot 3:33

A ritualized tarot web app that opens during configured windows.

## v1 Non-Goals

- payments
- subscriptions
- user accounts
""",
    )
    _write(
        tmp_path,
        "docs/README.md",
        """# Tarot Showcase

This folder is the source of truth for planning the Tarot build.

## v1 Constraint

- no login
- no admin panel
""",
    )
    _write(
        tmp_path,
        "docs/STORIES.md",
        """# Tarot Backlog

## Milestone A: Foundation

### T001 - Create app skeleton

- bootstrap a new Next.js App Router app in TypeScript
- add lint, unit test, and E2E test scaffolding

### T002 - Add baseline metadata

- manifest
- robots
- sitemap
""",
    )
    (tmp_path / ".forgegod").mkdir()

    router = FakeRouter(
        {
            "project": "tarot",
            "description": "generic app",
            "stories": [
                {
                    "id": "S001",
                    "title": "Database Schema and Migration Setup",
                    "description": "Set up a database",
                    "priority": 1,
                    "acceptance_criteria": ["Database exists"],
                },
                {
                    "id": "S002",
                    "title": "User Authentication System",
                    "description": "Add login",
                    "priority": 2,
                    "acceptance_criteria": ["Users can log in"],
                },
            ],
            "guardrails": ["Rule from model"],
        }
    )
    config = ForgeGodConfig(project_dir=tmp_path / ".forgegod")

    prd = await Planner(config=config, router=router).decompose(
        "Build Tarot from repository docs",
        project_name="tarot",
    )

    assert [story.id for story in prd.stories] == ["T001", "T002"]
    assert [story.title for story in prd.stories] == [
        "Create app skeleton",
        "Add baseline metadata",
    ]
    assert prd.stories[0].acceptance_criteria == [
        "bootstrap a new Next.js App Router app in TypeScript",
        "add lint, unit test, and E2E test scaffolding",
    ]
    assert all("Authentication" not in story.title for story in prd.stories)
    assert all("Database" not in story.title for story in prd.stories)
    assert "Repository Backlog Seed" in router.prompt
    assert "docs/STORIES.md" in router.prompt
    assert "Do not implement payments in this version." in prd.guardrails
    assert "Do not implement user accounts in this version." in prd.guardrails
    assert "Do not implement no login in this version." in prd.guardrails


@pytest.mark.asyncio
async def test_planner_falls_back_to_model_when_repo_docs_do_not_define_backlog(tmp_path):
    (tmp_path / ".forgegod").mkdir()
    router = FakeRouter(
        {
            "project": "tarot",
            "description": "Small app",
            "stories": [
                {
                    "id": "S001",
                    "title": "Create app shell",
                    "description": "Scaffold the app",
                    "priority": 1,
                    "acceptance_criteria": ["App shell exists"],
                }
            ],
            "guardrails": ["No secrets"],
        }
    )
    config = ForgeGodConfig(project_dir=tmp_path / ".forgegod")

    prd = await Planner(config=config, router=router).decompose(
        "Build a small app",
        project_name="tarot",
    )

    assert [story.id for story in prd.stories] == ["S001"]
    assert prd.stories[0].title == "Create app shell"
    assert prd.guardrails == ["No secrets"]


def test_planner_prioritizes_story_docs_in_repository_context(tmp_path):
    (tmp_path / ".forgegod").mkdir()
    _write(tmp_path, "README.md", "A" * 20_000)
    _write(tmp_path, "AGENTS.md", "B" * 20_000)
    _write(tmp_path, "DESIGN.md", "C" * 20_000)
    _write(
        tmp_path,
        "docs/STORIES.md",
        """# Tarot Backlog

## Milestone A

### T001 - Create app skeleton

- bootstrap the app
""",
    )
    _write(tmp_path, "docs/PRD.md", "# Tarot 3:33\n\nBuild the app from zero.")

    config = ForgeGodConfig(project_dir=tmp_path / ".forgegod")
    planner = Planner(config=config, router=FakeRouter({"stories": []}))
    context = planner._load_repository_context()

    assert "docs/STORIES.md" in context
    assert "docs/PRD.md" in context
