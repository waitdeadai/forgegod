from __future__ import annotations

from forgegod.config import ForgeGodConfig
from forgegod.models import ResearchDepth
from forgegod.researcher import Researcher
from forgegod.router import ModelRouter


class DummyRouter(ModelRouter):
    def __init__(self):
        pass


def _researcher() -> Researcher:
    return Researcher(ForgeGodConfig(), DummyRouter())


def test_research_limits_scale_with_depth():
    researcher = _researcher()

    quick = researcher._research_limits(ResearchDepth.QUICK)
    deep = researcher._research_limits(ResearchDepth.DEEP)
    sota = researcher._research_limits(ResearchDepth.SOTA)

    assert quick["max_fetch"] < deep["max_fetch"] <= sota["max_fetch"]
    assert quick["max_searches"] < deep["max_searches"] <= sota["max_searches"]


def test_parse_queries_falls_back_on_invalid_json():
    researcher = _researcher()

    queries = researcher._parse_queries("totally not json")

    assert len(queries) == 1
    assert "best practices" in queries[0].query


def test_parse_queries_accepts_dict_wrapper():
    researcher = _researcher()

    queries = researcher._parse_queries(
        '{"queries":[{"query":"fastapi release notes 2026","category":"docs","priority":1}]}'
    )

    assert len(queries) == 1
    assert queries[0].query == "fastapi release notes 2026"
    assert queries[0].category == "docs"


def test_parse_brief_returns_empty_brief_on_invalid_json():
    researcher = _researcher()

    brief = researcher._parse_brief("not json", "build api")

    assert brief.task == "build api"
    assert brief.libraries == []


def test_parse_brief_maps_library_recommendations():
    researcher = _researcher()

    brief = researcher._parse_brief(
        """
        {
          "libraries": [
            {
              "name": "fastapi",
              "version": "0.115",
              "why": "Current stable async API framework",
              "alternatives": ["flask"],
              "caveats": "Watch pydantic compatibility"
            }
          ],
          "architecture_patterns": ["service boundary per domain"],
          "security_warnings": ["validate auth headers"],
          "best_practices": ["pin dependency versions"],
          "prior_art": ["open-source fastapi boilerplates"]
        }
        """,
        "build api",
    )

    assert brief.task == "build api"
    assert len(brief.libraries) == 1
    assert brief.libraries[0].name == "fastapi"
    assert brief.architecture_patterns == ["service boundary per domain"]
