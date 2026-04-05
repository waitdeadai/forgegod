"""ForgeGod Planner — task decomposition from natural language to PRD."""

from __future__ import annotations

import logging

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
        """Break a task description into an ordered list of stories.

        Uses the planner model to analyze the task and produce stories
        with acceptance criteria, ordered by dependency.
        """
        if self.config.terse.enabled:
            prompt = TERSE_PLANNER_PROMPT.format(
                task=task,
                project_name=project_name,
            )
        else:
            prompt = f"""You are a senior software architect. Decompose the following task into
ordered implementation stories. Each story should be independently testable.

## Task
{task}

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
- Include guardrails (things the agent should NEVER do)
- Priority 1 = highest (do first), ascending numbers = lower priority
- Maximum 20 stories
- IDs: S001, S002, etc.

Output ONLY valid JSON, no markdown fences, no explanations."""

        response, _ = await self.router.call(
            prompt=prompt,
            role="planner",
            json_mode=True,
            max_tokens=8192,
            temperature=0.3,
        )

        return self._parse_prd(response, project_name, task)

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

        stories = []
        for s in data.get("stories", []):
            stories.append(
                Story(
                    id=s.get("id", f"S{len(stories)+1:03d}"),
                    title=s.get("title", "Untitled"),
                    description=s.get("description", ""),
                    status=StoryStatus.TODO,
                    priority=s.get("priority", len(stories) + 1),
                    acceptance_criteria=s.get("acceptance_criteria", []),
                )
            )

        return PRD(
            project=data.get("project", project_name),
            description=data.get("description", task),
            stories=stories,
            guardrails=data.get("guardrails", []),
        )

    # ── Recon Pipeline ──

    async def research_and_decompose(
        self, task: str, project_name: str = "project",
    ) -> tuple[PRD, ResearchBrief, DebateResult]:
        """Full Recon pipeline: research → plan → debate → approved PRD."""
        from forgegod.adversary import Adversary
        from forgegod.researcher import Researcher

        # Phase 1: RECON — web intelligence gathering
        logger.info("Recon Phase 1: researching...")
        researcher = Researcher(self.config, self.router)
        brief = await researcher.research(task)

        # Phase 2: ARCHITECT — research-grounded planning
        logger.info("Recon Phase 2: planning with research context...")
        prd = await self._decompose_with_research(task, project_name, brief)

        # Phase 3: ADVERSARY — debate loop
        logger.info("Recon Phase 3: adversarial debate...")
        adversary = Adversary(self.config, self.router)
        debate = await adversary.debate(prd, brief)

        # Phase 4: MEMORY — extract planning learnings
        try:
            from forgegod.memory import Memory
            from forgegod.memory_agent import MemoryAgent

            memory = Memory(self.config)
            ma = MemoryAgent(self.config, self.router, memory)
            await ma.process_planning_task(
                task_description=task,
                libraries=[lib.name for lib in brief.libraries],
                patterns=brief.architecture_patterns[:5],
                warnings=brief.security_warnings[:5],
                score=debate.final_score,
                converged=debate.converged,
                rounds=debate.rounds,
            )
        except Exception as e:
            logger.debug(f"Planning memory extraction skipped: {e}")

        return prd, brief, debate

    async def _decompose_with_research(
        self, task: str, project_name: str, brief: ResearchBrief,
    ) -> PRD:
        """Generate PRD enriched with research findings."""
        research_context = self._format_brief(brief)

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

        return self._parse_prd(response, project_name, task)

    @staticmethod
    def _format_brief(brief: ResearchBrief) -> str:
        """Format ResearchBrief as readable text for prompt injection."""
        sections = []

        if brief.libraries:
            lines = ["### Recommended Libraries"]
            for lib in brief.libraries:
                line = f"- **{lib.name}** v{lib.version}: {lib.why}"
                if lib.alternatives:
                    line += f" (alternatives: {', '.join(lib.alternatives)})"
                if lib.caveats:
                    line += f" ⚠ {lib.caveats}"
                lines.append(line)
            sections.append("\n".join(lines))

        if brief.architecture_patterns:
            sections.append("### Architecture Patterns\n" + "\n".join(
                f"- {p}" for p in brief.architecture_patterns
            ))

        if brief.security_warnings:
            sections.append("### Security Warnings\n" + "\n".join(
                f"- ⚠ {w}" for w in brief.security_warnings
            ))

        if brief.best_practices:
            sections.append("### Best Practices\n" + "\n".join(
                f"- {bp}" for bp in brief.best_practices
            ))

        if brief.prior_art:
            sections.append("### Prior Art\n" + "\n".join(
                f"- {pa}" for pa in brief.prior_art
            ))

        return "\n\n".join(sections) if sections else "No research findings available."

    async def refine_story(self, story: Story, context: str = "") -> Story:
        """Add more detail to a story if needed."""
        if story.acceptance_criteria and story.description:
            return story

        prompt = f"""Refine this story with more detail:

Title: {story.title}
Description: {story.description}
{f'Context: {context}' if context else ''}

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
