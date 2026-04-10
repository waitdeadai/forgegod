"""ForgeGod planner - task decomposition from natural language to PRD."""

from __future__ import annotations

import logging
import re

from forgegod.config import ForgeGodConfig
from forgegod.json_utils import extract_json
from forgegod.models import PRD, DebateResult, ResearchBrief, Story, StoryStatus
from forgegod.router import ModelRouter
from forgegod.terse import RECON_PLANNER_PROMPT, TERSE_PLANNER_PROMPT

logger = logging.getLogger("forgegod.planner")


class Planner:
    """Decomposes a high-level task into stories (PRD) for the Ralph loop."""

    def __init__(self, config: ForgeGodConfig, router: ModelRouter | None = None):
        self.config = config
        self.router = router or ModelRouter(config)

    async def decompose(self, task: str, project_name: str = "project") -> PRD:
        """Break a task description into an ordered list of stories."""
        repo_context = self._load_repository_context()
        seeded_prd = self._seed_prd_from_repository_docs(
            repo_context=repo_context,
            project_name=project_name,
            task=task,
        )

        if self.config.terse.enabled:
            prompt = TERSE_PLANNER_PROMPT.format(
                task=task,
                project_name=project_name,
            )
        else:
            prompt = self._build_planner_prompt(
                task=task,
                project_name=project_name,
                repo_context=repo_context,
                seeded_prd=seeded_prd,
            )

        response, _ = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=8192,
            temperature=0.3,
        )

        parsed = self._parse_prd(response, project_name, task)
        return self._merge_seeded_prd(seeded_prd, parsed)

    def _build_planner_prompt(
        self,
        task: str,
        project_name: str,
        repo_context: dict[str, str],
        seeded_prd: PRD | None,
    ) -> str:
        repo_text = self._format_repository_context(repo_context, seeded_prd)
        return f"""You are a senior software architect. Decompose the following task into
ordered implementation stories. Each story should be independently testable.

## Task
{task}

{repo_text}

## Output Format (JSON)
{{
  "project": "{project_name}",
  "description": "Brief project description",
  "stories": [
    {{
      "id": "S001",
      "title": "Short title",
      "description": "What to implement",
      "priority": 1,
      "acceptance_criteria": ["Criterion 1", "Criterion 2"]
    }}
  ],
  "guardrails": ["Rule 1", "Rule 2"]
}}

## Rules
- Order stories by dependency (earlier stories should be prerequisites for later ones)
- Keep stories small (1-3 files each, ~30-60 min of work)
- Each story must have clear, testable acceptance criteria
- Repository docs are source of truth when present. Preserve the repo-defined backlog.
- If docs/STORIES.md defines story IDs, titles, or order, reuse them.
- If docs/PRD.md or docs/README.md define non-goals, do not create stories for them.
- Do not invent auth, payments, subscriptions, databases, admin panels,
  or runtime AI unless the repository docs explicitly require them.
- Include guardrails (things the agent should NEVER do)
- Priority 1 = highest (do first), ascending numbers = lower priority
- Maximum 20 stories
- IDs: S001, S002, etc.

Output ONLY valid JSON, no markdown fences, no explanations."""

    def _parse_prd(self, response: str, project_name: str, task: str) -> PRD:
        """Parse LLM response into PRD model."""
        try:
            data = extract_json(response)
        except ValueError:
            logger.warning("Failed to parse planner output, creating single-story PRD")
            return PRD(
                project=project_name,
                description=task,
                stories=[
                    Story(
                        id="S001",
                        title="Implement task",
                        description=task,
                        priority=1,
                        acceptance_criteria=["Task is complete"],
                    )
                ],
            )

        stories: list[Story] = []
        for raw_story in data.get("stories", []):
            stories.append(
                Story(
                    id=raw_story.get("id", f"S{len(stories)+1:03d}"),
                    title=raw_story.get("title", "Untitled"),
                    description=raw_story.get("description", ""),
                    status=StoryStatus.TODO,
                    priority=raw_story.get("priority", len(stories) + 1),
                    acceptance_criteria=raw_story.get("acceptance_criteria", []),
                )
            )

        return PRD(
            project=data.get("project", project_name),
            description=data.get("description", task),
            stories=stories,
            guardrails=data.get("guardrails", []),
        )

    async def research_and_decompose(
        self, task: str, project_name: str = "project",
    ) -> tuple[PRD, ResearchBrief, DebateResult]:
        """Full Recon pipeline: research -> plan -> debate -> approved PRD."""
        from forgegod.adversary import Adversary
        from forgegod.researcher import Researcher

        logger.info("Recon Phase 1: researching...")
        researcher = Researcher(self.config, self.router)
        brief = await researcher.research(task)

        logger.info("Recon Phase 2: planning with research context...")
        prd = await self._decompose_with_research(task, project_name, brief)

        logger.info("Recon Phase 3: adversarial debate...")
        adversary = Adversary(self.config, self.router)
        debate = await adversary.debate(prd, brief)

        try:
            from forgegod.memory import Memory
            from forgegod.memory_agent import MemoryAgent

            memory = Memory(self.config)
            memory_agent = MemoryAgent(self.config, self.router, memory)
            await memory_agent.process_planning_task(
                task_description=task,
                libraries=[library.name for library in brief.libraries],
                patterns=brief.architecture_patterns[:5],
                warnings=brief.security_warnings[:5],
                score=debate.final_score,
                converged=debate.converged,
                rounds=debate.rounds,
            )
        except Exception as exc:  # pragma: no cover - non-critical learning path
            logger.debug("Planning memory extraction skipped: %s", exc)

        return prd, brief, debate

    async def _decompose_with_research(
        self, task: str, project_name: str, brief: ResearchBrief,
    ) -> PRD:
        """Generate a PRD enriched with research findings."""
        repo_context = self._load_repository_context()
        seeded_prd = self._seed_prd_from_repository_docs(
            repo_context=repo_context,
            project_name=project_name,
            task=task,
        )
        repo_text = self._format_repository_context(repo_context, seeded_prd)
        research_context = repo_text + "\n\n" + self._format_brief(brief)

        prompt = RECON_PLANNER_PROMPT.format(
            task=task,
            project_name=project_name,
            research_context=research_context,
        )

        response, _ = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=8192,
            temperature=0.3,
        )

        parsed = self._parse_prd(response, project_name, task)
        return self._merge_seeded_prd(seeded_prd, parsed)

    @staticmethod
    def _format_brief(brief: ResearchBrief) -> str:
        """Format ResearchBrief as readable text for prompt injection."""
        sections: list[str] = []

        if brief.libraries:
            lines = ["### Recommended Libraries"]
            for library in brief.libraries:
                line = f"- **{library.name}** v{library.version}: {library.why}"
                if library.alternatives:
                    line += f" (alternatives: {', '.join(library.alternatives)})"
                if library.caveats:
                    line += f" | caveats: {library.caveats}"
                lines.append(line)
            sections.append("\n".join(lines))

        if brief.architecture_patterns:
            sections.append(
                "### Architecture Patterns\n"
                + "\n".join(f"- {pattern}" for pattern in brief.architecture_patterns)
            )

        if brief.security_warnings:
            sections.append(
                "### Security Warnings\n"
                + "\n".join(f"- {warning}" for warning in brief.security_warnings)
            )

        if brief.best_practices:
            sections.append(
                "### Best Practices\n"
                + "\n".join(f"- {practice}" for practice in brief.best_practices)
            )

        if brief.prior_art:
            sections.append(
                "### Prior Art\n" + "\n".join(f"- {item}" for item in brief.prior_art)
            )

        return "\n\n".join(sections) if sections else "No research findings available."

    async def refine_story(self, story: Story, context: str = "") -> Story:
        """Add more detail to a story if needed."""
        if story.acceptance_criteria and story.description:
            return story

        prompt = f"""Refine this story with more detail:

Title: {story.title}
Description: {story.description}
{f"Context: {context}" if context else ""}

Output JSON:
{{
  "description": "Detailed description",
  "acceptance_criteria": ["Criterion 1", "Criterion 2", "Criterion 3"]
}}

Output ONLY valid JSON."""

        response, _ = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=1024,
            temperature=0.3,
        )

        try:
            data = extract_json(response)
            story.description = data.get("description", story.description)
            story.acceptance_criteria = data.get(
                "acceptance_criteria", story.acceptance_criteria
            )
        except (ValueError, AttributeError):
            pass

        return story

    def _load_repository_context(self) -> dict[str, str]:
        """Load bounded repo docs so planning can respect local source-of-truth files."""
        repo_root = self.config.project_dir.parent
        max_chars = max(2_000, self.config.security.max_rules_file_chars)
        remaining = max_chars
        context: dict[str, str] = {}
        candidates = [
            "docs/STORIES.md",
            "docs/PRD.md",
            "docs/ARCHITECTURE.md",
            "docs/DESIGN.md",
            "docs/RUNBOOK.md",
            "docs/README.md",
            "README.md",
            "AGENTS.md",
            "DESIGN.md",
        ]
        per_file_cap = max(1_000, max_chars // 5)

        for rel_path in candidates:
            if remaining <= 0:
                break
            path = repo_root / rel_path
            if not path.exists() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if not text:
                continue
            snippet = text[:min(remaining, per_file_cap)]
            context[rel_path] = snippet
            remaining -= len(snippet)

        return context

    def _seed_prd_from_repository_docs(
        self, repo_context: dict[str, str], project_name: str, task: str,
    ) -> PRD | None:
        """Create a deterministic PRD seed from repo docs when they define the backlog."""
        stories = self._parse_story_backlog(repo_context.get("docs/STORIES.md", ""))
        if not stories:
            return None

        prd_text = repo_context.get("docs/PRD.md", "")
        docs_readme = repo_context.get("docs/README.md", "")
        project = self._extract_first_heading(prd_text) or project_name
        description = (
            self._extract_first_paragraph(prd_text)
            or self._extract_first_paragraph(docs_readme)
            or task
        )

        return PRD(
            project=project,
            description=description,
            stories=stories,
            guardrails=self._extract_guardrails(repo_context),
        )

    @staticmethod
    def _parse_story_backlog(stories_markdown: str) -> list[Story]:
        """Parse docs/STORIES.md into an ordered PRD seed."""
        if not stories_markdown.strip():
            return []

        stories: list[Story] = []
        current_story: Story | None = None
        current_milestone = ""

        for raw_line in stories_markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("## "):
                current_milestone = line[3:].strip()
                continue

            match = re.match(r"^###\s+([A-Z]\d{3,})\s*-\s*(.+)$", line)
            if match:
                if current_story is not None:
                    stories.append(current_story)
                story_id, title = match.groups()
                description = title.strip()
                if current_milestone:
                    description = f"{current_milestone}: {description}"
                current_story = Story(
                    id=story_id,
                    title=title.strip(),
                    description=description,
                    status=StoryStatus.TODO,
                    priority=len(stories) + 1,
                    acceptance_criteria=[],
                )
                continue

            if current_story is None:
                continue

            if line.startswith("- "):
                current_story.acceptance_criteria.append(line[2:].strip())

        if current_story is not None:
            stories.append(current_story)

        return stories

    def _extract_guardrails(self, repo_context: dict[str, str]) -> list[str]:
        """Turn repo non-goals into explicit planner guardrails."""
        prd_text = repo_context.get("docs/PRD.md", "")
        docs_readme = repo_context.get("docs/README.md", "")
        guardrails: list[str] = []

        for heading in ("## v1 Non-Goals", "## v1 Constraint"):
            for source in (prd_text, docs_readme):
                for item in self._extract_bullet_section(source, heading):
                    guardrails.append(f"Do not implement {item} in this version.")

        if "No runtime AI in v1" in prd_text:
            guardrails.append("Do not add runtime AI calls inside the app in v1.")
        if "Free first" in prd_text:
            guardrails.append("Keep v1 free unless the repository docs are explicitly updated.")

        deduped: list[str] = []
        seen: set[str] = set()
        for rule in guardrails:
            normalized = rule.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    @staticmethod
    def _extract_bullet_section(text: str, heading: str) -> list[str]:
        if not text or heading not in text:
            return []

        items: list[str] = []
        capture = False
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if line.startswith("## "):
                if capture:
                    break
                capture = line.strip() == heading
                continue
            if capture and line.strip().startswith("- "):
                items.append(line.strip()[2:].strip())
        return items

    @staticmethod
    def _extract_first_heading(text: str) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    @staticmethod
    def _extract_first_paragraph(text: str) -> str:
        paragraph: list[str] = []
        body_started = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("# "):
                body_started = True
                continue
            if not body_started:
                continue
            if not line:
                if paragraph:
                    break
                continue
            if line.startswith("#"):
                if paragraph:
                    break
                continue
            paragraph.append(line)
        return " ".join(paragraph).strip()

    @staticmethod
    def _format_repository_context(
        repo_context: dict[str, str], seeded_prd: PRD | None,
    ) -> str:
        sections: list[str] = []

        if seeded_prd and seeded_prd.stories:
            seed_lines = ["## Repository Backlog Seed"]
            for story in seeded_prd.stories:
                seed_lines.append(f"- {story.id}: {story.title}")
            sections.append("\n".join(seed_lines))

        if repo_context:
            context_lines = ["## Repository Source of Truth"]
            for rel_path, content in repo_context.items():
                context_lines.append(f"### {rel_path}\n{content}")
            sections.append("\n\n".join(context_lines))

        return "\n\n".join(sections)

    @staticmethod
    def _merge_seeded_prd(seeded_prd: PRD | None, parsed_prd: PRD) -> PRD:
        """Keep repo-backed stories authoritative and use model output only to fill gaps."""
        if seeded_prd is None or not seeded_prd.stories:
            return parsed_prd

        parsed_by_id = {story.id.lower(): story for story in parsed_prd.stories}
        parsed_by_title = {
            Planner._normalize_story_key(story.title): story for story in parsed_prd.stories
        }
        seeded_ids = {story.id for story in seeded_prd.stories}

        merged_stories: list[Story] = []
        for seeded_story in seeded_prd.stories:
            match = parsed_by_id.get(seeded_story.id.lower()) or parsed_by_title.get(
                Planner._normalize_story_key(seeded_story.title)
            )
            merged = seeded_story.model_copy(deep=True)
            if match is not None:
                if not merged.description and match.description:
                    merged.description = match.description
                if not merged.acceptance_criteria and match.acceptance_criteria:
                    merged.acceptance_criteria = match.acceptance_criteria
                if match.depends_on:
                    merged.depends_on = [
                        dependency for dependency in match.depends_on if dependency in seeded_ids
                    ]
            merged_stories.append(merged)

        guardrails = seeded_prd.guardrails[:]
        for rule in parsed_prd.guardrails:
            if rule not in guardrails:
                guardrails.append(rule)

        return PRD(
            project=seeded_prd.project or parsed_prd.project,
            description=seeded_prd.description or parsed_prd.description,
            stories=merged_stories,
            guardrails=guardrails,
            learnings=parsed_prd.learnings,
        )

    @staticmethod
    def _normalize_story_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
