"""Verify the Compose Postgres probe on fresh and initialized databases.

Run from the repository root with `uv run python scripts/verify_postgres_startup.py`.
Only creates/removes its own containers and anonymous data volumes; no published ports.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from pathlib import Path

import yaml


def docker(*args: str) -> str:
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=True, timeout=60
    )
    # PostgreSQL writes its server log to stderr; both streams are mandatory.
    return result.stdout + result.stderr


def await_healthy(name: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        state = json.loads(docker("inspect", name))[0]["State"]
        if state["Health"]["Status"] == "healthy":
            return
        if not state["Running"]:
            raise AssertionError("Postgres exited before readiness")
        time.sleep(0.1)
    raise AssertionError("Postgres did not become healthy")


def main() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
    postgres = compose["services"]["postgres"]
    probe = postgres["healthcheck"]["test"][1].replace("$$", "$")
    for attempt in range(5):
        name = f"numra-web06a-health-{uuid.uuid4().hex}"
        docker(
            "run",
            "-d",
            "--name",
            name,
            "-e",
            "POSTGRES_USER=numra",
            "-e",
            "POSTGRES_PASSWORD=healthcheck_test_only",
            "-e",
            "POSTGRES_DB=numra",
            "--health-cmd",
            probe,
            "--health-interval",
            "100ms",
            "--health-timeout",
            "3s",
            "--health-retries",
            "200",
            postgres["image"],
        )
        try:
            for phase in ["fresh", "restart"]:
                if phase == "restart":
                    docker("restart", name)
                await_healthy(name)
                logs = docker("logs", name)
                if phase == "restart":
                    assert "Skipping initialization" in logs  # same initialized data volume
                errors = [
                    line
                    for line in logs.splitlines()
                    if re.search(r"Traceback|Unhandled|FATAL|panic", line, re.IGNORECASE)
                ]
                assert not errors, "\n".join(errors)
                docker("exec", name, "psql", "-U", "numra", "-d", "numra", "-c", "SELECT 1")
                closed = subprocess.run(
                    ["docker", "exec", name, "nc", "-z", "-w", "1", "127.0.0.1", "5433"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                assert closed.returncode != 0  # TCP probe must reject an unavailable port
                print(
                    f"{attempt + 1}/5 {phase}: healthy, SQL available, strict log audit clean",
                    flush=True,
                )
        finally:
            docker("rm", "-f", "-v", name)


if __name__ == "__main__":
    main()
