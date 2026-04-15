"""Check for hardcoded English text in index.html that lacks data-i18n attributes."""
import re
from pathlib import Path

BASE = Path(__file__).parent

html = (BASE / "index.html").read_text(encoding="utf-8")

# Find all data-i18n keys
i18n_keys = set(re.findall(r'data-i18n="([^"]+)"', html))
print(f"Total data-i18n keys in HTML: {len(i18n_keys)}")

# Find testimonial quotes (these are typically not translated as they're quotes)
testimonials = re.findall(r'class="testimonial-card__quote">(.*?)</p>', html)
print(f"\nTestimonial quotes found: {len(testimonials)}")
for i, t in enumerate(testimonials):
    print(f"  {i+1}: {t[:80]}...")

# Find label texts
labels = re.findall(r'<label[^>]*>(.*?)</label>', html, re.DOTALL)
print(f"\nForm labels found: {len(labels)}")
for lab in labels:
    clean = re.sub(r"<[^>]+>", "", lab).strip()
    print(f"  - {clean}")

# Find option texts
options = re.findall(r"<option[^>]*>(.*?)</option>", html)
print(f"\nOption texts found: {len(options)}")
for o in options:
    print(f"  - {o}")

# Find maturity labels
maturity = re.findall(r'<span class="maturity-labels">(.*?)</div>', html, re.DOTALL)
if maturity:
    spans = re.findall(r"<span>(.*?)</span>", maturity[0])
    print(f"\nMaturity labels: {spans}")

# Find placeholder texts
placeholders = re.findall(r'placeholder="([^"]*)"', html)
print(f"\nPlaceholder texts: {placeholders}")

# Find case study details
case_metrics = re.findall(r'class="case-study-card__metric"[^>]*>(.*?)</div>', html)
print(f"\nCase study metrics: {len(case_metrics)}")
for m in case_metrics:
    print(f"  - {m}")

# Find testimonial metrics
test_metrics = re.findall(r'class="testimonial-card__metric">(.*?)</div>', html)
print(f"\nTestimonial metrics: {len(test_metrics)}")
for m in test_metrics:
    print(f"  - {m}")

# Find testimonial roles
test_roles = re.findall(r'class="testimonial-card__role">(.*?)</span>', html)
print(f"\nTestimonial roles: {len(test_roles)}")
for r in test_roles:
    print(f"  - {r}")

# Find testimonial names
test_names = re.findall(r'class="testimonial-card__name">(.*?)</cite>', html)
print(f"\nTestimonial names: {len(test_names)}")
for n in test_names:
    print(f"  - {n}")

# Find case study titles without data-i18n
case_titles = re.findall(r'class="case-study-card__title"[^>]*>(.*?)</h3>', html)
print(f"\nCase study titles: {len(case_titles)}")
for t in case_titles:
    print(f"  - {t}")

# Find case study descriptions
case_descs = re.findall(r'class="case-study-card__desc"[^>]*>(.*?)</p>', html)
print(f"\nCase study descriptions: {len(case_descs)}")
for d in case_descs:
    print(f"  - {d[:80]}...")
