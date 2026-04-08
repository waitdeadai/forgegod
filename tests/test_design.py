"""Tests for DESIGN.md preset integration."""

import json
from pathlib import Path

import httpx
import pytest

from forgegod.design import (
    AWESOME_DESIGN_MD_TREE_URL,
    fetch_design_presets,
    install_design_md,
    resolve_design_source,
)


def test_resolve_design_source_slug():
    label, url = resolve_design_source("claude")
    assert label == "claude"
    assert url.endswith("/design-md/claude/DESIGN.md")


def test_resolve_design_source_url():
    label, url = resolve_design_source("https://example.com/custom/DESIGN.md")
    assert label == "custom"
    assert url == "https://example.com/custom/DESIGN.md"


def test_fetch_design_presets(monkeypatch):
    def fake_get(url, **kwargs):
        assert url == AWESOME_DESIGN_MD_TREE_URL
        return httpx.Response(
            200,
            json={
                "tree": [
                    {"path": "design-md/claude/DESIGN.md"},
                    {"path": "design-md/linear/DESIGN.md"},
                    {"path": "design-md/claude/preview.html"},
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    assert fetch_design_presets() == ["claude", "linear"]


def test_install_design_md(tmp_path: Path, monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(
            200,
            text="# DESIGN\nUse bold cyan.\n",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    installed = install_design_md(tmp_path, "claude")

    assert installed == tmp_path / "DESIGN.md"
    assert installed.read_text(encoding="utf-8").startswith("# DESIGN")
    meta = json.loads((tmp_path / ".forgegod" / "design-source.json").read_text(encoding="utf-8"))
    assert meta["preset"] == "claude"


def test_install_design_md_respects_force(tmp_path: Path, monkeypatch):
    (tmp_path / "DESIGN.md").write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        install_design_md(tmp_path, "claude")
