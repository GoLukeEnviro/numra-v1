# AVENYTH Web â€” Execution State

- **PLAN_VERSION:** 2
- **CURRENT_MAIN_SHA:** 8808c033a36c43fb394f8ed3d867f6fa3a7685ce
- **CURRENT_SEGMENT:** SEGMENT_C
- **CURRENT_PR:** PR-WEB-06a (in Umsetzung, noch kein PR)
- **CURRENT_BRANCH:** codex/pr-web-06a
- **LAST_MERGED_PR:** #52 (WEB-06-Plan)
- **LAST_GREEN_MAIN_SHA:** 8808c033a36c43fb394f8ed3d867f6fa3a7685ce
- **CURRENT_TASK:** A1â€“A10 Backend, Migration, Contract und Tests implementieren.
- **NEXT_ACTION:** Bestandsmigration und echte DB-ParallelitÃ¤t testen, Reviewbefunde beheben.
- **HUMAN_GATE_REQUIRED:** false (Umsetzung und Merge vom Nutzer freigegeben)
- **OPEN_BLOCKERS:** none
- **LAST_UPDATED_AT:** 2026-09-10

## Checkpoint WEB-06a

Eigener Worktree `E:/VS-code-Projekte-5.2025/numra-v1-pr-web-06a`, Basis #52.
Originalcheckout und untracked `.planning/` erhalten; keine fremden Arbeiten verÃ¤ndert.
Separater Testcontainer `numra-web06a-postgres`, Port 5546, nur synthetische Daten.
Snapshots, Versionierung, Idempotenz, Workspace-Lock, Routen und Client in Arbeit.
UnabhÃ¤ngiger Vorab-/Zwischenreview erfolgt; noch kein Abschlussreview.
Nachgewiesen: `/current`-Regression rot (422 statt 200) â†’ grÃ¼n nach Route-Fix.
Final lokal: 86 relevante Backend-Tests, 10 Alembic-Migrationsfälle und 244 Web-Tests grün.
Breite Vorab-Suite: 740 grün, ein korrigierter Test-Order-Befund (final gezielt grün).
Noch offen: PR-CI, Merge und Post-Merge-CI. WEB-06b bleibt unimplementiert.
