"""Audit JSON-LD schemas in index.html and extract FAQ/case-study content from HTML."""
import json
import re

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find JSON-LD blocks
blocks = re.findall(
    r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL
)
print(f"Found {len(blocks)} JSON-LD blocks\n")

for i, b in enumerate(blocks):
    try:
        schema = json.loads(b)
        print(f"--- Block {i+1} ---")
        print(f"@type: {schema.get('@type')}")
        print(json.dumps(schema, indent=2)[:600])
        print()
    except json.JSONDecodeError as e:
        print(f"--- Block {i+1} --- PARSE ERROR: {e}")
        print(b[:200])
        print()

# Extract FAQ questions from HTML
print("\n=== FAQ Questions in HTML ===")
faq_pattern = re.findall(
    r'<span data-i18n="faq\.q\d+">(.*?)</span>', content
)
for q in faq_pattern:
    print(f"  Q: {q[:100]}")

# Extract FAQ answers from HTML
print("\n=== FAQ Answers in HTML ===")
ans_pattern = re.findall(
    r'<p data-i18n="faq\.a\d+">(.*?)</p>', content
)
for a in ans_pattern:
    print(f"  A: {a[:100]}")

# Check for case study sections
print("\n=== Case Study sections ===")
cs_pattern = re.findall(r'id="case-stud[^"]*"', content)
for c in cs_pattern:
    print(f"  {c}")

cs_class = re.findall(r'class="case-stud[^"]*"', content)
for c in cs_class:
    print(f"  {c}")
