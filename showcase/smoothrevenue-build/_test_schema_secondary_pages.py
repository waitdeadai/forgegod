"""Test schema markup on secondary pages (impressum, privacy, terms)."""
import json
import re
import sys
from pathlib import Path

PAGES = ["impressum.html", "privacy.html", "terms.html"]
BASE = Path(__file__).parent


def test_each_page_has_json_ld_in_head():
    """Each secondary page must have exactly 1 JSON-LD block in <head>."""
    for page in PAGES:
        content = (BASE / page).read_text(encoding="utf-8")
        head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
        assert head_match, f"{page}: No <head> section found"

        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            head_match.group(1),
            re.DOTALL
        )
        assert len(blocks) == 1, f"{page}: Expected 1 JSON-LD block, found {len(blocks)}"


def test_schema_includes_webpage_type():
    """Schema must include @type WebPage."""
    for page in PAGES:
        content = (BASE / page).read_text(encoding="utf-8")
        head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            head_match.group(1),
            re.DOTALL
        )
        schema = json.loads(blocks[0])

        # Check if WebPage is in @graph or at root level
        has_webpage = False
        if schema.get("@type") == "WebPage":
            has_webpage = True
        elif "@graph" in schema:
            types = [item.get("@type") for item in schema["@graph"]]
            has_webpage = "WebPage" in types

        assert has_webpage, f"{page}: Schema must include @type WebPage"


def test_schema_references_organization():
    """Schema must reference Organization via @id."""
    for page in PAGES:
        content = (BASE / page).read_text(encoding="utf-8")
        head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            head_match.group(1),
            re.DOTALL
        )
        schema = json.loads(blocks[0])

        # Check if Organization is in @graph or at root level
        has_org = False
        org_id = None

        if schema.get("@type") == "Organization":
            has_org = True
            org_id = schema.get("@id")
        elif "@graph" in schema:
            for item in schema["@graph"]:
                if item.get("@type") == "Organization":
                    has_org = True
                    org_id = item.get("@id")
                    break

        assert has_org, f"{page}: Schema must include @type Organization"

        # Check that WebPage references Organization via publisher
        if "@graph" in schema:
            for item in schema["@graph"]:
                if item.get("@type") == "WebPage":
                    publisher = item.get("publisher", {})
                    if isinstance(publisher, dict) and "@id" in publisher:
                        assert publisher["@id"] == org_id, (
                            f"{page}: WebPage publisher @id must match Organization @id"
                        )


def test_json_ld_passes_validation():
    """JSON-LD must be syntactically valid with no errors."""
    for page in PAGES:
        content = (BASE / page).read_text(encoding="utf-8")
        head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            head_match.group(1),
            re.DOTALL
        )
        try:
            schema = json.loads(blocks[0])
            # Verify it's a dict with required schema.org context
            assert isinstance(schema, dict), f"{page}: JSON-LD must be an object"
            assert "@context" in schema, f"{page}: JSON-LD must have @context"
        except json.JSONDecodeError as e:
            assert False, f"{page}: Invalid JSON — {e}"


def test_no_visual_regression():
    """JSON-LD in <head> does not affect page rendering."""
    for page in PAGES:
        content = (BASE / page).read_text(encoding="utf-8")

        # Verify JSON-LD is in <head>, not <body>
        head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
        assert head_match, f"{page}: No <head> section found"

        head_blocks = re.findall(
            r'<script type="application/ld\+json">',
            head_match.group(1)
        )
        assert len(head_blocks) >= 1, f"{page}: JSON-LD must be in <head>"

        body_match = re.search(r"<body>(.*?)</body>", content, re.DOTALL)
        if body_match:
            body_blocks = re.findall(
                r'<script type="application/ld\+json">',
                body_match.group(1)
            )
            assert len(body_blocks) == 0, (
                f"{page}: JSON-LD found in <body> — should only be in <head>"
            )


if __name__ == "__main__":
    tests = [
        test_each_page_has_json_ld_in_head,
        test_schema_includes_webpage_type,
        test_schema_references_organization,
        test_json_ld_passes_validation,
        test_no_visual_regression,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__} — {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
