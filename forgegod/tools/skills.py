"""ForgeGod Skills — on-demand loading of task-specific instructions.

Inspired by OpenClaw's Skills system (Steinberger, 2025):
- Skills are directories with a SKILL.md file containing instructions
- Only a compact list (name + description) is injected into system prompt
- The agent reads the full SKILL.md on-demand via this tool
- This saves massive context vs injecting all skills upfront

Skill directories live at .forgegod/skills/{skill_name}/SKILL.md
"""

from __future__ import annotations

import os
from pathlib import Path

from forgegod.tools import register_tool


def _get_skills_dir() -> Path:
    return Path.cwd() / ".forgegod" / "skills"


async def list_skills() -> str:
    """List all available skills with their descriptions."""
    skills_dir = _get_skills_dir()
    if not skills_dir.exists():
        return "No skills directory found. Create skills at .forgegod/skills/{name}/SKILL.md"

    skills = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue

        # Extract first line as description
        try:
            first_lines = skill_md.read_text(encoding="utf-8", errors="replace").split("\n")
            # Skip header, grab first non-empty content line
            desc = ""
            for line in first_lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:120]
                    break
            skills.append(f"  {entry.name}: {desc}")
        except OSError:
            skills.append(f"  {entry.name}: (error reading)")

    if not skills:
        return "No skills found in .forgegod/skills/"
    return f"Available skills ({len(skills)}):\n" + "\n".join(skills)


async def load_skill(name: str) -> str:
    """Load the full instructions for a specific skill."""
    skills_dir = _get_skills_dir()
    skill_dir = skills_dir / name
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return f"Error: Skill '{name}' not found at {skill_md}"

    try:
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        # Cap at 20K chars per skill (OpenClaw pattern)
        if len(content) > 20_000:
            content = content[:20_000] + "\n\n[... truncated at 20K chars ...]"

        # Also check for example files in the skill directory
        examples = []
        for f in sorted(skill_dir.iterdir()):
            if f.name != "SKILL.md" and f.is_file() and f.suffix in (".py", ".ts", ".js", ".sh"):
                examples.append(f.name)

        result = f"[Skill: {name}]\n\n{content}"
        if examples:
            result += f"\n\nExample files available: {', '.join(examples)}"
        return result
    except OSError as e:
        return f"Error loading skill '{name}': {e}"


def get_skills_summary() -> str:
    """Get a compact skills list for system prompt injection.

    Only names + one-line descriptions — NOT full content.
    The agent reads full content on-demand via load_skill().
    """
    skills_dir = _get_skills_dir()
    if not skills_dir.exists():
        return ""

    entries = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            first_line = ""
            for line in skill_md.read_text(encoding="utf-8", errors="replace").split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    first_line = line[:80]
                    break
            entries.append(f"- `{entry.name}`: {first_line}")
        except OSError:
            continue

    if not entries:
        return ""
    return (
        "\n\n## Skills (use `load_skill(name)` for full instructions)\n"
        + "\n".join(entries)
    )


# ── Register tools ──

register_tool(
    name="list_skills",
    description="List all available ForgeGod skills with descriptions.",
    parameters={"type": "object", "properties": {}},
    handler=list_skills,
)

register_tool(
    name="load_skill",
    description="Load the full instructions for a specific skill. Use list_skills first to see available skills.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name to load"},
        },
        "required": ["name"],
    },
    handler=load_skill,
)
