"""Verify JSON-LD schemas in index.html are valid."""
import json
import re
import sys

errors = []

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

blocks = re.findall(
    r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL
)
print(f"Found {len(blocks)} JSON-LD blocks")

for i, b in enumerate(blocks):
    try:
        schema = json.loads(b)
    except json.JSONDecodeError as e:
        errors.append(f"Block {i+1}: JSON parse error: {e}")
        continue
    print(f"Block {i+1}: @type={schema.get('@type', 'NONE (graph)')}")

# 1. Organization schema
org = json.loads(blocks[0])
assert org["@type"] == "Organization", "Block 1 must be Organization"
assert "name" in org, "Organization needs name"
assert "url" in org, "Organization needs url"
assert "logo" in org, "Organization needs logo"
assert "contactPoint" in org, "Organization needs contactPoint"
assert org["contactPoint"]["@type"] == "ContactPoint"
print("OK: Organization schema valid")

# 2. FAQPage schema
faq = json.loads(blocks[1])
assert faq["@type"] == "FAQPage", "Block 2 must be FAQPage"
questions = [q["name"] for q in faq["mainEntity"]]
print(f"  FAQ schema has {len(questions)} questions")

# Extract HTML FAQ questions
html_questions = re.findall(r'<span data-i18n="faq\.q\d+">(.*?)</span>', content)
print(f"  HTML has {len(html_questions)} questions")

for q in html_questions:
    found = any(q in sq for sq in questions)
    if not found:
        errors.append(f"FAQ mismatch: '{q[:60]}' not in schema")

if not errors:
    print("OK: FAQPage schema matches HTML")

# 3. Graph block (TechArticle + CaseStudy items)
graph = json.loads(blocks[2])
items = graph.get("@graph", [])
print(f"  @graph has {len(items)} items")

valid_types = {
    "Organization", "ContactPoint", "FAQPage", "Question", "Answer",
    "TechArticle", "Article", "WebPage", "Thing", "AggregateRating",
    "Person", "CreativeWork", "Review",
}

for item in items:
    t = item.get("@type", "MISSING")
    print(f"    item @type: {t}")
    if t not in valid_types:
        errors.append(f"Non-standard @type: '{t}' — consider using 'Article'")
    # Check required fields for TechArticle
    if t == "TechArticle":
        for field in ["headline", "author", "datePublished"]:
            if field not in item:
                errors.append(f"TechArticle missing required field: {field}")
        if "author" in item:
            assert item["author"]["@type"] in ("Organization", "Person")

print()

if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL SCHEMAS VALID ✅")
