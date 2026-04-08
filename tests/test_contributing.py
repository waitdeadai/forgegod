"""Tests for contribution mode helpers."""

from pathlib import Path

import httpx

from forgegod.contributing import (
    ContributionContext,
    IssueCandidate,
    build_contribution_task,
    collect_contribution_context,
    default_checkout_dir,
    fetch_issue_candidates,
    parse_github_repo,
    render_contribution_brief,
)


def test_parse_github_repo():
    assert parse_github_repo("https://github.com/acme/repo") == ("acme", "repo")
    assert parse_github_repo("https://github.com/acme/repo.git") == ("acme", "repo")
    assert parse_github_repo("not-a-url") is None


def test_default_checkout_dir(tmp_path: Path):
    dest = default_checkout_dir(tmp_path, "acme", "repo")
    assert dest == tmp_path / ".forgegod" / "contribute" / "acme__repo"


def test_collect_contribution_context(tmp_path: Path):
    (tmp_path / "README.md").write_text("Read me first", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text(
        "Open an issue before large changes",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("Run tests before commit", encoding="utf-8")

    context = collect_contribution_context(tmp_path, repo_url="https://github.com/acme/repo")
    assert context.repo_name == tmp_path.name
    assert "Open an issue" in context.contributing_excerpt
    assert "Run tests" in context.agents_excerpt


def test_render_contribution_brief():
    context = ContributionContext(
        repo_name="demo",
        repo_url="https://github.com/acme/demo",
        local_path="/tmp/demo",
        contributing_excerpt="Discuss changes first.",
        issue_candidates=[
            IssueCandidate(number=12, title="Add tests", url="https://github.com/acme/demo/issues/12")
        ],
    )
    brief = render_contribution_brief(context)
    assert "CONTRIBUTING.md" in brief
    assert "#12: Add tests" in brief


def test_build_contribution_task_mentions_rules():
    context = ContributionContext(repo_name="demo", local_path="/tmp/demo")
    task = build_contribution_task(context, goal="Improve docs")
    assert "Improve docs" in task
    assert "Read and follow CONTRIBUTING.md" in task


def test_fetch_issue_candidates(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "Good first issue",
                    "html_url": "https://github.com/acme/demo/issues/1",
                    "labels": [{"name": "good first issue"}],
                    "body": "A small fix",
                }
            ],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    issues = fetch_issue_candidates("acme", "demo", limit=2)
    assert len(issues) == 1
    assert issues[0].number == 1
