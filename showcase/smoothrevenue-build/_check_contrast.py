"""Check WCAG 2.1 AA contrast ratios for Smoothrevenue color tokens."""

from __future__ import annotations


def luminance(hex_color: str) -> float:
    """Calculate relative luminance of a hex color."""
    r = int(hex_color[1:3], 16) / 255
    g = int(hex_color[3:5], 16) / 255
    b = int(hex_color[5:7], 16) / 255
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate contrast ratio between two hex colors."""
    l1 = luminance(hex1)
    l2 = luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> None:
    """Run contrast checks against all key color tokens."""
    bg_base = "#0a0a0b"
    bg_surface = "#111114"
    bg_elevated = "#18181c"

    colors = {
        "text-primary": "#f0f0f5",
        "text-secondary": "#c8c8d0",
        "text-tertiary": "#8888a0",
        "accent-orange": "#ff6b35",
        "accent-blue": "#3b82f6",
    }

    backgrounds = {
        "bg-base": bg_base,
        "bg-surface": bg_surface,
        "bg-elevated": bg_elevated,
    }

    all_pass = True
    for bg_name, bg_color in backgrounds.items():
        print(f"\n--- On {bg_name} ({bg_color}) ---")
        for name, color in colors.items():
            ratio = contrast_ratio(color, bg_color)
            passes_normal = ratio >= 4.5
            passes_large = ratio >= 3.0
            status_n = "PASS" if passes_normal else "FAIL"
            status_l = "PASS" if passes_large else "FAIL"
            if not passes_normal:
                all_pass = False
            print(
                f"  {name} ({color}): {ratio:.2f}:1 — "
                f"AA normal: {status_n}, AA large: {status_l}"
            )

    if all_pass:
        print("\nAll normal text contrast checks PASS.")
    else:
        print("\nSome normal text contrast checks FAIL.")


if __name__ == "__main__":
    main()
