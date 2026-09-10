# REALITY_CHECK_2 — Abschlussbericht

**Segment B (PR-WEB-01 – PR-WEB-04)** · Ausgangs-`main`: `f947976`
· Abschluss-`main`: `8175413` · Datum: 2026-09-10

REALITY_CHECK_2 ist der harte Human-/UX-Gate nach Segment B. Dieser
Bericht schließt die im ersten Anlauf offenen Punkte ab: fehlende echte
Mobile-Journey, falsche Einladungslink-Origin, ungeklärte CI-Instabilität.
WEB-05 war bis zu diesem Bericht pausiert.

## Ergebnis je Kategorie

| Kategorie | Status | Beleg |
|---|---|---|
| **Link-Fix (Einladung / Verify / Reset)** | **PASS** | PR #43 (`6d0c664`), Post-Merge-`main`-CI Run `34450795482` grün. RC2-Journey öffnet den **tatsächlich erzeugten** `http://localhost:3100/connections/redeem?token=…` in Kontext B ohne Umschreiben. |
| **Backend-/Consent-Nachweis** | **PASS** | Contract bestätigt (`specs/v2/consent-spec.md`, Decision #7: 3 Default-Scopes **beidseitig**). Directional Grant/Revoke mit sofortiger Wirkung, Re-Grant nach Revoke (PR #45, `40fea15`), Dissolve-Lock. RC2-Playwright + `pytest -k consent` (18 passed). |
| **Desktop-Journey (gemessener Viewport)** | **PASS** | `desktop-1440x900`, `window.innerWidth/innerHeight == 1440×900` via Playwright assertiert (kein `resize_window`-Tool). Vollständige Journey grün. |
| **Mobile-Journey (gemessener Viewport)** | **PASS** | `mobile-390x844`, `window.innerWidth/innerHeight == 390×844` via Playwright assertiert. Vollständige Journey grün. Der zuvor blockierende Chrome-Extension-`resize_window` wird nicht mehr verwendet. |
| **CI-Ursache** | **BEWIESEN UND BEHOBEN** | PR #44 (`1f70b65`). Details: `docs/planning/ci-flake-root-cause.md`. |
| **Required Checks + Post-Merge-CI** | **PASS** | Siehe Tabelle unten. |

## Fixes in diesem Abschluss

| PR | Inhalt | Merge-Commit | PR-CI | Post-Merge-`main`-CI |
|---|---|---|---|---|
| **#43** | `web_app_base_url`-Default `5173`→`3000`; `Settings.build_web_app_url()` als einzige URL-Bau-Stelle (Trailing-Slash-tolerant, nie aus Host/Forwarded-Headern); `WEB_APP_BASE_URL` in `.env.example` + Compose. Regressionstests Invite/Verify/Reset. | `6d0c664` | 12/12 grün (1. Lauf) | Run `34450795482` — grün |
| **#44** | DB-Commit vor Response (`Depends(get_db, scope="function")` an 126 Stellen + 5 Middlewares auf pure ASGI). Root Cause der CI-Instabilität **und** latenter Prod-Korrektheitsfehler. Regressionstest + gescrubte CI-Failure-Artefakte + `[CI-DIAG]`-Logging (nur `ENVIRONMENT=test`). | `1f70b65` | 12/12 grün (1. Lauf) | Run `34453209752` — grün |
| **#45** | Consent-Re-Grant nach Revoke schlug mit `500` fehl (`UniqueViolationError`; `grant_consent` reaktiviert die revozierte Zeile jetzt + `ConsentEvent(GRANTED)`; `IntegrityError`→`409 CONSENT_GRANT_CONFLICT`). Im RC2-Lauf gefunden. 4 Regressionstests. | `40fea15` | 12/12 grün (1. Lauf) | Run `34454947452` — grün |
| **#46** | Echte Zwei-Konten-RC2-Playwright-Suite (Desktop + Mobile), eigene Config/Compose-Overlay/Wrapper, `workflow_dispatch`-Workflow. Rein additiv, kein Required Check. | `8175413` | 12/12 grün (1. Lauf) | Run auf `8175413` |

Alle drei gemergten Fixes: `docker-compose-e2e`, `system-e2e` und
`playwright` grün **im ersten Lauf** — die Signatur „erster Lauf rot,
Re-Run grün" ist seit dem Fix nicht wieder aufgetreten.

## RC2-Journey — was verifiziert wurde

Suite: `apps/web/e2e-system/rc2-two-account-journey.spec.ts` gegen den
isolierten `docker compose -p numra-rc2`-Stack. Zwei unabhängige
`browser.newContext()` (A = Einladender, B = Einlösender), **kein**
`page.route()`. Einzige API-Schritte (im Code markiert): die zwei
Registrierungen (kein Self-Signup-UI) und das Same-Origin-`PATCH`/`GET`-Paar
zur 409-Verifikation nach Dissolve.

Lauf: `bash scripts/rc2-e2e.sh up && npx playwright test
--config=playwright.rc2.config.ts` → **2 passed** (Desktop 18,8 s /
Mobile 19,7 s), Stack danach sauber abgebaut (nur `numra-rc2`-Ressourcen;
fremde Container/Volumes/`.env` unangetastet).

Abgedeckt (jeder Schritt echte UI-Aktion, sofern nicht markiert):

* Registrierung + SELF-Profil + Berechnung für A und B
* gemessener Viewport vor jeder Fachprüfung
* A erstellt LINK-Einladung, echter `redeem_url` aus dem readonly-Feld
* B öffnet den **unveränderten** `redeem_url` in Kontext B → Preview →
  Annehmen → Relationship Workspace
* Default-Consent: exakt 3 Scopes beidseitig `aria-checked=true`, 5
  erweiterte `false`; eingehend „Freigegeben" — auf A- und B-Seite
* Dual-Profile **vollständig** (echte Kernzahlen beidseitig), A- und B-Sicht
* A widerruft `CORE_NUMEROLOGY` (A→B), **B hat die Overview offen** →
  `reload` → degradiert (`self_person`/`core_numbers` leer, Hinweistext),
  **kein** Fehlerzustand
* B nächster geschützter Abruf: eingehend „Nicht freigegeben"
* **Gegenrichtung unberührt**: B→A `CORE_NUMEROLOGY` weiter aktiv (B-Switch,
  A-eingehend „Freigegeben", A-Overview zeigt B-Zahlen)
* **Re-Grant** von `CORE_NUMEROLOGY` (A→B) über den Toggle → B bekommt
  beim nächsten Abruf wieder Zugriff (deckt PR #45 über die UI ab)
* unabhängiges Grant/Revoke `PRIVATE_JOURNAL` (B→A) und `PRIVATE_TASKS`
  (A→B), strikt per Richtung
* Relationship-Type PARTNER, expliziter Speichern-Button, Persistenz nach
  Reload + Badge in der `/workspaces`-Liste
* Dissolve über die UI → Read-only-Zustand sichtbar; `PATCH` → **409
  `WORKSPACE_DISSOLVED`**, `GET` → **200**
* Off-Origin-Guard: der Browser trifft ausschließlich same-origin `/api/*`

Visuell Desktop/Mobile (mit Assertions, nicht nur Screenshots): keine
Überläufe, Bedienelemente im Viewport (`toBeInViewport`), Read-only-/
degradierte Zustände lesbar.

## Nicht als Produktfehler gewertet

* **`/people/new` erzeugt nur `MANAGED_OTHER`** — das für das Dual-Profile
  nötige SELF-Profil entsteht im `/onboarding`-Flow; die Journey nutzt
  diesen als realen UI-Pfad.
* **Anzeigename der Gegenseite fällt bei entzogenem `CORE_NUMEROLOGY` auf
  die E-Mail zurück** und bricht auf Mobile mehrzeilig um — Artefakt der
  synthetischen Test-E-Mail-Adressen, bei echten Namen unkritisch.
* **`.invalid`-Adressen werden abgelehnt** — laut Auftraggeber
  ausdrücklich kein Produktfehler.

## Sicherheitsvorfall (Autofill) — Stand

Im vorherigen Segment: Chrome hat zweimal echte gespeicherte Zugangsdaten
in ein Login-Feld eingesetzt. Übertragungsweg forensisch geklärt — kein
Logging im App-Stack, der Passwort-Vergleich wurde technisch nie
ausgeführt (User-Lookup scheiterte zuerst). Restunsicherheit ausschließlich
auf Betriebssystem-Ebene (Netzwerk-Capture, Autofill-Cache), nicht
einsehbar.

**Stehende Empfehlung:** Passwort ändern — nicht wegen eines
nachgewiesenen Lecks, sondern wegen der nicht ausräumbaren OS-Level-
Restunsicherheit. Alle RC2-Arbeiten liefen ausschließlich mit synthetischen
Konten in isolierten Browser-Kontexten ohne persönliches Chrome-Profil.

## Empfehlung für WEB-05

**STARTBEREIT.**

Begründung:
* Alle vereinbarten RC2-Kriterien erfüllt und belegt (Tabelle oben).
* Drei blockierende Befunde behoben und mit grüner Post-Merge-`main`-CI
  bestätigt: falsche Link-Origin (#43), latenter Stale-Read-/CI-Bug (#44),
  Consent-Re-Grant-`500` (#45).
* Reale Zwei-Konten-UI-Journey über Desktop **und** Mobile grün, Viewport
  gemessen.
* Keine offenen Produktfehler; die drei nicht-blockierenden Notizen oben
  sind dokumentiert.

WEB-05 selbst ist nicht Teil dieses Abschlusses.
