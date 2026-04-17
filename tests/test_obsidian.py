from __future__ import annotations

import json
import subprocess

import pytest
import toml
from typer.testing import CliRunner

from forgegod.cli import app
from forgegod.config import ForgeGodConfig
from forgegod.hive import HiveCoordinator, HiveWorker
from forgegod.memory import Memory
from forgegod.memory_agent import MemoryAgent
from forgegod.models import (
    PRD,
    AgentResult,
    HiveWorkerResult,
    LibraryRecommendation,
    ModelUsage,
    ResearchBrief,
    Story,
    StoryStatus,
)
from forgegod.obsidian import ObsidianAdapter
from forgegod.researcher import Researcher

runner = CliRunner()


class DummyRouter:
    async def close(self):
        return None


class FakeMemoryRouter:
    async def call(self, **_kwargs):
        payload = {
            "semantic": [
                {
                    "text": "Prefer projected knowledge over replacing runtime memory",
                    "category": "architecture",
                    "confidence": 0.81,
                }
            ],
            "procedural": [
                {
                    "name": "Projection first",
                    "trigger": "When integrating human-readable knowledge surfaces",
                    "action": "Keep SQLite hot-path memory and export durable notes",
                    "pattern_type": "recipe",
                }
            ],
            "error_solutions": [
                {
                    "error_pattern": "vault not configured",
                    "solution": "Run forgegod obsidian init with a vault path",
                    "context": "obsidian integration",
                }
            ],
            "causal_edges": [
                {"factor": "projection-first architecture", "outcome": "success", "weight": 0.77}
            ],
        }
        return json.dumps(payload), ModelUsage(model="openai:gpt-5.4-mini")


def _obsidian_config(tmp_path) -> ForgeGodConfig:
    config = ForgeGodConfig()
    config.project_dir = tmp_path / ".forgegod"
    config.project_dir.mkdir(parents=True, exist_ok=True)
    config.obsidian.enabled = True
    config.obsidian.vault_path = str((tmp_path / "vault").resolve())
    return config


@pytest.mark.asyncio
async def test_obsidian_adapter_exports_research_and_memory_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("forgegod.memory.Path.home", lambda: tmp_path / "home")

    config = _obsidian_config(tmp_path)
    adapter = ObsidianAdapter(config)

    brief = ResearchBrief(
        task="Integrate Obsidian into ForgeGod",
        libraries=[
            LibraryRecommendation(
                name="obsidian-cli",
                version="official",
                why="Use the first-party CLI when available",
            )
        ],
        architecture_patterns=["projection-first knowledge surface"],
        security_warnings=["Never export provider secrets into the vault"],
        best_practices=["Keep runtime memory in SQLite"],
        prior_art=["Markdown-native operator dashboards"],
    )
    research_path = adapter.export_research_brief(brief, depth="sota")
    assert research_path is not None
    assert research_path.exists()
    assert "projection-first knowledge surface" in research_path.read_text(encoding="utf-8")

    memory = Memory(config)
    await memory.add_semantic(
        text="Project stable memories into Obsidian instead of replacing SQLite retrieval",
        category="architecture",
        confidence=0.92,
        source_episode="T001",
    )
    await memory.add_procedure(
        name="Projection first",
        description="Export stable principles to a vault after tasks complete",
        pattern_type="recipe",
        trigger="When adding a human-readable knowledge surface",
        action="Keep runtime recall in SQLite and export durable notes",
        source_episode="T001",
    )

    exported = await adapter.export_memory_projection(memory, limit=10)
    assert any(path.name == "memory-overview.md" for path in exported)
    assert any(path.parent.name == "Patterns" for path in exported)


