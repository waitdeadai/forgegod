"""Check contact form keys in i18n files."""
import json

with open("i18n_en.json") as f:
    en_data = json.load(f)
with open("i18n_es.json") as f:
    es_data = json.load(f)

en_keys = set(en_data.get("en", {}).keys())
es_keys = set(es_data.get("es", {}).keys())

contact_form_keys = sorted(k for k in en_keys if "form." in k or "contact." in k)

print("Contact/form keys in i18n_en.json:")
for k in contact_form_keys:
    print(f"  {k}")

print(f"\nTotal: {len(contact_form_keys)}")

# Check ES has same keys
missing_in_es = set(contact_form_keys) - es_keys
if missing_in_es:
    print(f"\nMissing in ES: {sorted(missing_in_es)}")
else:
    print("\nAll contact form keys present in ES")
