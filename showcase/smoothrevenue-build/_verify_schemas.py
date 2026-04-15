"""Verify JSON-LD schemas in index.html - comprehensive validation."""
import json
import re
import sys

errors = []

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

blocks = re.findall(
    r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL
)
print(f"Found {len(blocks)} JSON-LD blocks\n")

all_valid = True
for i, b in enumerate(blocks, 1):
    try:
        schema = json.loads(b)
        t = schema.get("@type", "Graph")
        print(f"Block {i}: @type={t}")
    except json.JSONDecodeError as e:
        errors.append(f"Block {i}: JSON parse error: {e}")
        all_valid = False
        print(f"Block {i}: JSON ERROR - {e}")

# Collect top-level @id values to check for duplicates
# Note: nested @id values (like itemReviewed.@id) are references, not declarations
all_ids = {}
for i, b in enumerate(blocks, 1):
    try:
        schema = json.loads(b)
        # Only check top-level @id, not nested ones
        if "@id" in schema:
            id_val = schema["@id"]
            if id_val in all_ids:
                errors.append(f"Duplicate @id '{id_val}' in blocks {all_ids[id_val]} and {i}")
            all_ids[id_val] = i
    except Exception:
        pass

print(f"\nCollected {len(all_ids)} unique @id values")

# Check for required schemas
required_schemas = ["Service", "BreadcrumbList", "HowTo"]
found_types = set()
for b in blocks:
    try:
        schema = json.loads(b)
        found_types.add(schema.get("@type", ""))
    except Exception:
        pass

print(f"Found types: {sorted(found_types)}")

for req in required_schemas:
    if req not in found_types:
        errors.append(f"Missing required schema: {req}")

# Check Service schema
service_block = None
for i, b in enumerate(blocks, 1):
    try:
        schema = json.loads(b)
        if schema.get("@type") == "Service":
            service_block = schema
            name = schema.get("name", "MISSING")
            has_provider = "@id" in str(schema.get("provider", {}))
            has_offers = "offers" in schema
            print(f"\nService schema: name={name}, provider={has_provider}, offers={has_offers}")
    except Exception:
        pass

if not service_block:
    errors.append("Service schema not found")

# Check BreadcrumbList
breadcrumb_block = None
for b in blocks:
    try:
        schema = json.loads(b)
        if schema.get("@type") == "BreadcrumbList":
            breadcrumb_block = schema
            items = schema.get("itemListElement", [])
            print(f"BreadcrumbList has {len(items)} items")
    except Exception:
        pass

if not breadcrumb_block:
    errors.append("BreadcrumbList schema not found")

# Check HowTo
howto_block = None
for b in blocks:
    try:
        schema = json.loads(b)
        if schema.get("@type") == "HowTo":
            howto_block = schema
            steps = schema.get("step", [])
            print(f"HowTo schema has {len(steps)} steps")
    except Exception:
        pass

if not howto_block:
    errors.append("HowTo schema not found")

print()
if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL SCHEMAS VALID")
