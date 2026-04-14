"""Verify i18n key coverage between HTML data-i18n attrs and i18n JSON files."""
import json
import re
from pathlib import Path

BASE = Path("showcase/smoothrevenue-build")


def get_html_keys():
    """Extract all data-i18n attribute values from index.html."""
    html_path = BASE / "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return set(re.findall(r'data-i18n="([^"]+)"', content))


def get_json_keys(lang):
    """Extract translation keys from an i18n JSON file for the given language."""
    json_path = BASE / f"i18n_{lang}.json"
    if not json_path.exists():
        return set()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Support {lang: {key: val}} format — look for the lang key first
    if lang in data and isinstance(data[lang], dict):
        return set(data[lang].keys())
    # Fallback: treat top-level as flat {key: val}
    if isinstance(data, dict):
        first_val = next(iter(data.values()), None)
        if isinstance(first_val, dict):
            return set(data.keys())
    return set()


def main():
    """Run the i18n completeness check and return 0 if pass, 1 if fail."""
    html_keys = get_html_keys()

    en_keys = get_json_keys("en")
    es_keys = get_json_keys("es")

    print(f"HTML data-i18n keys: {len(html_keys)}")
    print(f"EN translations (i18n_en.json): {len(en_keys)}")
    print(f"ES translations (i18n_es.json): {len(es_keys)}")

    missing_en = html_keys - en_keys
    missing_es = html_keys - es_keys

    print(f"\nMissing from EN: {len(missing_en)}")
    for k in sorted(missing_en):
        print(f"  - {k}")

    print(f"\nMissing from ES: {len(missing_es)}")
    for k in sorted(missing_es):
        print(f"  - {k}")

    if missing_en or missing_es:
        print("\ni18n coverage incomplete!")
        return 1
    else:
        print("\ni18n coverage complete!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
