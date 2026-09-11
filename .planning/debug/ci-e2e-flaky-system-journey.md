---
status: awaiting_human_verify
trigger: "Root-Cause-Analyse wiederkehrender CI-Instabilitaet apps/web/e2e-system/system-journey.spec.ts (3 verschiedene Fehler in PR-WEB-02/03/04, jeweils erster Lauf rot, Re-Run gruen)"
created: 2026-09-10T00:00:00Z
updated: 2026-09-10T23:59:00Z
---

## Current Focus

hypothesis: CONFIRMED (deterministisch reproduziert + Fix verifiziert). Der Commit
  der Request-Transaktion laeuft NACH dem Senden der Response, weil er in der
  Exit-Haelfte einer FastAPI "dependency with yield" (`numra_api.deps.get_db`,
  `await session.commit()` nach `yield`) steckt. FastAPI registriert diese
  Exit-Haelfte per Default auf dem `request`-scope-ExitStack, der erst nach
  `await response(scope, receive, send)` schliesst (fastapi/routing.py ~Z.140-146,
  0.141.1). Zusaetzlich haben die 5 `BaseHTTPMiddleware`-Subklassen in
  middleware/security.py diesen Effekt verschaerft/garantiert
  (fastapi/fastapi#5597, #8407: Teardown erst nach vollstaendig gesendetem Body).
  Ergebnis: Write-Route liefert 2xx + ID -> COMMIT noch offen -> unmittelbar
  folgender Request auf frischer DB-Connection sieht die Zeile nicht.
  Kalt-Start/CI-Last verbreitern nur das Zeitfenster; der Bug ist immer da, wird
  aber von der 350er-Testsuite verdeckt (httpx ASGITransport draint die Response
  in-process, wodurch der verzoegerte Teardown vorher fertig wird).
test: Deterministischer Regressionstest
  apps/api/tests/integration/test_yield_commit_ordering.py -- echter uvicorn-Server
  (nicht ASGITransport) + kuenstlich verlangsamter COMMIT (0,75s) + Follow-up-Read
  direkt nach dem 201. Ohne Fix: reproduzierbar 401/404 (stale read). Mit Fix
  (`Depends(get_db, scope="function")` + pure-ASGI-Middleware): 200. 390/390
  apps/api-Tests gruen mit Fix.
next_action: Human-Verify: docker-compose-e2e + system-e2e auf dem Branch
  chore/ci-coldstart-diagnostics mehrfach (>=3x) gruen sehen; danach Bericht nach
  resolved/ verschieben. Bei erneutem stale read: neue [CI-DIAG]-Artefakte
  (get_db-Commit-Korrelation + Playwright-Traces) auswerten.

## Symptoms

expected: system-journey.spec.ts sollte bei jedem CI-Lauf deterministisch gruen sein, da workers:1 und einziger Test.
actual: Bei den letzten 3 main-Merges (PR-WEB-02/03/04) schlug der jeweils ERSTE CI-Lauf mit 3 unterschiedlichen Fehlern fehl; sofortiger Re-Run (gleicher Commit) war jedes Mal gruen.
errors: |
  1. PR-WEB-02 (Run 34379732294): expect(page).toHaveURL(/\/analysis\/[0-9a-f-]{36}$/) faellt, Seite bleibt /people/new, Zeile ~153.
  2. PR-WEB-03 (Run 34389541930, docker-compose-e2e): expect(page.getByText(/Kompatibilitaets-Prozentsatz/i)).toBeVisible() Timeout 15000ms bei /relationships/{id}, Zeile ~187.
  3. PR-WEB-04 (Run 34410729477, docker-compose-e2e): expect(reRegisterResponse.status()).toBe(201) erhaelt 409 EMAIL_ALREADY_REGISTERED bei Re-Registrierung nach Delete-All, Zeile 218.
reproduction: Deterministisch via apps/api/tests/integration/test_yield_commit_ordering.py (echter uvicorn + verlangsamter Commit). NICHT reproduziert wurde in CI-Umgebung per 5 Kalt-Start-Docker-Laeufen -- siehe Evidence, war nach dem deterministischen Nachweis auch nicht mehr noetig.
started: PR-WEB-02 (erster beobachteter Fall) -- Bug latent seit d3ec4c6 (get_db + BaseHTTPMiddleware beide seit Beginn), erst durch die neuen realen System-Journey-Tests (schnelle write-then-read ueber Request-Grenzen gegen echten Server) sichtbar geworden.

## Eliminated

- hypothesis: "Ressourcen-Kontention ist die Ursache."
  evidence: Nur Trigger, nicht Ursache. Der stale read ist auch ohne jede
    Kontention 100% reproduzierbar, sobald das Zeitfenster zwischen
    "Response gesendet" und "COMMIT ausgefuehrt" kuenstlich aufgezogen wird
    (verlangsamter Commit im Regressionstest). CPU/RAM-Druck auf CI-Runnern
    verbreitert dieses Fenster nur.
  timestamp: 2026-09-10

- hypothesis: "Code-Review von routes/deps/db schliesst Transaktions-/Session-Probleme aus."
  evidence: Falsch. Jede Datei ist fuer sich korrekt; der Bug ist das
    Zusammenspiel aus (a) commit-nach-yield in get_db und (b) FastAPIs
    Default-scope "request" fuer yield-Teardown bzw. BaseHTTPMiddleware, die den
    Teardown hinter das Response-Senden schiebt. Nur Laufzeit-Instrumentierung
    (echter Server) hat es sichtbar gemacht.
  timestamp: 2026-09-10

## Evidence

- timestamp: 2026-09-10 (Runde 3 -- Root Cause)
  checked: fastapi/routing.py (0.141.1) request handler; fastapi/dependencies/utils.py
    Z.664-671 (`use_astack = request_astack; if sub_dependant.scope == "function":
    use_astack = function_astack`); fastapi/param_functions.py Z.2316-2340
    (Doku: scope="function" endet die yield-Dependency "before the response is sent
    back to the client"); middleware/security.py (5x BaseHTTPMiddleware).
  found: get_db (`async with sessionmaker() as session: yield session; await
    session.commit()`) wird ueber `Depends(get_db)` an 126 Stellen ohne scope
    aufgeloest -> Default-scope "request" -> `await session.commit()` laeuft im
    request_stack.__aexit__, also NACH `await response(scope, receive, send)`.
    Zusaetzlich verschiebt jede BaseHTTPMiddleware den Teardown ohnehin hinter das
    gesendete Response (bekannter starlette/fastapi-Effekt, #5597/#8407).
  implication: Jede Write-Route bestaetigt die 3 CI-Fehler mit demselben
    Mechanismus: POST /v1/people (flush, kein commit) -> 201 -> get_db-Teardown
    committet spaeter -> POST .../calculations::get_person auf neuer Session -> 404.
    Analog relationships (POST 201 -> GET /{id} 404) und account/delete-all
    (204 -> register::get_user_by_email sieht alte Email -> 409).

- timestamp: 2026-09-10 (Runde 3 -- deterministische Reproduktion)
  checked: apps/api/tests/integration/test_yield_commit_ordering.py -- echter
    uvicorn.Server auf freiem Port (ASGITransport verdeckt den Bug), AsyncSession.commit
    um 0,75s verlangsamt, Sequenz login -> POST /v1/people (201) -> GET
    /v1/people/{id}.
  found: OHNE Fix deterministisch rot: Follow-up-Request bekommt 401
    ("session not found") bzw. 404 -- die Transaktion des vorigen Requests war beim
    Senden seiner 2xx-Response noch nicht committed. MIT Fix deterministisch gruen (200).
  implication: Mechanismus + Fix bewiesen, unabhaengig von Kalt-Start-Timing.

- timestamp: 2026-09-10 (Runde 3 -- Regressionslauf)
  checked: `pytest apps/api/tests -q` (390 Tests) mit Fix.
  found: 390 passed. ruff format/check + mypy auf geaenderten Dateien sauber.
  implication: Pure-ASGI-Middleware-Portierung + scope="function" an allen 126
    Stellen ist regressionsfrei gegen die bestehende Suite.

- timestamp: 2026-09-10 (Runde 3 -- 5 Kalt-Start-Docker-Laeufe)
  checked: NICHT durchgefuehrt. Begruendung: Der deterministische Regressionstest
    ist strikt besseres Evidenzniveau als probabilistische Kalt-Starts (100%
    Reproduktion des exakten Mechanismus + Beweis, dass der Fix greift). Runde 2
    hatte bereits 13 valide Docker-Repro-Versuche ohne Reproduktion -- weitere
    blinde Laeufe waren laut Auftrag Punkt 3/4 explizit unerwuenscht.
  found: -
  implication: Real-Environment-Bestaetigung erfolgt jetzt guenstiger ueber die
    CI selbst: docker-compose-e2e + system-e2e laufen auf dem Branch mit den neuen
    Diagnose-Artefakten; >=3 gruene Laeufe = Verifikation.

## Resolution

root_cause: |
  Die DB-Transaktion eines Requests wird erst nach dem Senden der Response
  committed. `numra_api.deps.get_db` ist eine FastAPI "dependency with yield" und
  committet in ihrer Exit-Haelfte (`await session.commit()` nach `yield`). Diese
  Exit-Haelfte laeuft per FastAPI-Default (scope "request") im request-ExitStack,
  der erst nach `await response(...)` schliesst; zusaetzlich schieben die 5
  `BaseHTTPMiddleware`-Subklassen in middleware/security.py den yield-Teardown
  ohnehin hinter die vollstaendig gesendete Response (fastapi/fastapi#5597, #8407).
  Damit liefert jede Write-Route ihre 2xx-Antwort (mit gueltiger ID) BEVOR ihr
  eigener COMMIT ausgefuehrt ist. Der unmittelbar folgende Request laeuft auf einer
  frischen DB-Connection (eigene Session pro Request) und sieht die noch nicht
  committete Zeile nicht -> 404 bzw. 409. Latenz auf CI-Runnern (Kalt-Start, Last)
  verbreitert nur das Zeitfenster; die bestehende Testsuite verdeckt den Bug, weil
  httpx ASGITransport die Response in-process draint und dabei den verzoegerten
  Teardown vorzieht.
fix: |
  1. apps/api/src/numra_api/deps.py: get_db-Nutzung ueberall auf
     `Depends(get_db, scope="function")` umgestellt (126 Stellen). scope="function"
     beendet die yield-Dependency nach der Path-Operation-Funktion, aber VOR dem
     Senden der Response (FastAPI-Doku param_functions.py). COMMIT ist damit
     abgeschlossen, bevor die 2xx-Antwort das Prozess verlaesst.
  2. apps/api/src/numra_api/middleware/security.py: alle 5 Middlewares von
     starlette BaseHTTPMiddleware auf pure ASGI-Middleware portiert (verhalten
     identisch: Security-Header, Correlation-Id, Access-Log, Body-Limit,
     Origin-Validierung), damit der yield-Teardown nicht mehr generell hinter das
     Response-Senden rutscht. Defense-in-depth zu (1).
  3. apps/api/src/numra_api/deps.py: [CI-DIAG]-Logging in get_db, nur bei
     settings.environment == "test": Correlation-Id, txid_current() vor Commit,
     Commit-Dauer. Produktionspfad unveraendert (Fast-Path ohne Extra-SELECT).
  4. .github/workflows/ci.yml: docker-compose-e2e + system-e2e laden bei
     jedem Lauf gescrubte Diagnose-Artefakte hoch (compose-/service-Logs,
     Playwright HTML-Report + Traces). Secret-Werte (SESSION_SECRET,
     PDF_INTERNAL_TOKEN, POSTGRES_PASSWORD) werden vor dem Upload per sed durch
     ***REDACTED*** ersetzt -- gleicher Scrub-Vertrag wie der bestehende
     "Log and secret audit"-Step.
  5. apps/web/playwright.{compose,system}.config.ts: html-Reporter (open: never)
     zusaetzlich zu list, damit ein uploadbarer Failure-Report entsteht.
  6. Regressionstest apps/api/tests/integration/test_yield_commit_ordering.py.
verification: |
  - apps/api: 390/390 Tests gruen (inkl. neuer Regressionstest).
  - Regressionstest ist Rot ohne Fix (401/404 stale read), Gruen mit Fix (200).
  - ruff format --check + ruff check + mypy sauber auf geaenderten Dateien.
  - CI YAML syntaktisch validiert.
  - OFFEN (Human-Verify): >=3 gruene docker-compose-e2e + system-e2e Laeufe auf
    dem Branch als Real-Environment-Bestaetigung. Web-e2e/Playwright-Jobs lokal
    nicht ausgefuehrt (kein Full-Stack lokal aufgesetzt).
files_changed:
  - apps/api/src/numra_api/deps.py
  - apps/api/src/numra_api/middleware/security.py
  - apps/api/tests/integration/test_yield_commit_ordering.py
  - .github/workflows/ci.yml
  - apps/web/playwright.compose.config.ts
  - apps/web/playwright.system.config.ts
  - "apps/api/src/numra_api/routes/*.py (26 Dateien: Depends(get_db, scope=\"function\"))"

restunsicherheit: |
  - Der deterministische Test beweist Mechanismus + Fix, aber die genaue
    Latenz-Kette auf GitHub-Runnern (Disk-I/O, Noisy-Neighbor-Scheduling) wurde
    nie direkt gemessen. Falls nach dem Fix wider Erwarten erneut ein stale read
    auftritt, liefern die neuen [CI-DIAG]-Logs (get_db-Commit-Korrelation) + die
    Playwright-Traces die Daten zur Zweit-Analyse.
  - scope="function" ist ein relativ junges FastAPI-Feature (0.115+). Falls es in
    einem Edge-Case (z.B. StreamingResponse/SSE-Routen) unerwuenschtes Verhalten
    zeigt, ist Fix (2) allein -- pure ASGI-Middleware -- die konservativere
    Teil-Absicherung; die Kombination wurde gegen die volle Suite getestet.
