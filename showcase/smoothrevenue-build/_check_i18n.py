"""Verify i18n key coverage between HTML data-i18n attrs and JS translations."""
import re


def get_html_keys():
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return set(re.findall(r'data-i18n="([^"]+)"', content))


def get_js_keys(lang):
    with open("app.js", "r", encoding="utf-8") as f:
        content = f.read()
    section = content.split(f"{lang}: {{")[1].split("},")[0]
    return set(re.findall(r"'([^']+)':", section))


html_keys = get_html_keys()
en_keys = get_js_keys("en")
es_keys = get_js_keys("es")

print(f"HTML data-i18n keys: {len(html_keys)}")
print(f"EN translations: {len(en_keys)}")
print(f"ES translations: {len(es_keys)}")

missing_en = html_keys - en_keys
missing_es = html_keys - es_keys

print(f"\nMissing from EN: {len(missing_en)}")
for k in sorted(missing_en):
    print(f"  - {k}")

print(f"\nMissing from ES: {len(missing_es)}")
for k in sorted(missing_es):
    print(f"  - {k}")

if missing_en or missing_es:
    print("\n⚠️  i18n coverage incomplete!")
    exit(1)
else:
    print("\n✅ i18n coverage complete!")
