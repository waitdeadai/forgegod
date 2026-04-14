"""Generate app.js with full EN/ES i18n translations from i18n.json."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "i18n.json"), encoding="utf-8") as f:
    i18n = json.load(f)


def fmt_obj(d, indent=6):
    """Format a dict as a JS object literal."""
    pad = " " * indent
    lines = []
    for k, v in d.items():
        esc = v.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"{pad}'{k}': '{esc}'")
    inner = ",\n".join(lines)
    return "{\n" + inner + "\n" + " " * (indent - 4) + "}"


# Read existing app.js to extract the non-translation parts
with open(os.path.join(HERE, "app.js"), encoding="utf-8") as f:
    old_js = f.read()

# Build new translations block
en_block = fmt_obj(i18n["en"], indent=6)
es_block = fmt_obj(i18n["es"], indent=6)

new_translations = f"""  var translations = {{
    en: {en_block},
    es: {es_block},
  }};"""

# Replace old translations block
pattern = r"  var translations = \{[\s\S]*?\n  \};"
new_js = re.sub(pattern, new_translations, old_js, count=1)

with open(os.path.join(HERE, "app.js"), "w", encoding="utf-8") as f:
    f.write(new_js)

print("app.js generated successfully")
