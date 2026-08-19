#!/usr/bin/env python3
"""Export the FastAPI app's OpenAPI schema to openapi/numra-v1.json.

Run with ``--check`` in CI to fail if the committed file would change (schema drift).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
OUTPUT_PATH = REPO_ROOT / "openapi" / "numra-v1.json"


def build_schema() -> dict:
    sys.path.insert(0, str(API_SRC))
    from numra_api.app import create_app

    app = create_app()
    schema: dict = app.openapi()
    return schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    schema = build_schema()
    rendered = json.dumps(schema, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text() != rendered:
            print(f"DRIFT: {OUTPUT_PATH} is stale — run scripts/export_openapi.py", file=sys.stderr)
            return 1
        print("OpenAPI schema up to date.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered)
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
