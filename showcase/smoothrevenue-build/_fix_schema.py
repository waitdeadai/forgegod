"""Fix JSON-LD schemas in index.html."""
import json
import re

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Extract all JSON-LD blocks
blocks = re.findall(
    r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL
)

# ============================================================
# FIX 1: Replace block 3 (@graph) — remove invalid CaseStudy type,
# add publisher and articleBody to TechArticle items
# ============================================================
graph = json.loads(blocks[2])

# Filter out CaseStudy items (not a valid Schema.org type)
# and enhance TechArticle items with publisher + articleBody
tech_articles = [item for item in graph["@graph"] if item.get("@type") == "TechArticle"]
case_studies = [item for item in graph["@graph"] if item.get("@type") == "CaseStudy"]

# Build new graph items
new_items = []
for item in tech_articles:
    item["publisher"] = {"@type": "Organization", "name": "Smoothrevenue"}
    item["articleBody"] = item.get("description", "")
    new_items.append(item)

# Convert valid CaseStudy data to TechArticle (preserving content)
for item in case_studies:
    cs_id = item.get("@id", "")
    new_item = {
        "@type": "TechArticle",
        "@id": cs_id,
        "headline": item.get("headline", ""),
        "description": item.get("description", ""),
        "articleBody": item.get("description", ""),
        "author": item.get("author", {"@type": "Organization", "name": "Smoothrevenue"}),
        "publisher": item.get("publisher", {"@type": "Organization", "name": "Smoothrevenue"}),
        "datePublished": item.get("datePublished", ""),
        "proficiencyLevel": "Expert",
        "about": item.get("about", []),
    }
    # Only add if this @id is not already in new_items (avoid duplicates)
    existing_ids = [ni.get("@id") for ni in new_items]
    if cs_id not in existing_ids:
        new_items.append(new_item)

graph["@graph"] = new_items
new_block3 = json.dumps(graph, indent=2, ensure_ascii=False)

# Replace block 3 in content
old_block3 = blocks[2]
content = content.replace(
    f'<script type="application/ld+json">{old_block3}</script>',
    f'<script type="application/ld+json">\n{new_block3}\n  </script>',
    1
)

# ============================================================
# FIX 2: Verify FAQPage questions match HTML (should be 8)
# ============================================================
faq = json.loads(blocks[1])
schema_questions = [q["name"] for q in faq["mainEntity"]]
html_questions = re.findall(r'<span data-i18n="faq\.q\d+">(.*?)</span>', content)
html_answers = re.findall(r'<p data-i18n="faq\.a\d+">(.*?)</p>', content)

print(f"Schema FAQ questions: {len(schema_questions)}")
print(f"HTML FAQ questions: {len(html_questions)}")

if len(schema_questions) != len(html_questions):
    print("Updating FAQPage schema to match HTML...")
    new_entities = []
    for q, a in zip(html_questions, html_answers):
        new_entities.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a
            }
        })
    faq["mainEntity"] = new_entities
    new_block2 = json.dumps(faq, indent=2, ensure_ascii=False)
    old_block2 = blocks[1]
    content = content.replace(
        f'<script type="application/ld+json">{old_block2}</script>',
        f'<script type="application/ld+json">\n{new_block2}\n  </script>',
        1
    )

with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Done. index.html updated.")
