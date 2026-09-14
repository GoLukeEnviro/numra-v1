# Handoff: MOBILE-12C — Native Today/Daily-Brief

Stand: 2026-09-14, ca. 22:20 UTC. Verifiziert durch direkten `git status`/`git diff`
im Checkout unmittelbar vor Erstellung dieses Dokuments — keine Behauptung ohne
Beleg.

## 1. Wo alles herkommt

`docs/planning/avenyth-web-execution-state.md` und
`.specify/feature-012c-mobile-today-brief/{spec,plan,tasks}.md` sind die
übergeordneten, bereits gemergten (`main` @ `b206870`) Planungsdokumente.
Dieses Dokument ist NUR der taktische Zwischenstand der laufenden
Implementierung, kein Ersatz für die Spec.

## 2. Lokaler Working-Tree-Zustand (verifiziert, JETZT)

```
Branch: feat/mobile12c-today-daily-brief
Tracking: origin/main (Branch selbst noch NICHT auf origin gepusht)
HEAD: b206870201df10f4980646c57d4dc73189993798 (= main, docs: MOBILE-12C Spec/Plan/Tasks (#83))
```

Working Tree ist NICHT sauber — 9 geänderte + 5 neue Dateien, **uncommittet**:

```
 M .specify/feature-012c-mobile-today-brief/tasks.md
 M apps/api/src/numra_api/deps.py
 M apps/api/src/numra_api/routes/calculations.py
 M apps/api/src/numra_api/routes/people.py
 M apps/mobile/App.tsx
 M openapi/numra-v1.json
 M packages/schema/src/generated/schema.d.ts
 M specs/v2/api-contract.md
 M uv.lock
?? apps/api/tests/integration/test_mobile_today.py
?? apps/mobile/src/__tests__/today-client.test.ts
?? apps/mobile/src/__tests__/today-state.test.ts
?? apps/mobile/src/api/today-client.ts
?? apps/mobile/src/screens/today-state.ts
```

216 Insertions / 45 Deletions in den geänderten Dateien (`git diff --stat`).

**Diese Änderungen dürfen NICHT verworfen werden** (kein `git reset --hard`,
`git clean`, `git checkout -- <datei>`, `git restore .`, `git stash drop`).
Zwei aufeinanderfolgende `godlike-code-master`-Subagenten wurden mitten in der
Verifikation extern gestoppt (nicht von mir absichtlich abgebrochen) — der
Code-Stand ist der Zwischenstand ihrer TDD-Arbeit, nicht vollständig
gegengeprüft.

## 3. Was NICHT verifiziert ist (ehrlich, nicht raten)

- **mypy strict**: NICHT VERIFIZIERT in diesem Zwischenstand.
- **Ruff format/lint**: NICHT VERIFIZIERT.
- **Volle Python-Testsuite inkl. Integrationstests gegen echte PostgreSQL**:
  NICHT VERIFIZIERT (Backend-Integrationstests brauchen eine laufende DB —
  ob eine verfügbar war, ist aus dem Subagenten-Bericht nicht restlos klar).
- **Mobile Lint/Typecheck/Tests**: NICHT VERIFIZIERT.
- **OpenAPI-Drift-Check**: NICHT VERIFIZIERT (obwohl `openapi/numra-v1.json`
  und `packages/schema/src/generated/schema.d.ts` bereits verändert wurden —
  das beweist nicht, dass sie automatisch/korrekt regeneriert statt manuell
  editiert wurden; das muss der nächste Agent selbst nachvollziehen).
- Die IDE-Diagnostics (Pyright) zeigten zwischenzeitlich `reportMissingImports`
  für zahlreiche Module in `deps.py`. Das ist mit hoher Wahrscheinlichkeit ein
  bekanntes Monorepo-venv-Auflösungsproblem des Editors (siehe Memory
  `numra-v1-worktree-lint-preflight`), keine echte Fehlermeldung — aber das
  wurde NICHT durch einen echten `mypy`/`pytest`-Lauf gegengeprüft. Erster
  Schritt für den nächsten Agenten: mit dem echten Testrunner prüfen, nicht
  dem Editor vertrauen.

## 4. Was inhaltlich umgesetzt wurde (laut Diff-Liste, ungeprüft im Detail)

Backend:
- `apps/api/src/numra_api/deps.py`: vermutlich die geplante
  `get_current_user_any_auth`-Dependency (Cookie-ODER-Bearer), siehe Plan §
  "Backend" Schritt 2.
- `apps/api/src/numra_api/routes/calculations.py`: Einsatz dieser Dependency
  an `/timing` und `/daily-brief` (6 Zeilen Diff — schlank, wie geplant).
- `apps/api/src/numra_api/routes/people.py`: **nicht im ursprünglichen Plan
  vorgesehen** — 11 Zeilen Diff, unklar warum diese Datei ebenfalls
  angefasst wurde. Erster Punkt, den der nächste Agent klären muss (Abweichung
  von der Spec dokumentieren oder zurücknehmen, falls nicht nötig).
- `apps/api/tests/integration/test_mobile_today.py` (neu): Bearer-Auth-Tests
  für die beiden Endpunkte.
- `openapi/numra-v1.json`, `packages/schema/src/generated/schema.d.ts`,
  `uv.lock`: vermutlich Folgeänderungen aus Regenerierung/`uv sync`.

Mobile:
- `apps/mobile/src/api/today-client.ts` (neu), `today-client.test.ts` (neu).
- `apps/mobile/src/screens/today-state.ts` (neu), `today-state.test.ts` (neu).
- `apps/mobile/App.tsx`: Verdrahtung (67 Zeilen Diff).

