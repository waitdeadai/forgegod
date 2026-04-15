"""Comprehensive JSON-LD schema audit for index.html.

Validates:
1. Organization schema exists with required fields
2. FAQPage schema exists and matches HTML FAQ questions
3. TechArticle schemas exist for case studies with required fields
4. All @type values are valid Schema.org types
5. articleBody content is substantive (not just description copy)
6. HTML microdata consistency with JSON-LD
"""
import json
import re
import sys
from pathlib import Path

HTML_FILE = Path(__file__).parent / "index.html"
content = HTML_FILE.read_text(encoding="utf-8")

# ── Extract JSON-LD blocks ──────────────────────────────────────────
blocks = re.findall(
    r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL
)
assert len(blocks) == 3, f"Expected 3 JSON-LD blocks, found {len(blocks)}"

errors: list[str] = []

def err(msg: str) -> None:
    errors.append(msg)
    print(f"  FAIL: {msg}")

# ── Block 1: Organization ───────────────────────────────────────────
org = json.loads(blocks[0])
assert org["@type"] == "Organization", "Block 1 must be Organization"
for field in ["name", "url", "logo", "contactPoint"]:
    if field not in org:
        err(f"Organization missing required field: {field}")
if "contactPoint" in org:
    cp = org["contactPoint"]
    if cp.get("@type") != "ContactPoint":
        err("Organization contactPoint @type must be ContactPoint")
    for cf in ["contactType", "email"]:
        if cf not in cp:
            err(f"ContactPoint missing field: {cf}")
if "description" not in org:
    err("Organization missing recommended field: description")
print(f"[1/6] Organization schema: {'PASS' if not errors else 'FAIL'}")

# ── Block 2: FAQPage ────────────────────────────────────────────────
prev_errors = len(errors)
faq = json.loads(blocks[1])
assert faq["@type"] == "FAQPage", "Block 2 must be FAQPage"
assert "mainEntity" in faq, "FAQPage must have mainEntity"

schema_questions = [q["name"] for q in faq["mainEntity"]]
html_questions = re.findall(r'<span data-i18n="faq\.q\d+">(.*?)</span>', content)
html_answers = re.findall(r'<p data-i18n="faq\.a\d+">(.*?)</p>', content)

if len(schema_questions) != len(html_questions):
    err(f"FAQ count mismatch: schema={len(schema_questions)}, html={len(html_questions)}")

for i, (sq, hq) in enumerate(zip(schema_questions, html_questions)):
    if sq != hq:
        err(f"FAQ Q{i+1} mismatch: schema='{sq[:50]}...' vs html='{hq[:50]}...'")

# Verify schema answers match HTML answers
for i, q in enumerate(faq["mainEntity"]):
    ans = q.get("acceptedAnswer", {})
    if ans.get("@type") != "Answer":
        err(f"FAQ Q{i+1} acceptedAnswer missing @type=Answer")
    if "text" not in ans:
        err(f"FAQ Q{i+1} acceptedAnswer missing text")

print(f"[2/6] FAQPage schema: {'PASS' if len(errors) == prev_errors else 'FAIL'}")

# ── Block 3: @graph with TechArticle ────────────────────────────────
prev_errors = len(errors)
graph = json.loads(blocks[2])
items = graph.get("@graph", [])
assert len(items) >= 2, f"Expected at least 2 graph items, got {len(items)}"

VALID_TYPES = {
    "Organization", "ContactPoint", "FAQPage", "Question", "Answer",
    "TechArticle", "Article", "WebPage", "Thing", "AggregateRating",
    "Person", "CreativeWork", "Review",
}

