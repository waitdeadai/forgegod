"""ForgeGod contribution-mode helpers.

Contribution mode reads repository contribution guidance, optionally discovers
approachable GitHub issues, and prepares a repo-specific task brief so the
planner/agent can contribute without ignoring maintainer rules.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import httpx
from pydantic import BaseModel, Field


class IssueCandidate(BaseModel):
    number: int
    title: str
    url: str
    labels: list[str] = Field(default_factory=list)
    body_excerpt: str = ""


class ContributionContext(BaseModel):
    repo_name: str
    repo_url: str = ""
    local_path: str = ""
    readme_excerpt: str = ""
    contributing_excerpt: str = ""
    agents_excerpt: str = ""
    issue_candidates: list[IssueCandidate] = Field(default_factory=list)


def parse_github_repo(target: str) -> tuple[str, str] | None:
    """Parse https://github.com/owner/repo(.git) into (owner, repo)."""
    match = re.match(r"^https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", target.strip())
    if not match:
        return None
    owner, repo = match.groups()
    return owner, repo


def default_checkout_dir(base_dir: Path, owner: str, repo: str) -> Path:
    """Return the default local checkout path for a remote contribution target."""
    return base_dir.resolve() / ".forgegod" / "contribute" / f"{owner}__{repo}"


def ensure_target_checkout(target: str, checkout_dir: Path | None = None) -> tuple[Path, str]:
    """Resolve a local repo path or clone a GitHub repo URL when needed."""
    parsed = parse_github_repo(target)
    if not parsed:
        path = Path(target).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Target path not found: {path}")
        return path, ""

    owner, repo = parsed
    dest = checkout_dir or default_checkout_dir(Path.cwd(), owner, repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    repo_url = f"https://github.com/{owner}/{repo}"
    if not dest.exists():
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"git clone failed for {repo_url}: {(proc.stderr or proc.stdout).strip()}"
            )
    return dest.resolve(), repo_url


def fetch_issue_candidates(
    owner: str,
    repo: str,
    *,
    labels: tuple[str, ...] = ("good first issue", "help wanted"),
    limit: int = 5,
    timeout: float = 20.0,
) -> list[IssueCandidate]:
    """Fetch open issues labeled as approachable contribution targets."""
    results: list[IssueCandidate] = []
    seen: set[int] = set()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "forgegod",
    }

    for label in labels:
        resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            params={"state": "open", "labels": label, "per_page": str(limit)},
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        for item in resp.json():
            if "pull_request" in item:
                continue
            number = int(item.get("number", 0))
            if number in seen:
                continue
            seen.add(number)
            results.append(IssueCandidate(
                number=number,
                title=item.get("title", ""),
                url=item.get("html_url", ""),
                labels=[lbl.get("name", "") for lbl in item.get("labels", []) if lbl.get("name")],
                body_excerpt=(item.get("body") or "")[:700],
            ))
            if len(results) >= limit:
                return results
    return results


def _read_first_existing(base: Path, candidates: list[str], max_chars: int = 6000) -> str:
    for rel in candidates:
        path = base / rel
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return ""


def collect_contribution_context(
    repo_path: Path | str,
    *,
    repo_url: str = "",
    issue_candidates: list[IssueCandidate] | None = None,
) -> ContributionContext:
    """Collect local repo docs and optional issue candidates."""
    path = Path(repo_path).resolve()
    return ContributionContext(
        repo_name=path.name,
        repo_url=repo_url,
        local_path=str(path),
        readme_excerpt=_read_first_existing(path, ["README.md", "README.rst"]),
        contributing_excerpt=_read_first_existing(
            path,
            [
                "CONTRIBUTING.md",
                ".github/CONTRIBUTING.md",
                "docs/CONTRIBUTING.md",
            ],
        ),
        agents_excerpt=_read_first_existing(
            path,
            [
                "AGENTS.md",
                ".forgegod/rules.md",
                ".github/copilot-instructions.md",
            ],
        ),
        issue_candidates=issue_candidates or [],
    )


def render_contribution_brief(context: ContributionContext) -> str:
    """Format contribution context for prompt injection."""
    sections = [
        "## Contribution Context",
        f"Repository: {context.repo_name}",
        f"Local path: {context.local_path}",
    ]
    if context.repo_url:
        sections.append(f"GitHub: {context.repo_url}")
    if context.contributing_excerpt:
        sections.append(
            "### CONTRIBUTING.md\n"
            + context.contributing_excerpt
        )
    if context.agents_excerpt:
        sections.append(
            "### Repo Agent Rules\n"
            + context.agents_excerpt
        )
    if context.readme_excerpt:
        sections.append(
            "### README Excerpt\n"
            + context.readme_excerpt
        )
    if context.issue_candidates:
        lines = ["### Suggested Issues"]
        for issue in context.issue_candidates:
            labels = ", ".join(issue.labels) if issue.labels else "no labels"
            lines.append(f"- #{issue.number}: {issue.title} ({labels})")
            if issue.url:
                lines.append(f"  {issue.url}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def build_contribution_task(
    context: ContributionContext,
    *,
    goal: str = "",
    issue_number: int | None = None,
) -> str:
    """Build the planner/agent task text for contribution mode."""
    focus = goal.strip() or (
        "Identify the highest-value contribution that fits the repo guidelines, "
        "prefer a small issue or docs/tests improvement, and avoid speculative large refactors."
    )
    issue_hint = ""
    if issue_number is not None:
        issue_hint = (
            f"\nPrioritize issue #{issue_number} if it is present in the suggested "
            "issue list."
        )
    return (
        f"{render_contribution_brief(context)}\n\n"
        "## Contribution Goal\n"
        f"{focus}{issue_hint}\n\n"
        "## Contribution Rules\n"
        "- Read and follow CONTRIBUTING.md before proposing work.\n"
        "- Prefer issues labeled good first issue or help wanted when available.\n"
        "- Prefer tests, docs, or tightly scoped bug fixes over broad rewrites.\n"
        "- If proposing a feature, align with existing architecture and maintainer guidance.\n"
        "- Do not push or open a PR automatically unless the user explicitly asks."
    )
