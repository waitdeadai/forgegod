"""Optional Obsidian vault integration for ForgeGod.

Projection-first design:
- runtime memory remains in SQLite
- durable artifacts are exported to a Markdown vault
- the official Obsidian CLI is detected but not required
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forgegod.config import ForgeGodConfig
from forgegod.models import (
    PRD,
    DeepResearchBrief,
    HiveState,
    LoopState,
    Principle,
    ResearchBrief,
    Story,
)


class ObsidianAdapter:
    """Project ForgeGod knowledge into an Obsidian vault."""

    _FOLDERS = (
        "Dashboard",
        "Research",
        "Patterns",
        "Errors",
        "Runs",
        "Stories",
    )

    def __init__(self, config: ForgeGodConfig):
        self.config = config
        self.obsidian = config.obsidian

    def is_configured(self) -> bool:
        return bool(str(self.obsidian.vault_path).strip())

    def is_enabled(self) -> bool:
        return bool(self.obsidian.enabled and self.is_configured())

    def cli_available(self) -> bool:
        command = str(self.obsidian.cli_command).strip()
        return bool(command and shutil.which(command))

    def vault_path(self) -> Path:
        raw = Path(self.obsidian.vault_path).expanduser()
        if raw.is_absolute():
            return raw
        return (self.config.project_dir.parent / raw).resolve()

    def export_root(self) -> Path:
        return self.vault_path() / self.obsidian.export_root

    def status(self) -> dict[str, Any]:
        vault = self.vault_path() if self.is_configured() else None
        return {
            "enabled": self.obsidian.enabled,
            "configured": self.is_configured(),
            "vault_path": str(vault) if vault else "",
            "vault_exists": bool(vault and vault.exists()),
            "export_root": str(self.export_root()) if vault else "",
            "mode": self.obsidian.mode,
            "cli_available": self.cli_available(),
            "write_strategy": self.obsidian.write_strategy,
        }

    def initialize_layout(self) -> Path:
        if not self.is_configured():
            raise ValueError("Obsidian vault_path is not configured")
        vault = self.vault_path()
        vault.mkdir(parents=True, exist_ok=True)
        export_root = self.export_root()
        export_root.mkdir(parents=True, exist_ok=True)
        for folder in self._FOLDERS:
            (export_root / folder).mkdir(parents=True, exist_ok=True)
        if self.obsidian.generate_dashboard:
            self._write_dashboard()
        return export_root

    def export_research_brief(
        self,
        brief: ResearchBrief,
        *,
        depth: str = "sota",
        note_title: str | None = None,
    ) -> Path | None:
        if not self.is_enabled():
            return None
        self.initialize_layout()
        title = note_title or f"Research {self._date_prefix()} {brief.task}"
        sources = self._dedupe_urls([result.url for result in brief.raw_results if result.url])
        frontmatter = {
            "type": "research",
            "project": self._project_name(),
            "status": "captured",
            "depth": depth,
            "search_count": brief.search_count,
            "updated_at": self._now(),
            "tags": ["forgegod", "research", depth],
            "sources": sources[:12],
        }
        sections = [
            ("Task", brief.task),
            (
                "Libraries",
                self._bullets(
                    f"{lib.name} v{lib.version or 'unspecified'}: {lib.why}".strip(": ")
                    for lib in brief.libraries
                ),
            ),
            ("Architecture Patterns", self._bullets(brief.architecture_patterns)),
            ("Security Warnings", self._bullets(brief.security_warnings)),
            ("Best Practices", self._bullets(brief.best_practices)),
            ("Prior Art", self._bullets(brief.prior_art)),
            ("Sources", self._bullets(sources)),
        ]
        return self._write_note("Research", title, frontmatter, sections)

    def export_deep_research_brief(self, brief: DeepResearchBrief) -> Path | None:
        if not self.is_enabled():
            return None
        self.initialize_layout()
        title = f"Deep Research {self._date_prefix()} {brief.story_id or brief.task}"
        source_urls = [src.url for src in brief.sources_verified if src.url]
        frontmatter = {
            "type": "deep-research",
            "project": self._project_name(),
            "story_id": brief.story_id,
            "status": "captured",
            "iterations": brief.search_iterations,
            "updated_at": self._now(),
            "tags": ["forgegod", "research", "deep"],
            "sources": self._dedupe_urls(source_urls)[:12],
        }
        competitive = [
            f"{item.competitor}: {item.technique}"
            + (f" ({item.evidence_url})" if item.evidence_url else "")
            for item in brief.competitive_intelligence
        ]
        sota_patterns = [
            f"{item.pattern_name}: {item.description}"
            + (f" ({item.evidence_url})" if item.evidence_url else "")
            for item in brief.sota_patterns
        ]
        sections = [
            ("Task", brief.task),
            ("Competitive Intelligence", self._bullets(competitive)),
            ("SOTA Patterns", self._bullets(sota_patterns)),
            ("Verified Constraints", self._bullets(brief.verified_constraints)),
            ("Sources", self._bullets(self._dedupe_urls(source_urls))),
        ]
        return self._write_note("Research", title, frontmatter, sections)

    def export_memory_extraction_summary(
        self,
        *,
        task_id: str,
        task_description: str,
        task_type: str,
        extractions: dict[str, Any],
    ) -> Path | None:
        if not self.is_enabled():
            return None
        self.initialize_layout()
        title = f"{task_id or 'task'} Memory Summary"
        frontmatter = {
            "type": "memory-summary",
            "project": self._project_name(),
            "task_id": task_id,
            "task_type": task_type,
            "status": "captured",
            "updated_at": self._now(),
            "tags": ["forgegod", "memory", task_type],
        }
        sections = [
            ("Task", task_description),
            (
                "Semantic Learnings",
                self._bullets(item.get("text", "") for item in extractions.get("semantic", [])),
            ),
            (
                "Procedural Learnings",
                self._bullets(
                    f"{item.get('name', '')}: {item.get('action', '')}".strip(": ")
                    for item in extractions.get("procedural", [])
                ),
            ),
            (
                "Error Solutions",
                self._bullets(
                    f"{item.get('error_pattern', '')}: {item.get('solution', '')}".strip(": ")
                    for item in extractions.get("error_solutions", [])
                ),
            ),
            (
                "Causal Factors",
                self._bullets(
                    f"{item.get('factor', '')} -> {item.get('outcome', '')}".strip()
                    for item in extractions.get("causal_edges", [])
                ),
            ),
        ]
        return self._write_note(
            "Stories",
            title,
            frontmatter,
            sections,
            filename_stem=f"{task_id or 'task'}-memory-summary",
        )

    async def export_memory_projection(self, memory, *, limit: int = 20) -> list[Path]:
        if not self.is_enabled():
            return []
        self.initialize_layout()
        threshold = (
            self.obsidian.min_confidence
            if self.obsidian.project_stable_memories_only
            else 0.0
        )
        principles = await memory.get_principles(min_confidence=threshold)
        procedures = await memory.get_procedures(limit=limit)
        recent = await memory.get_recent_episodes(limit=min(10, limit))
        paths: list[Path] = []

        for principle in principles[:limit]:
            paths.append(self._write_principle_note(principle))

        for procedure in procedures[:limit]:
            paths.append(self._write_procedure_note(procedure))

        summary_sections = [
            (
                "Principles",
                self._bullets(
                    f"[{item.category}] {item.text} ({item.confidence:.2f}, {item.evidence_count}x)"
                    for item in principles[:limit]
                ),
            ),
            (
                "Procedures",
                self._bullets(
                    (
                        f"{item.get('name', '')} "
                        f"({item.get('pattern_type', '')}): "
                        f"{item.get('description', '')}"
                    )
                    for item in procedures[:limit]
                ),
            ),
            (
                "Recent Episodes",
                self._bullets(
                    f"{item.get('task_id', '')}: {item.get('task_description', '')}"
                    for item in recent
                ),
            ),
        ]
        paths.append(
            self._write_note(
                "Dashboard",
                "Memory Overview",
                {
                    "type": "memory-overview",
                    "project": self._project_name(),
                    "updated_at": self._now(),
                    "tags": ["forgegod", "memory", "overview"],
                },
                summary_sections,
                filename_stem="memory-overview",
            )
        )
        self._write_dashboard()
        return paths

    def export_story_summary(
        self, story: Story, *, result=None, state: LoopState | None = None
    ) -> Path | None:
        if not self.is_enabled():
            return None
        self.initialize_layout()
        output = getattr(result, "output", "") if result else ""
        error = getattr(result, "error", "") if result else ""
        files_modified = list(
            getattr(result, "files_modified", []) or story.files_touched or []
        )
        verification_commands = list(getattr(result, "verification_commands", []) or [])
        frontmatter = {
            "type": "story-summary",
            "project": self._project_name(),
            "story_id": story.id,
            "status": self._story_status(story),
            "priority": story.priority,
            "updated_at": self._now(),
            "completed_at": story.completed_at,
            "tags": ["forgegod", "story", str(story.status)],
        }
        sections = [
            ("Title", story.title),
            ("Description", story.description or ""),
            ("Acceptance Criteria", self._bullets(story.acceptance_criteria)),
            ("Files Modified", self._bullets(files_modified)),
            ("Verification Commands", self._bullets(verification_commands)),
            ("Output", output[:4000]),
            ("Errors", self._bullets(story.error_log + ([error] if error else []))),
        ]
        if state is not None:
            sections.append(
                (
                    "Loop State",
                    self._bullets(
                        [
                            f"stories_completed={state.stories_completed}",
                            f"stories_failed={state.stories_failed}",
                            f"total_iterations={state.total_iterations}",
                            f"total_cost_usd={state.total_cost_usd:.4f}",
                        ]
                    ),
                )
            )
        return self._write_note(
            "Stories",
            f"{story.id} {story.title}",
            frontmatter,
            sections,
            filename_stem=f"{story.id}-{self._slug(story.title)}",
        )

    def export_loop_summary(self, *, prd: PRD, state: LoopState) -> Path | None:
        if not self.is_enabled():
            return None
        self.initialize_layout()
        sections = [
            ("Project", prd.project),
            ("Status", self._status_value(state.status)),
            (
                "Counts",
                self._bullets(
                    [
                        f"stories_completed={state.stories_completed}",
                        f"stories_failed={state.stories_failed}",
                        f"total_iterations={state.total_iterations}",
                        f"total_cost_usd={state.total_cost_usd:.4f}",
                    ]
                ),
            ),
            (
                "Current Batch",
                self._bullets([state.current_story_id] if state.current_story_id else []),
            ),
            (
                "Stories",
                self._bullets(self._story_line(story) for story in prd.stories),
            ),
        ]
        path = self._write_note(
            "Runs",
            "Loop Latest",
            {
                "type": "run-summary",
                "runtime": "loop",
                "project": self._project_name(),
                "status": self._status_value(state.status),
                "updated_at": self._now(),
                "tags": ["forgegod", "run", "loop"],
            },
            sections,
            filename_stem="loop-latest",
        )
        self._write_dashboard()
        return path

    def export_hive_summary(self, *, prd: PRD, state: HiveState) -> Path | None:
        if not self.is_enabled():
            return None
        self.initialize_layout()
        sections = [
            ("Project", prd.project),
            ("Status", state.status),
            (
                "Counts",
                self._bullets(
                    [
                        f"stories_completed={state.stories_completed}",
                        f"stories_failed={state.stories_failed}",
                        f"total_iterations={state.total_iterations}",
                    ]
                ),
            ),
            ("Current Batch", self._bullets(state.current_batch)),
            (
                "Stories",
                self._bullets(self._story_line(story) for story in prd.stories),
            ),
        ]
        path = self._write_note(
            "Runs",
            "Hive Latest",
            {
                "type": "run-summary",
                "runtime": "hive",
                "project": self._project_name(),
                "status": state.status,
                "updated_at": self._now(),
                "tags": ["forgegod", "run", "hive"],
            },
            sections,
            filename_stem="hive-latest",
        )
        self._write_dashboard()
        return path

    def _write_principle_note(self, principle: Principle) -> Path:
        return self._write_note(
            "Patterns",
            principle.text,
            {
                "type": "pattern",
                "pattern_kind": "semantic",
                "project": self._project_name(),
                "pattern_id": principle.principle_id,
                "category": principle.category,
                "confidence": round(principle.confidence, 3),
                "evidence_count": principle.evidence_count,
                "updated_at": self._now(),
                "tags": ["forgegod", "pattern", principle.category or "general"],
            },
            [
                ("Principle", principle.text),
                ("Source Tasks", self._bullets(principle.source_tasks)),
            ],
            filename_stem=f"{principle.principle_id}-{self._slug(principle.text)}",
        )

    def _write_procedure_note(self, procedure: dict[str, Any]) -> Path:
        return self._write_note(
            "Patterns",
            procedure.get("name", "Procedure"),
            {
                "type": "pattern",
                "pattern_kind": "procedural",
                "project": self._project_name(),
                "pattern_id": procedure.get("pattern_id", ""),
                "pattern_type": procedure.get("pattern_type", ""),
                "success_rate": round(float(procedure.get("success_rate", 0.0) or 0.0), 4),
                "usage_count": int(procedure.get("usage_count", 0) or 0),
                "updated_at": self._now(),
                "tags": ["forgegod", "pattern", procedure.get("pattern_type", "pattern")],
            },
            [
                ("Description", procedure.get("description", "")),
                ("Trigger", procedure.get("trigger", "")),
                ("Action", procedure.get("action", "")),
            ],
            filename_stem=(
                f"{procedure.get('pattern_id', 'procedure')}-"
                f"{self._slug(procedure.get('name', 'procedure'))}"
            ),
        )

    def _write_dashboard(self) -> Path:
        export_root = self.export_root()
        sections = [
            (
                "Status",
                self._bullets(
                    [
                        f"mode={self.obsidian.mode}",
                        f"cli_available={self.cli_available()}",
                        f"write_strategy={self.obsidian.write_strategy}",
                        f"updated_at={self._now()}",
                    ]
                ),
            ),
            (
                "Folders",
                self._bullets(
                    str((export_root / folder).relative_to(self.vault_path()))
                    for folder in self._FOLDERS
                ),
            ),
            (
                "Notes",
                self._bullets(
                    [
                        "Runtime memory stays in SQLite. This vault is a projection surface.",
                        (
                            "Use `forgegod obsidian export-memory` to write canonical "
                            "pattern notes from memory.db."
                        ),
                        (
                            "Research and run summaries are exported automatically "
                            "when this integration is enabled."
                        ),
                    ]
                ),
            ),
        ]
        return self._write_note(
            "Dashboard",
            "Overview",
            {
                "type": "dashboard",
                "project": self._project_name(),
                "updated_at": self._now(),
                "tags": ["forgegod", "dashboard"],
            },
            sections,
            filename_stem="overview",
        )

    def _write_note(
        self,
        folder: str,
        title: str,
        frontmatter: dict[str, Any],
        sections: list[tuple[str, str]],
        *,
        filename_stem: str | None = None,
    ) -> Path:
        folder_path = self.export_root() / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        stem = filename_stem or title
        path = folder_path / f"{self._safe_filename(stem)}.md"
        frontmatter_text = self._frontmatter(frontmatter)
        body_lines = [f"# {title}"]
        for heading, content in sections:
            if not content:
                continue
            body_lines.append("")
            body_lines.append(f"## {heading}")
            body_lines.append("")
            body_lines.append(content.rstrip())
        content = frontmatter_text + "\n" + "\n".join(body_lines).strip() + "\n"
        path.write_text(content, encoding="utf-8")
        return path

    def _project_name(self) -> str:
        name = self.config.project_dir.parent.name.strip()
        return name or "forgegod"

    def _date_prefix(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _frontmatter(self, values: dict[str, Any]) -> str:
        lines = ["---"]
        for key, value in values.items():
            if value in (None, "", []):
                continue
            lines.extend(self._yaml_pair(key, value))
        lines.append("---")
        return "\n".join(lines)

    def _yaml_pair(self, key: str, value: Any, indent: int = 0) -> list[str]:
        prefix = " " * indent
        if isinstance(value, bool):
            return [f"{prefix}{key}: {'true' if value else 'false'}"]
        if isinstance(value, (int, float)):
            return [f"{prefix}{key}: {value}"]
        if isinstance(value, list):
            if not value:
                return [f"{prefix}{key}: []"]
            lines = [f"{prefix}{key}:"]
            for item in value:
                if isinstance(item, (str, int, float, bool)):
                    lines.append(f"{prefix}  - {self._yaml_scalar(item)}")
                else:
                    lines.append(f"{prefix}  - {json.dumps(item, ensure_ascii=False)}")
            return lines
        return [f"{prefix}{key}: {self._yaml_scalar(value)}"]

    def _yaml_scalar(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        if "\n" in text:
            return json.dumps(text, ensure_ascii=False)
        if not text or any(ch in text for ch in ":#[]{},\"'"):
            return json.dumps(text, ensure_ascii=False)
        if text != text.strip():
            return json.dumps(text, ensure_ascii=False)
        return text

    def _safe_filename(self, text: str) -> str:
        slug = self._slug(text)
        return slug or "note"

    def _slug(self, text: str) -> str:
        cleaned = re.sub(r"[<>:\"/\\\\|?*]+", " ", str(text))
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        cleaned = re.sub(r"[^a-z0-9._ -]+", "", cleaned)
        cleaned = cleaned.replace(" ", "-")
        return cleaned[:96].strip("-")

    def _status_value(self, status: Any) -> str:
        return status.value if hasattr(status, "value") else str(status)

    def _story_status(self, story: Story) -> str:
        return self._status_value(story.status)

    def _story_line(self, story: Story) -> str:
        return f"{story.id} [{self._story_status(story)}] {story.title}"

    def _bullets(self, items) -> str:
        lines = [f"- {item}" for item in items if str(item).strip()]
        return "\n".join(lines)

    def _dedupe_urls(self, urls: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for url in urls:
            if not url or url in seen:
                continue
            seen.add(url)
            ordered.append(url)
        return ordered
