#!/usr/bin/env python3
"""Recompute WCAG 2.1 contrast ratios for the AVENYTH redesign concept.

Stdlib only. Ratios use relative luminance (WCAG 2.1 §1.4.3).
Run: python3 docs/design/tools/contrast_check.py
"""

from __future__ import annotations

import sys

PALETTE = {
    "noir": "0B0B0F",
    "obsidian": "13131A",
    "obsidian_plus": "191921",
    "gold": "C8A96B",
    "bronze": "8F6B3E",
    "ivory": "F2EBDD",
    "parchment": "E8E3D8",
    "ash": "9E98A4",
    "plum": "604B72",
    "plum_light": "B39BCF",
    "ui_line": "6B6775",
    "cinnabar": "E28B7C",
    "sage": "8FBF9F",
    "paper": "EEECF1",
    "sheet": "F8F7FA",
    "ink": "1C1B24",
    "old_gold": "7A5B1F",
    "line_light": "827D8C",
    "ultramarine": "2536A6",
    "ultramarine_dark": "9AA6FF",
    "ochre": "7C5A10",
    "ochre_dark": "D6AA4E",
    "film": "ECEEE9",
    "graphite": "22252A",
    "night": "14171D",
    "chalk": "E3E6E8",
}


def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.strip().lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def channel(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


PAIRS = [
    ("gold on noir", "gold", "noir"),
    ("ivory on noir", "ivory", "noir"),
    ("parchment on noir", "parchment", "noir"),
    ("ash on noir", "ash", "noir"),
    ("plum on noir (text)", "plum", "noir"),
    ("plum_light on noir", "plum_light", "noir"),
    ("ivory on plum", "ivory", "plum"),
    ("bronze on noir (text)", "bronze", "noir"),
    ("ui_line on noir", "ui_line", "noir"),
    ("cinnabar on noir", "cinnabar", "noir"),
    ("sage on noir", "sage", "noir"),
    ("ink on paper", "ink", "paper"),
    ("old_gold on paper", "old_gold", "paper"),
    ("plum on paper", "plum", "paper"),
    ("line_light on paper", "line_light", "paper"),
    ("graphite on film", "graphite", "film"),
    ("ultramarine on film", "ultramarine", "film"),
    ("ochre on film", "ochre", "film"),
    ("chalk on night", "chalk", "night"),
    ("ultramarine_dark on night", "ultramarine_dark", "night"),
    ("ochre_dark on night", "ochre_dark", "night"),
    ("ivory button on obsidian", "ivory", "obsidian"),
    ("ivory button on obsidian_plus", "ivory", "obsidian_plus"),
    ("noir text on ivory button", "noir", "ivory"),
    ("ui_line on obsidian", "ui_line", "obsidian"),
    ("ui_line on obsidian_plus", "ui_line", "obsidian_plus"),
]


def main() -> int:
    print("WCAG 2.1 contrast ratios — AVENYTH redesign palette")
    print("AA text 4.5:1 · AA large/UI 3:1 · AAA 7:1")
    print()
    for label, fg, bg in PAIRS:
        ratio = contrast(PALETTE[fg], PALETTE[bg])
        aa = "AA" if ratio >= 4.5 else ("AA-large" if ratio >= 3.0 else "fail")
        print(f"{label:32} {ratio:5.2f}:1  {aa}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