Doku:
- `.specify/feature-012c-mobile-today-brief/tasks.md`: teilweise abgehakt.
- `specs/v2/api-contract.md`: Auth-Extensions-Zusatz + Roadmap-Eintrag.

## 5. Nächste Schritte für den Coding-Agenten

1. `git status`/`git diff` erneut selbst prüfen — dieser Bericht ist ein
   Snapshot, kein Ersatz für eigene Verifikation.
2. Klären, warum `apps/api/src/numra_api/routes/people.py` verändert wurde
   (nicht im Plan) — Diff lesen, Notwendigkeit bewerten.
3. Echte Verifikation fahren (nicht Editor-Diagnostics vertrauen):
   - `uv run ruff format --check .`
   - `uv run ruff check .`
   - `uv run mypy apps/api/src packages/engine-numerology/src packages/engine-interpretation/src packages/engine-astrology/src`
   - Backend-Tests inkl. `test_mobile_today.py` — falls keine lokale
     PostgreSQL verfügbar ist, das explizit so vermerken und auf echte
     CI-Verifikation verweisen statt es als "getestet" zu behaupten.
   - `pnpm --filter @numra/mobile lint|typecheck|test`
   - OpenAPI-Drift-Check laut CI-Workflow (`.github/workflows/ci.yml`,
     Job `schema-and-openapi-drift`) lokal nachvollziehen.
4. Bei echten Fehlern: Root Cause fixen, nicht symptomatisch flicken.
5. Nur die zum Feature gehörenden Dateien explizit committen (kein
   `git add -A`), Commit-Message im Stil der vorherigen Increments.
6. Branch `feat/mobile12c-today-daily-brief` nach `origin` pushen.
7. PR gegen `main` öffnen, Titel `MOBILE-12C: Native Today/Daily-Brief
   (read-only)`.
8. **PR NICHT mergen.** Grund: `main`-Merges deployen auf dieser
   Produktions-VPS automatisch (siehe Abschnitt 6) — Merge-Freigabe muss
   explizit vom Nutzer kommen, pro PR, nicht mehr automatisch.
9. Abschlussbericht mit denselben Feldern wie in Abschnitt 7 unten.

## 6. WICHTIG — Produktions-Realität (heute neu verifiziert, nicht annehmen)

`numra-v1` läuft produktiv auf der VPS **HermesTrader**
(`hermestrader-root` SSH-Alias, Tailscale `100.96.132.39`,
`hermestrader.taile6801f.ts.net`), verwaltet vom Systemuser `deploy` unter
`/opt/numra`. Ein systemd-Timer (`numra-update.timer`, alle ~11 Minuten)
prüft `origin/main` und deployt **automatisch und ohne weitere Rückfrage**,
sobald der Commit sich ändert — mit eigenen Gates (Container-Recreate,
Alembic-Migration, interner Health-Check, 24 "Golden-Smoke"-Checks,
Log-Audit auf Secret-Leaks), erst danach wird `deployed_sha` geschrieben.

Verifizierter Stand zum Zeitpunkt dieses Dokuments:
`origin/main` = VPS-Repo-HEAD = `deployed_sha` = `b206870...` (alle drei
identisch, Deploy erfolgreich, alle Container `healthy`).

Zugriff (heute richtiggestellt — NICHT über Caddy, sondern über
**`tailscale serve`**, tailnet-only):
```
https://hermestrader.taile6801f.ts.net:8443/            → NUMRA Web
https://hermestrader.taile6801f.ts.net:8443/api/v1/...  → NUMRA API (same-origin-Proxy)
```
Verifiziert: `/` → 200, `/api/v1/health/live` → `{"status":"live"}`.

Backups laufen täglich (`numra-backup.timer`), mit echter
`pg_restore --list`-Integritätsprüfung, zuletzt erfolgreich.

**Konsequenz für jeden Merge nach `main`:** Ab sofort gilt — jeder Merge ist
eine produktionswirksame Aktion und braucht explizite Freigabe des Nutzers,
nicht nur "CI grün + Review sauber" wie in den Increments zuvor. Diese Regel
wurde heute neu eingeführt, nachdem sich herausstellte, dass zuvor mehrere
Merges (WEB-09 bis MOBILE-12B-Kette, diverse Dependency-Updates, PR #74)
unwissentlich sofort automatisch deployt wurden — im Nachhinein verifiziert
ohne Schaden, aber ohne vorherige bewusste Freigabe.

Weitere Workloads auf derselben VPS (Freqtrade-Instanzen, Rainbow, Hermes)
dürfen durch NUMRA-Arbeit niemals gestört werden — nur das Compose-Projekt
`numra-prod` mit expliziter `-f /opt/numra/compose.production.yml` ansprechen,
nie generische `docker`-Befehle ohne Projekt-Scope.

Die `/etc/numra/numra.env`-Datei ist `root:root 600` — nur mit `root`
lesbar, nicht mit `deploy`. Lesende Compose-Befehle (`ps`, `logs`) daher als
`root` ausführen, niemals den Inhalt der Datei ausgeben.

## 7. Erwarteter Abschlussbericht-Rahmen für den nächsten Agenten

```
Lokaler Branch:
Commit-SHA (neu):
PR:
Working Tree sauber:
Ruff/mypy:
Backend-Tests (lokal / CI):
Mobile-Tests:
OpenAPI-Drift:
Required CI:
Merge durchgeführt: (sollte NEIN sein, außer explizite Freigabe erhalten)
Abweichungen von der Spec (inkl. routes/people.py-Änderung):
offene Punkte:
```

Unbekannte Werte ausdrücklich als „NICHT VERIFIZIERT" kennzeichnen.
