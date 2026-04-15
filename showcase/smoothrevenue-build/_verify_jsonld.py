#!/usr/bin/env python3
"""Verify JSON-LD structured data in index.html."""
import json
import re
import sys


def main() -> int:
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all JSON-LD script blocks
    pattern = r'<script type="application/ld\+json">(.*?)</script>'
    matches = re.findall(pattern, content, re.DOTALL)

    all_valid = True
    all_ids: list[str] = []
    schema_types: list[str] = []

    # Parse all blocks upfront for clean iteration
    parsed_schemas: list[dict] = []
    for i, match in enumerate(matches, 1):
        match = match.strip()
        print(f'--- Schema Block {i} ---')
        try:
            data = json.loads(match)
            parsed_schemas.append(data)
            schema_type = data.get('@type', 'Unknown')
            schema_types.append(schema_type)
            print(f'  Type: {schema_type}')

            # Collect @id values
            if '@id' in data:
                all_ids.append(data['@id'])
                print(f'  @id: {data["@id"]}')

            # Check @graph for nested @id
            if '@graph' in data:
                for item in data['@graph']:
                    if '@id' in item:
                        all_ids.append(item['@id'])
                        print(f'  Nested @id: {item["@id"]}')

            print('  [OK] Valid JSON')
        except json.JSONDecodeError as e:
            print(f'  [FAIL] INVALID JSON: {e}')
            all_valid = False
        print()

    print('=== @id Values Found ===')
    for id_val in all_ids:
        print(f'  {id_val}')
    print(f'Total unique @ids: {len(set(all_ids))} / {len(all_ids)} total')

    dupes = [x for x in all_ids if all_ids.count(x) > 1]
    if dupes:
        print('[FAIL] DUPLICATE @id VALUES FOUND!')
        for d in sorted(set(dupes)):
            print(f'  - {d}')
    else:
        print('[OK] No duplicate @ids')

    print()
    print('=== Schema Types Present ===')
    for t in schema_types:
        print(f'  - {t}')

    # Build a set of all @type values found (including nested in @graph)
    all_type_values: set[str] = set()
    for schema in parsed_schemas:
        t = schema.get('@type')
        if t:
            all_type_values.add(t)
        for item in schema.get('@graph', []):
            t = item.get('@type')
            if t:
                all_type_values.add(t)

    required_schemas = {
        'Organization': 'Organization' in all_type_values,
        'FAQPage': 'FAQPage' in all_type_values,
        'Service': 'Service' in all_type_values,
        'WebApplication': 'WebApplication' in all_type_values,
        'HowTo': 'HowTo' in all_type_values,
        'BreadcrumbList': 'BreadcrumbList' in all_type_values,
        'AggregateRating': 'AggregateRating' in all_type_values,
        'WebSite': 'WebSite' in all_type_values,
        'Review': 'Review' in all_type_values,
    }

    print()
    print('=== Required Schema Check ===')
    for name, present in required_schemas.items():
        status = '[OK]' if present else '[MISSING]'
        print(f'  {status} {name} schema')

    missing = [name for name, present in required_schemas.items() if not present]

    # Cross-reference checks
    print()
    print('=== Cross-Reference Checks ===')

    # Check Service provider references Organization @id
    service_schema = None
    for schema in parsed_schemas:
        if schema.get('@type') == 'Service':
            service_schema = schema
            break

    if service_schema:
        provider_id = service_schema.get('provider', {}).get('@id')
        if provider_id:
            print(f'  [OK] Service provider @id: {provider_id}')
        else:
            print('  [WARN] Service schema missing provider @id reference')

    # Check Review itemReviewed references Service @id
    review_count = 0
    for schema in parsed_schemas:
        graph_items = schema.get('@graph', [])
        for item in graph_items:
            if item.get('@type') == 'Review':
                review_count += 1
                reviewed = item.get('itemReviewed', {})
                reviewed_id = reviewed.get('@id') if isinstance(reviewed, dict) else None
                if reviewed_id:
                    print(f'  [OK] Review references: {reviewed_id}')
                else:
                    print('  [WARN] Review missing itemReviewed @id')

    if review_count:
        print(f'  [OK] Found {review_count} Review schemas')

    # Check hreflang
    hreflangs = re.findall(r'hreflang="([^"]+)"', content)
    print()
    print('=== hreflang Tags ===')
    for h in hreflangs:
        print(f'  - {h}')
    has_xdefault = 'x-default' in hreflangs
    print(f'  {"[OK]" if has_xdefault else "[MISSING]"} x-default hreflang')

    print()
    if all_valid and not dupes and not missing:
        print('[SUCCESS] All JSON-LD blocks valid and comprehensive')
        return 0
    else:
        if missing:
            print(f'[FAIL] Missing schema types: {", ".join(missing)}')
        if not all_valid:
            print('[FAIL] Invalid JSON found')
        if dupes:
            print('[FAIL] Duplicate @id values found')
        return 1


if __name__ == '__main__':
    sys.exit(main())
