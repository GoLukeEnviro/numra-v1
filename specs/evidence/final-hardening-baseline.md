# Final Hardening — Baseline

## Recon

```
$ git status --short
(clean)
$ git branch --show-current
main   (before creating fix/numra-v1-production-completion)
$ git rev-parse HEAD
574a74ff92f69e54cf371af81bfe3de53c936b18
$ git log --oneline -10
574a74f fix(security): bump vitest to ^3.2.6, resolving the critical arbitrary-file-read advisory
fe5465e feat: Phase 6 — PDF service, Docker, CI, ADRs, README, final verification
68d3b6b feat: Phase 5 (web frontend) + account delete-all (Phase 6 privacy)
05c7eca feat: Phase 4 — long-form report pipeline (AgentWrite) + Postgres job queue worker
d3ec4c6 feat: Phase 2 (API/DB/OpenAPI) + Phase 3 (knowledge/interpretation/LLM adapter)
3d35a29 feat: Phase 1 — deterministic numerology engine, 104 tests, 100% coverage
60cc921 docs: Phase 0 — Canon-Spec, JSON-Schema, Lukas-Springer Golden Fixture
```

Worktree was clean → created branch `fix/numra-v1-production-completion` from this HEAD.

## Baseline verification (before any hardening changes)

```
$ uv sync --all-packages --all-groups
Resolved 64 packages — Audited 61 packages

$ pnpm install --frozen-lockfile
Lockfile is up to date — Already up to date

$ python3 scripts/verify.py --skip-docker --skip-playwright
PASS     ruff format --check
PASS     ruff check
PASS     mypy strict
PASS     engine coverage gate (>=90%)
PASS     full python test suite
PASS     openapi drift check
PASS     web lint
PASS     web typecheck
PASS     web unit tests
PASS     web build
SKIPPED  web e2e (Playwright)  (--skip-playwright)
PASS     pdf service tests
SKIPPED  docker compose config  (docker not available or --skip-docker)
All non-skipped gates PASSED.
```

Baseline is fully green — no pre-existing local-gate failures to fix. The work in this
pass is closing real *architectural/product gaps* identified in the follow-up
directive (production LLM provider wiring, retry semantics, truthful health checks,
export/PDF product integration, Today/Identity Timeline/Reports frontend, rate
limiting, security hardening, real system E2E), not repairing broken gates.

## Known pre-existing environment limitations (unchanged from prior session)

- No running Docker daemon in this sandbox (`docker info` fails) — Docker
  build/up/health verification remains `NOT_VERIFIED` for the same reason documented in
  `specs/evidence/phase-6.md`.
- No `OLLAMA_API_KEY` configured — live Ollama Cloud generation remains `NOT_VERIFIED`.
- No `gh` CLI / GitHub Actions execution access from this session for this repo beyond
  the MCP GitHub tools already in scope — real GitHub Actions run status will be
  recorded as `NOT_VERIFIED` unless a PR's checks can actually be observed.
