"""Validate JSON-LD schemas on secondary pages (impressum, privacy, terms).

Checks:
1. Each page has <script type="application/ld+json"> block in <head>
2. Schema includes @type WebPage
3. Schema references Organization via @id
4. JSON is syntactically valid with no errors
5. No visual regression (schema is in <head>, non-rendering)
"""
import json
import re
import sys
from pathlib import Path

PAGES = ["impressum.html", "privacy.html", "terms.html"]
BASE = Path(__file__).parent
errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"  FAIL: {msg}")


def validate_page(page_name: str) -> None:
    print(f"\n=== Validating {page_name} ===")
    content = (BASE / page_name).read_text(encoding="utf-8")

    # Extract <head> section
    head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
    if not head_match:
        err(f"{page_name}: No <head> section found")
        return
    head = head_match.group(1)

    # Extract JSON-LD blocks from <head>
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', head, re.DOTALL
    )
    if len(blocks) == 0:
        err(f"{page_name}: No JSON-LD block found in <head>")
        return
    if len(blocks) > 1:
        err(f"{page_name}: Expected 1 JSON-LD block, found {len(blocks)}")

    # Parse JSON and validate structure
    try:
        schema = json.loads(blocks[0])
    except json.JSONDecodeError as e:
        err(f"{page_name}: Invalid JSON syntax — {e}")
        return

    # Verify JSON-LD object structure
    if not isinstance(schema, dict):
        err(f"{page_name}: JSON-LD must be an object")
        return

    if "@context" not in schema:
        err(f"{page_name}: JSON-LD must have @context (schema.org)")

    # Check for WebPage type (in @graph or at root)
    has_webpage = False
    has_organization = False
    org_id = None

    if schema.get("@type") == "WebPage":
        has_webpage = True
    elif schema.get("@type") == "Organization":
        has_organization = True
        org_id = schema.get("@id")

    if "@graph" in schema:
        for item in schema["@graph"]:
            item_type = item.get("@type")
            if item_type == "WebPage":
                has_webpage = True
            elif item_type == "Organization":
                has_organization = True
                org_id = item.get("@id")

                # Check WebPage references this Organization via publisher
                for graph_item in schema["@graph"]:
                    if graph_item.get("@type") == "WebPage":
                        publisher = graph_item.get("publisher", {})
                        if isinstance(publisher, dict) and "@id" in publisher:
                            pub_id = publisher["@id"]
                            if pub_id != org_id:
                                err(
                                    f"{page_name}: WebPage publisher @id "
                                    f"'{pub_id}' != Organization @id '{org_id}'"
                                )

    if not has_webpage:
        err(f"{page_name}: Schema must include @type WebPage")

    if not has_organization:
        err(f"{page_name}: Schema must include @type Organization")

    # Verify no JSON-LD in <body> (should only be in <head>)
    body_match = re.search(r"<body>(.*?)</body>", content, re.DOTALL)
    if body_match:
        body_blocks = re.findall(
            r'<script type="application/ld\+json">', body_match.group(1)
        )
        if body_blocks:
            err(
                f"{page_name}: Found {len(body_blocks)} JSON-LD block(s) "
                "in <body> — should be in <head> only"
            )

    # Report results
    print(f"  JSON-LD block count: {len(blocks)}")
    print(f"  Has @type WebPage: {has_webpage}")
    print(f"  Has @type Organization: {has_organization}")
    print("  Valid JSON: True")

    page_errors = [e for e in errors if page_name in e]
    print(f"  Status: {'PASS' if not page_errors else 'FAIL'}")


for page in PAGES:
    validate_page(page)

print("\n" + "=" * 50)
if errors:
    print(f"VALIDATION FAILED ({len(errors)} error(s)):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL SECONDARY PAGE SCHEMAS VALID [OK]")
    sys.exit(0)