@pytest.mark.asyncio
async def test_researcher_auto_exports_note_when_obsidian_enabled(tmp_path):
    config = _obsidian_config(tmp_path)
    researcher = Researcher(config, DummyRouter())

    async def fake_generate_queries(*_args, **_kwargs):
        return []

    async def fake_execute_searches(*_args, **_kwargs):
        return []

    async def fake_fetch_top_results(results, **_kwargs):
        return results

    async def fake_check_pypi(_task, results):
        return results

    async def fake_synthesize(task, _results):
        return ResearchBrief(
            task=task,
            architecture_patterns=["manager + projection pattern"],
            best_practices=["export durable summaries for operators"],
        )

    researcher._generate_queries = fake_generate_queries
    researcher._execute_searches = fake_execute_searches
    researcher._fetch_top_results = fake_fetch_top_results
    researcher._check_pypi = fake_check_pypi
    researcher._synthesize = fake_synthesize

    await researcher.research("Integrate Obsidian", depth=None)

    research_dir = tmp_path / "vault" / "ForgeGod" / "Research"
    assert any(research_dir.glob("*.md"))


@pytest.mark.asyncio
async def test_memory_agent_exports_summary_note(tmp_path, monkeypatch):
    monkeypatch.setattr("forgegod.memory.Path.home", lambda: tmp_path / "home")

    config = _obsidian_config(tmp_path)
    memory = Memory(config)
    agent = MemoryAgent(config, FakeMemoryRouter(), memory)

    result = AgentResult(
        success=True,
        output="Integrated the projection layer.",
        files_modified=["forgegod/obsidian.py"],
        total_usage=ModelUsage(model="openai:gpt-5.4-mini", cost_usd=0.01, elapsed_s=1.0),
    )

    await agent.process_coding_task("Integrate Obsidian export layer", result, task_id="T123")

    summary_note = tmp_path / "vault" / "ForgeGod" / "Stories" / "t123-memory-summary.md"
    assert summary_note.exists()
    content = summary_note.read_text(encoding="utf-8")
    assert "Projection first" in content
    assert "vault not configured" in content


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_hive_exports_latest_summary_note(tmp_path):
    if not _git_available():
        pytest.skip("git is required for hive worktree tests")

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    config = ForgeGodConfig()
    config.project_dir = repo / ".forgegod"
    config.project_dir.mkdir(parents=True, exist_ok=True)
    config.audit.enabled = False
    config.obsidian.enabled = True
    config.obsidian.vault_path = str((tmp_path / "vault").resolve())
    (config.project_dir / "config.toml").write_text(
        toml.dumps(config.model_dump(mode="json", exclude={"global_dir", "project_dir"})),
        encoding="utf-8",
    )

    prd_path = config.project_dir / "prd.json"
    prd = PRD(
        project="Hive Obsidian Test",
        stories=[Story(id="T001", title="Create app file", status=StoryStatus.TODO)],
    )
    prd_path.write_text(prd.model_dump_json(indent=2), encoding="utf-8")

    async def fake_runner(worker: HiveWorker) -> HiveWorkerResult:
        target = worker.worktree_path / "src" / "app.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("print('hive')\n", encoding="utf-8")
        return HiveWorkerResult(
            story_id=worker.story_id,
            success=True,
            exit_code=0,
            files_modified=["src/app.py"],
        )

    coordinator = HiveCoordinator(config=config, worker_runner=fake_runner)
    await coordinator.run(prd_path, max_iterations=1, max_workers=1, dry_run=False)

    summary = tmp_path / "vault" / "ForgeGod" / "Runs" / "hive-latest.md"
    assert summary.exists()
    assert "stories_completed=1" in summary.read_text(encoding="utf-8")


def test_obsidian_init_command_updates_config_and_layout(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    vault = tmp_path / "vault"
    result = runner.invoke(app, ["obsidian", "init", "--vault", str(vault)])

    assert result.exit_code == 0
    config_path = workspace / ".forgegod" / "config.toml"
    data = toml.loads(config_path.read_text(encoding="utf-8"))
    assert data["obsidian"]["enabled"] is True
    assert data["obsidian"]["vault_path"] == str(vault.resolve())
    assert (vault / "ForgeGod" / "Dashboard" / "overview.md").exists()
