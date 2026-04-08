"""ForgeGod DESIGN.md integration helpers.

Integrates the awesome-design-md ecosystem into ForgeGod:
- list available presets from VoltAgent/awesome-design-md
- install a DESIGN.md preset into a project root
- persist lightweight source metadata for traceability
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

AWESOME_DESIGN_MD_TREE_URL = (
    "https://api.github.com/repos/VoltAgent/awesome-design-md/git/trees/main?recursive=1"
)
AWESOME_DESIGN_MD_RAW_BASE = (
    "https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main"
)


def fetch_design_presets(timeout: float = 20.0) -> list[str]:
    """Return sorted preset slugs from the awesome-design-md repository."""
    resp = httpx.get(
        AWESOME_DESIGN_MD_TREE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "forgegod"},
        timeout=timeout,
    )
    resp.raise_for_status()

    presets: set[str] = set()
    for item in resp.json().get("tree", []):
        path = item.get("path", "")
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "design-md" and parts[-1] == "DESIGN.md":
            presets.add(parts[1])
    return sorted(presets)


def resolve_design_source(preset_or_url: str) -> tuple[str, str]:
    """Resolve a preset name or raw URL into (label, url)."""
    value = preset_or_url.strip()
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        label = Path(parsed.path).parent.name or "custom"
        return label, value
    slug = value.lower().strip("/")
    return slug, f"{AWESOME_DESIGN_MD_RAW_BASE}/design-md/{slug}/DESIGN.md"


def install_design_md(
    project_root: Path | str,
    preset_or_url: str,
    *,
    force: bool = False,
    timeout: float = 20.0,
) -> Path:
    """Install DESIGN.md into a project root from awesome-design-md or a raw URL."""
    root = Path(project_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    design_path = root / "DESIGN.md"
    if design_path.exists() and not force:
        raise FileExistsError(f"{design_path} already exists. Use force=True to overwrite.")

    label, source_url = resolve_design_source(preset_or_url)
    resp = httpx.get(source_url, headers={"User-Agent": "forgegod"}, timeout=timeout)
    resp.raise_for_status()

    content = resp.text
    if not content.strip():
        raise RuntimeError(f"Downloaded empty DESIGN.md from {source_url}")

    design_path.write_text(content, encoding="utf-8")

    meta_dir = root / ".forgegod"
    meta_dir.mkdir(exist_ok=True)
    meta = {
        "source": source_url,
        "preset": label,
        "provider": (
            "VoltAgent/awesome-design-md"
            if "awesome-design-md" in source_url
            else "custom"
        ),
    }
    (meta_dir / "design-source.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    return design_path
