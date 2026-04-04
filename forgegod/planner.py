"""ForgeGod Planner — task decomposition from natural language to PRD."""

from __future__ import annotations

import json
import logging

from forgegod.config import ForgeGodConfig
from forgegod.models import PRD, Story, StoryStatus
from forgegod.router import ModelRouter
from forgegod.terse import TERSE_PLANNER_PROMPT

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
            max_tokens=4096,
            temperature=0.3,
        )

        return self._parse_prd(response, project_name, task)

    def _parse_prd(self, response: str, project_name: str, task: str) -> PRD:
        """Parse LLM response into PRD model."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                # Fallback: create single-story PRD
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
            data = json.loads(response)
            story.description = data.get("description", story.description)
            story.acceptance_criteria = data.get(
                "acceptance_criteria", story.acceptance_criteria
            )
        except json.JSONDecodeError:
            pass

        return story
