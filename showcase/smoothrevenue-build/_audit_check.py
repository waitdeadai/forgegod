#!/usr/bin/env python3
"""Accessibility audit checks for smoothrevenue.com"""

def luminance(r, g, b):
    def f(x):
        x = x / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def contrast(l1, l2):
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

# Check tertiary text contrast on dark background
# BG: #0a0a0b = (10, 10, 11)
bg = luminance(10, 10, 11)

# Current: #8888a0 = (136, 136, 160)
current_tertiary = luminance(136, 136, 160)
print(f"Text tertiary (#8888a0) contrast: {contrast(bg, current_tertiary):.2f}:1")

# Fix: Need to increase brightness for 4.5:1 ratio
# Calculate needed brightness for 4.5:1
# For 4.5:1: darker = (lighter + 0.05) / 4.5 - 0.05
# We need lighter text on dark bg
# For pure white (1.0) vs dark: white is lighter
white = luminance(255, 255, 255)
print(f"White (#fff) contrast: {contrast(white, bg):.2f}:1")

# Minimum brightness needed for 4.5:1
# (1.0 + 0.05) / ratio = max luminance
# We need text on dark background
# For 4.5:1: max_lum = (lighter_lum + 0.05) / 4.5
# Since bg is darker (0.002), text needs to be lighter
# 4.5:1 means text_lum >= (bg_lum + 0.05) * 4.5 - 0.05
needed_lum = (bg + 0.05) * 4.5 - 0.05
print(f"Needed luminance for 4.5:1: {needed_lum:.4f}")

# Current tertiary is too low - need brighter
# Let's find approximate RGB for 4.5:1
for val in range(136, 220):
    lum = luminance(val, val, val)
    ratio = contrast(lum, bg)
    if ratio >= 4.5:
        hex_color = "#" + ("%02x" % val) * 3
        print(f"Minimum for 4.5:1 - {hex_color} = RGB({val},{val},{val}), "
              f"ratio: {ratio:.2f}:1")
        break
