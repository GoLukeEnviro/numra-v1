# CI-Instabilität `system-journey.spec.ts` — Root Cause & Behebung

**Status:** BEWIESEN UND BEHOBEN (PR #44, `main` @ `1f70b65`)
**Untersuchung:** 2026-09-10, drei Runden. Arbeitslog (lokal, nicht Teil des Repos):
`.planning/debug/ci-e2e-flaky-system-journey.md`.

## Symptom

Bei den `main`-Merges von PR-WEB-02/03/04 schlug der **jeweils erste**
CI-Lauf fehl, ein sofortiger Re-Run desselben Commits war grün — drei
unterschiedliche Fehlerbilder:

| Merge | Job | Fehler |
|---|---|---|
| PR-WEB-02 (`abeaa82`) | system-e2e | `POST /v1/people` 201 → Folgeschritt bleibt auf `/people/new`, `get_person` findet die Person nicht |
| PR-WEB-03 (`ee205ba`) | docker-compose-e2e | `POST /v1/relationships` 201 → `GET /v1/relationships/{id}` 404 |
| PR-WEB-04 (`f947976`) | docker-compose-e2e | `POST /v1/account/delete-all` 204 → `POST /v1/auth/register` 409 `EMAIL_ALREADY_REGISTERED` |

Gemeinsames Muster: eine Mutation liefert `2xx` **mit gültiger ID**, der
unmittelbar folgende Request, der genau diese Mutation lesen/voraussetzen
muss, sieht sie **nicht**.

## Root Cause

Die DB-Transaktion eines Requests wird **erst nach dem Senden der
Response** committed.

`numra_api.deps.get_db` ist eine FastAPI *dependency with yield* und
committet in ihrer Exit-Hälfte (`await session.commit()` nach `yield`).
Diese Exit-Hälfte lief per FastAPI-Default-Scope (`request`) im
Request-`ExitStack`, der erst nach `await response(scope, receive, send)`
schließt (`fastapi/routing.py`, 0.141.1). Zusätzlich schoben die fünf
`starlette.middleware.base.BaseHTTPMiddleware`-Subklassen in
`middleware/security.py` den yield-Teardown ohnehin hinter die vollständig
gesendete Response (bekannter Effekt, `fastapi/fastapi#5597`, `#8407`).

Folge: Jede Write-Route liefert ihre `2xx`-Antwort, **bevor** ihr eigener
COMMIT ausgeführt ist. Der unmittelbar folgende Request läuft auf einer
frischen DB-Connection (eigene Session pro Request) und sieht die noch
nicht committete Zeile nicht → `404` bzw. `409`.

Das ist **kein reines CI-Artefakt, sondern ein latenter
Produktions-Korrektheitsfehler**. Latenz auf CI-Runnern (Kalt-Start,
Last) verbreitert nur das Zeitfenster. „Ressourcen-Kontention" war also
**Trigger, nicht Ursache**.

Die bestehende 390er-Testsuite verdeckte den Bug: httpx `ASGITransport`
draint die Response in-process und zieht dabei den verzögerten Teardown
vor — der Commit ist „zufällig" fertig, bevor der nächste Aufruf beginnt.

## Beweis

* **FastAPI-Quellcode:** `fastapi/dependencies/utils.py` (`if
  sub_dependant.scope == "function": use_astack = function_astack`),
  `fastapi/param_functions.py` (Doku zu `scope="function"`: beendet die
  yield-Dependency „before the response is sent back to the client").
* **Deterministische Reproduktion:**
  `apps/api/tests/integration/test_yield_commit_ordering.py` — echter
  `uvicorn.Server` (nicht `ASGITransport`), künstlich um 0,75 s
  verlangsamter `AsyncSession.commit`, Sequenz `login → POST /v1/people
  (201) → GET /v1/people/{id}`.
  * **ohne Fix:** deterministisch `404` (unabhängig gegengeprüft via
    `git checkout f947976 -- apps/api/src/numra_api` + Test → `404`)
  * **mit Fix:** `200`

## Behebung (PR #44)

1. `Depends(get_db)` → `Depends(get_db, scope="function")` an 126 Stellen
   (26 Routen-Dateien + `deps.py`). `scope="function"` beendet die
   yield-Dependency **vor** dem Response-Send → COMMIT abgeschlossen,
   bevor die `2xx`-Antwort den Prozess verlässt.
2. Alle fünf Middlewares von `BaseHTTPMiddleware` auf **pure ASGI**
   portiert (verhaltensidentisch — unabhängig reviewt: Security-Header,
   Correlation-ID, Access-Log, Body-Limit, Origin-Validierung,
   CSRF-Interaktion, Exception-Propagation). Defense-in-depth zu (1).
3. Diagnosefähigkeit für eine etwaige Wiederkehr:
   * `docker-compose-e2e` + `system-e2e` laden bei jedem Lauf **gescrubte**
     Failure-Artefakte hoch (compose-/Service-Logs, Playwright-HTML-Report).
     Binäre Trace-Zips werden nicht hochgeladen (der Klartext-Scrub kann
     nicht hineinsehen). Secret-Werte werden vor dem Upload ersetzt.
   * `[CI-DIAG]`-Logging in `get_db` (Correlation-ID, `txid_current()`,
     Commit-Dauer) — **nur** bei `ENVIRONMENT=test`, Produktionspfad ist
     der unveränderte Fast-Path.

## Verifikation

* `pytest apps/api/tests` → **390 passed** (inkl. neuem Regressionstest).
* Regressionstest rot ohne Fix / grün mit Fix (s. o.).
* Unabhängiger Code-Review (Middleware-Port + Scope-Sweep): verhaltens­-
  identisch bestätigt; zwei MEDIUM-Auflagen (Trace-Scrub, DB-Passwort-Scrub)
  vor Merge behoben.
* **Real-Environment (die Jobs, die zuvor flaky waren):**

| Lauf | Commit | `docker-compose-e2e` | `system-e2e` | `playwright` |
|---|---|---|---|---|
| PR #44 CI | — | grün (1. Lauf) | grün (1. Lauf) | grün (1. Lauf) |
| `main` post-merge #44 | `1f70b65` · Run `34453209752` | grün (1. Lauf) | grün (1. Lauf) | grün (1. Lauf) |
| PR #45 CI | — | grün (1. Lauf) | grün (1. Lauf) | grün (1. Lauf) |
| `main` post-merge #45 | `40fea15` · Run `34454947452` | grün (1. Lauf) | grün (1. Lauf) | grün (1. Lauf) |

Die Signatur „erster Lauf rot, Re-Run grün" ist seit dem Fix nicht wieder
aufgetreten.

## Restunsicherheit

* Der deterministische Test beweist Mechanismus **und** Fix, aber die
  genaue Latenz-Kette auf GitHub-Runnern (Disk-I/O, Noisy-Neighbor-
  Scheduling) wurde nie direkt gemessen. Falls nach dem Fix wider Erwarten
  erneut ein Stale Read auftritt, liefern die neuen `[CI-DIAG]`-Logs +
  Playwright-Traces die Daten zur Zweitanalyse — **nicht** durch stillen
  Re-Run zu grün normalisieren.
* `scope="function"` ist ein jüngeres FastAPI-Feature (0.115+). Es gibt
  aktuell keine `StreamingResponse`/SSE/`BackgroundTasks`-Route, bei der
  die Session vor Stream-Ende geschlossen würde (im Review geprüft). Käme
  eine hinzu, wäre Fix (2) allein — pure ASGI-Middleware — die
  konservativere Teilabsicherung.