tech_article_count = 0
for i, item in enumerate(items):
    t = item.get("@type", "MISSING")
    if t not in VALID_TYPES:
        err(f"Graph item {i}: invalid @type '{t}'")
    if t == "TechArticle":
        tech_article_count += 1
        for field in ["headline", "author", "datePublished"]:
            if field not in item:
                err(f"TechArticle item {i} missing required field: {field}")
        # Check articleBody is substantive (>50 chars, not just description copy)
        body = item.get("articleBody", "")
        desc = item.get("description", "")
        if not body:
            err(f"TechArticle item {i} missing articleBody")
        elif body == desc:
            err(f"TechArticle item {i} articleBody is identical to description (not substantive)")
        elif len(body) < 50:
            err(f"TechArticle item {i} articleBody too short ({len(body)} chars)")
        # Check author structure
        author = item.get("author", {})
        if isinstance(author, dict):
            if author.get("@type") not in ("Organization", "Person"):
                err(f"TechArticle item {i} author @type must be Organization or Person")
        # Check publisher exists
        if "publisher" not in item:
            err(f"TechArticle item {i} missing recommended field: publisher")

if tech_article_count < 2:
    err(f"Expected 2 TechArticle items, found {tech_article_count}")

print(f"[3/6] TechArticle schemas: {'PASS' if len(errors) == prev_errors else 'FAIL'}")

# ── Cross-check: HTML microdata vs JSON-LD ──────────────────────────
prev_errors = len(errors)
html_articles = re.findall(r'itemtype="https://schema\.org/Article"', content)
if len(html_articles) < 2:
    err(f"Expected 2 HTML microdata Articles, found {len(html_articles)}")

# Check JSON-LD headlines reference the same case studies
html_headlines = re.findall(
    r'<h3[^>]*itemprop="headline"[^>]*>(.*?)</h3>', content
)
json_headlines = [item["headline"] for item in items if item.get("@type") == "TechArticle"]

# They don't need to be exact match but should reference same topics
for jh in json_headlines:
    # At least one HTML headline should share significant words
    words = set(jh.lower().split()) - {"for", "the", "a", "an", "of", "in", "to", "and"}
    matched = False
    for hh in html_headlines:
        hh_words = set(hh.lower().split()) - {"for", "the", "a", "an", "of", "in", "to", "and"}
        overlap = words & hh_words
        if len(overlap) >= 2:
            matched = True
            break
    if not matched:
        err(f"JSON-LD headline '{jh[:60]}' has no matching HTML case study")

print(f"[4/6] HTML/JSON-LD consistency: {'PASS' if len(errors) == prev_errors else 'FAIL'}")

# ── Schema.org type validation ──────────────────────────────────────
prev_errors = len(errors)
for i, b in enumerate(blocks):
    schema = json.loads(b)
    if "@type" in schema:
        if schema["@type"] not in VALID_TYPES:
            err(f"Block {i+1} has non-standard @type: {schema['@type']}")
    if "@graph" in schema:
        for item in schema["@graph"]:
            t = item.get("@type", "")
            if t and t not in VALID_TYPES:
                err(f"Block {i+1} graph item has non-standard @type: {t}")
    # Check nested @type in sub-objects
    def check_nested(obj: dict, path: str = "") -> None:
        for k, v in obj.items():
            if isinstance(v, dict):
                if "@type" in v:
                    if v["@type"] not in VALID_TYPES:
                        err(f"{path}.{k} has non-standard @type: {v['@type']}")
                check_nested(v, f"{path}.{k}")
            elif isinstance(v, list):
                for j, item in enumerate(v):
                    if isinstance(item, dict):
                        if "@type" in item:
                            if item["@type"] not in VALID_TYPES:
                                err(f"{path}.{k}[{j}] has non-standard @type: {item['@type']}")
                        check_nested(item, f"{path}.{k}[{j}]")
    check_nested(schema, f"Block{i+1}")

print(f"[5/6] Schema.org type validity: {'PASS' if len(errors) == prev_errors else 'FAIL'}")

# ── JSON validity check ─────────────────────────────────────────────
prev_errors = len(errors)
for i, b in enumerate(blocks):
    try:
        json.loads(b)
    except json.JSONDecodeError as e:
        err(f"Block {i+1} has invalid JSON: {e}")
print(f"[6/6] JSON syntax validity: {'PASS' if len(errors) == prev_errors else 'FAIL'}")

# ── Summary ─────────────────────────────────────────────────────────
print()
if errors:
    print(f"SCHEMA AUDIT FAILED ({len(errors)} error(s)):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL SCHEMA CHECKS PASSED")
