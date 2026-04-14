import re

with open('showcase/smoothrevenue-build/index.html', 'r', encoding='utf-8') as f:
    content = f.read()
matches = re.findall(r'data-i18n="([^"]+)"', content)
print(f"Total data-i18n attributes: {len(matches)}")
for m in sorted(set(matches)):
    print(m)
