#!/usr/bin/env python3
"""Pack and gate the AVENYTH design preview for GitHub Actions.

Stdlib only. Exit 0 with skip if docs/design/ preview files are absent
(workflow may live on main before the concept PR merges).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "design"
OUT = ROOT / "dist" / "design-preview"
FORBIDDEN = (
    "lukas-springer",
    "Lukas Springer",
    "1986-06-18",
    "18.06.1986",
)


class _Html(HTMLParser):
    def error(self, message: str) -> None:  # pragma: no cover
        raise RuntimeError(message)


def main() -> int:
    preview = DESIGN / "avenyth-redesign-preview.html"
    concept = DESIGN / "avenyth-redesign-concept.md"
    contrast = DESIGN / "tools" / "contrast_check.py"

    if not preview.is_file():
        print("skip: docs/design/avenyth-redesign-preview.html not present")
        return 0

    text = preview.read_text(encoding="utf-8")
    _Html().feed(text)
    print("html_ok")

    # Only the preview HTML is a user-facing sample. The concept may name the
    # forbidden fixture in order to ban it.
    lowered = text.lower()
    hits = [n for n in FORBIDDEN if n.lower() in lowered]
    if hits:
        print("pii_forbidden:", ", ".join(hits), file=sys.stderr)
        return 1
    print("pii_ok")

    if "noindex" not in text.lower():
        print("missing noindex on preview", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(preview, OUT / preview.name)
    if concept.is_file():
        shutil.copy2(concept, OUT / concept.name)

    if contrast.is_file():
        result = subprocess.run(
            [sys.executable, str(contrast)],
            check=True,
            capture_output=True,
            text=True,
        )
        (OUT / "contrast.txt").write_text(result.stdout, encoding="utf-8")
        print(result.stdout)

    print("packed", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
