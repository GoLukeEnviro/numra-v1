#!/usr/bin/env python3
"""Single entry point orchestrating every NUMRA quality gate.

Usage: uv run python scripts/verify.py [--skip-docker] [--skip-playwright]

Runs each gate as a real subprocess and reports PASS/FAIL/SKIPPED per gate — never
fabricates a result. Exits non-zero if any non-skipped gate fails.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class GateResult:
    name: str
    status: str  # PASS | FAIL | SKIPPED
    detail: str = ""


def run(name: str, cmd: list[str], *, cwd: Path = REPO_ROOT) -> GateResult:
    print(f"\n=== {name} ===")
    print(f"$ {' '.join(cmd)}  (cwd={cwd})")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode == 0:
        return GateResult(name, "PASS")
    return GateResult(name, "FAIL", f"exit code {result.returncode}")


def skip(name: str, reason: str) -> GateResult:
    print(f"\n=== {name} ===\nSKIPPED: {reason}")
    return GateResult(name, "SKIPPED", reason)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--skip-playwright", action="store_true")
    args = parser.parse_args()

    results: list[GateResult] = []

    results.append(run("ruff format --check", ["uv", "run", "ruff", "format", "--check", "."]))
    results.append(run("ruff check", ["uv", "run", "ruff", "check", "."]))
    results.append(
        run(
            "mypy strict",
            [
                "uv",
                "run",
                "mypy",
                "apps/api/src",
                "packages/engine-numerology/src",
                "packages/engine-interpretation/src",
                "packages/engine-astrology/src",
            ],
        )
    )
    results.append(
        run(
            "engine coverage gate (>=90%)",
            [
                "uv",
                "run",
                "pytest",
                "packages/engine-numerology/tests",
                "-q",
                "--cov=packages/engine-numerology/src/numra_numerology",
                "--cov-fail-under=90",
            ],
        )
    )
    results.append(
        run("full python test suite", ["uv", "run", "pytest", "packages", "apps/api/tests", "-q"])
    )
    results.append(
        run("openapi drift check", ["uv", "run", "python3", "scripts/export_openapi.py", "--check"])
    )

    if shutil.which("pnpm"):
        results.append(run("web lint", ["pnpm", "--filter", "@numra/web", "lint"]))
        results.append(run("web typecheck", ["pnpm", "--filter", "@numra/web", "typecheck"]))
        results.append(
            run("web unit tests", ["pnpm", "--filter", "@numra/web", "test", "--", "--run"])
        )
        results.append(run("web build", ["pnpm", "--filter", "@numra/web", "build"]))
        if args.skip_playwright:
            results.append(skip("web e2e (Playwright)", "--skip-playwright"))
        else:
            results.append(
                run(
                    "web e2e (Playwright)",
                    ["pnpm", "--filter", "@numra/web", "exec", "playwright", "test"],
                )
            )
        results.append(run("pdf service tests", ["pnpm", "--filter", "@numra/pdf", "test"]))
    else:
        for gate in (
            "web lint",
            "web typecheck",
            "web unit tests",
            "web build",
            "web e2e (Playwright)",
            "pdf service tests",
        ):
            results.append(skip(gate, "pnpm not available"))

    if args.skip_docker or not shutil.which("docker"):
        results.append(skip("docker compose config", "docker not available or --skip-docker"))
    else:
        results.append(run("docker compose config", ["docker", "compose", "config", "--quiet"]))

    print("\n" + "=" * 60)
    print("NUMRA VERIFY SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"{r.status:8s} {r.name}" + (f"  ({r.detail})" if r.detail else ""))

    failed = [r for r in results if r.status == "FAIL"]
    if failed:
        print(f"\n{len(failed)} gate(s) FAILED.")
        return 1
    print("\nAll non-skipped gates PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
