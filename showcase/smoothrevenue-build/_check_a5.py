"""Quick check for a5a5af tertiary color."""
from _check_contrast import contrast_ratio

for bg_name, bg in [("bg-base","#0a0a0b"),("bg-surface","#111114"),("bg-elevated","#18181c")]:
    r = contrast_ratio("#a5a5af", bg)
    print(f"a5a5af on {bg_name} ({bg}): {r:.2f}:1 — {'PASS' if r>=4.5 else 'FAIL'}")
