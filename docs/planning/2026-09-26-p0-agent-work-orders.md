# P0-Aufträge für Coding-Agents: Weg zur V2-Aktivierung (Connections + Workspaces)

**Stand:** 2026-09-26 · Basis `main@989c502`
**Zweck:** Die P0-Lücken aus der Lückenanalyse so schließen, dass die Stufen 1 und 2 aus `docs/ops/2026-09-26-v2-activation-connections-workspaces.md` freigegeben werden können.
**Reihenfolge und Parallelisierung:** siehe §9. Jeder Auftrag ist ein eigener PR.

---

## 0. Rahmen für jeden Auftrag (in jeden Agent-Prompt übernehmen)

```text
REPO: GoLukeEnviro/numra-v1 · Basis: aktueller main · ein Auftrag = ein Branch = ein PR.
NICHT-ZIELE (hart): keine neuen numerologischen Formeln; Astrologie, Element/Wasser,
Planes, Essence, Transits, Period-Altersgrenzen und Kompatibilitätsprozent bleiben
FEATURE_DISABLED_NO_CANON/RESERVED_UNFROZEN (ADR 006, ADR 015). Keine Flag-Defaults
ändern (config.py:133-139 bleibt False). Kein Produktions-Deploy, keine Host-Änderung.
KONVENTIONEN: Nutzertexte über den i18n-Katalog (de + en, catalog-parity.test.ts muss
grün bleiben); Fehler als Domain-Errors in services/errors.py; IDOR-Doktrin 404 statt
403; keine Secrets, keine PII in Logs.
PFLICHTCHECKS VOR DEM PR (identisch zur CI):
  uv sync --all-packages --all-groups
  uv run ruff format --check . && uv run ruff check .
  uv run mypy <betroffene Pakete>          # wie im python-typecheck-Job
  uv run pytest packages apps/api/tests -q
  uv run python3 scripts/export_openapi.py --check   # bei API-Änderung vorher ohne --check
  pnpm --filter @numra/schema generate               # bei API-Änderung, dann git diff committen
  pnpm --filter @numra/web lint && pnpm --filter @numra/web exec tsc --noEmit
  pnpm --filter @numra/web test -- --run && pnpm --filter @numra/web build
ABSCHLUSS: PR-Beschreibung mit Lücken-ID, Akzeptanzkriterien als Checkliste und
Testnachweis; docs/planning/avenyth-pwa-execution-state.md nur im letzten PR der Welle
aktualisieren.
```

---

## A0 · Infrastruktur-Vorbereitung (bereits vorbereitet, Review nötig)

| Feld | Inhalt |
|---|---|
| Lücken | L02, L03 |
| Branch | `ops/v2-activation-prep` (lokal vorbereitet) |
| Inhalt | `deploy/compose.production.yml`: Service `analysis-worker` plus die 7 `AVENYTH_*`-Flags als `${VAR:-false}` am `api`; `scripts/ops/v2-flag-probe.sh`; dieses Dokument; Runbook `docs/ops/2026-09-26-v2-activation-connections-workspaces.md`; `numra-topology.md` angepasst |
| Nachweis | `v2-flag-probe.sh https://avenyth.de/api stage0` → `RESULT: OK (matches stage0)` am 26.09.2026 |
| Verhalten | neutral: Alle Flags bleiben aus, bis `numra.env` sie setzt |

---

## A1 · Öffentliche Rechtsseiten

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | L23 · **P0** · 1 PT |
| Branch / PR-Titel | `feat/web-legal-pages` · `feat(web): public /impressum, /datenschutz, /agb` |
| Abhängigkeiten | Rechtstexte vom Operator (Platzhalter erlaubt, klar markiert) |
| Kontext | `apps/web/src/app/page.tsx:231` (Footer-Link „Datenschutz" → `/settings/privacy`, login-geschützt); `apps/web/src/app/settings/page.tsx:129`; `components/layout/app-shell.tsx`; `apps/web/public/robots.txt` (bleibt `Disallow: /` laut `NEXT_ACTION`) |

**Aufgabe**
1. Die Texte als Markdown im Repo ablegen: `apps/web/content/legal/{impressum,datenschutz,agb}.de.md` (+ `.en.md`). Jeder fehlende Operator-Wert wird als `[[OPERATOR: …]]` markiert.
2. Server-Routen `app/impressum/page.tsx`, `app/datenschutz/page.tsx`, `app/agb/page.tsx` als **Server Components** ohne `"use client"` und ohne Auth-Abhängigkeit. Das Markdown wird beim Build gelesen; es gibt keine Markdown-Dependency, ein Mini-Renderer für Überschriften, Absätze, Listen und Links genügt. Dazu `generateMetadata` mit Titel.
3. Neue Komponente `components/layout/legal-footer.tsx` mit drei Links, eingebunden in die Landing (`app/page.tsx`), Login, Register, Forgot/Reset/Verify und in die App-Shell (Desktop-Sidebar-Fuß und Mobile „More").
4. Der Landing-Link „Datenschutz" zeigt auf `/datenschutz`; `/settings/privacy` bleibt als Konto-Datenseite erhalten.
5. Auf `/register` steht vor dem Submit-Button der Satz „Mit der Registrierung gelten die AGB; Hinweise zum Datenschutz" mit Links.
6. Test `legal-pages.test.tsx`: Die drei Seiten rendern ohne Session, der Footer enthält alle drei Links.
7. CI-Wächter: Ein Test bricht, wenn eine Legal-Datei in einem Release-Build noch `[[OPERATOR:` enthält (`NODE_ENV=production` plus env `LEGAL_PLACEHOLDERS_ALLOWED` ≠ `1`).

**Akzeptanz:** Alle drei Routen liefern 200 ohne Cookie; sie sind von jeder öffentlichen Seite und aus der App höchstens zwei Klicks entfernt; `robots.txt` ist unverändert; `catalog-parity` ist grün.
**Nicht-Ziele:** keine Cookie-Banner-Logik (es gibt keine Drittanbieter-Skripte), keine CMS-Anbindung.

---

## A2 · KI-Hinweis (AI Act Art. 50 Abs. 1)

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | L12 · **P0** · 0,5–1 PT |
| Branch / PR-Titel | `feat/web-ai-disclosure` · `feat(web): AI interaction disclosure for copilot, reports and dynamics` |
| Abhängigkeiten | keine |
| Kontext | `components/copilot/personal-copilot-content.tsx`, `components/workspaces/copilot/workspace-copilot-content.tsx`, `components/reports/report-reader.tsx`, `components/workspaces/dynamics/analysis-meta-footer.tsx`, `relationship-analysis-view.tsx`, `shadow-dynamics-view.tsx`; i18n `i18n/messages/{de,en}/app.ts` (heute nur `app.dynamics.meta.model` = „Sprachmodell") |

**Aufgabe**
1. Eine gemeinsame Komponente `components/ui/ai-disclosure.tsx` (`variant: "chat" | "generated"`), ruhig und `role="note"`, in `muted`, mit Sparkles-Icon `aria-hidden`.
2. Die i18n-Keys `app.ai.disclosureChat` („Du schreibst mit einer KI. Zahlen stammen ausschließlich aus der Engine; die KI formuliert nur.") und `app.ai.disclosureGenerated` („Dieser Text wurde von einer KI formuliert und gegen die berechneten Werte geprüft.") in de und en.
3. Einbau: `chat` oberhalb beider Copilot-Eingabefelder und im Empty-State; `generated` am Kopf des Report-Readers sowie an Relationship-Analyse und Shadow Dynamics (neben der Modell-Meta).
4. Die PDF-Vorlage bekommt den Hinweis im Kopf oder Fuß (in `apps/pdf` bzw. dem HTML, das die API an den PDF-Dienst liefert; nachsehen, wo `report-reader`-äquivalentes HTML entsteht).
5. Tests: Snapshot bzw. `getByRole("note")` in allen fünf Oberflächen; ein PDF-Test prüft den String im gerenderten HTML.

**Akzeptanz:** Der Hinweis ist überall sichtbar, wo KI-Text erscheint oder eingegeben wird, und kann nicht weggeklickt werden.
**Nicht-Ziele:** maschinenlesbare Kennzeichnung nach Art. 50 Abs. 2 (Frist 02.12.2026, eigener Auftrag).

---

## A3 · Connections härten: verifizierte E-Mail und E-Mail-Bindung beim Redeem

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | neu (Sicherheit vor der Öffnung) · **P0** · 1–1,5 PT |
| Branch / PR-Titel | `fix/connections-verified-email-binding` · `fix(api): require verified email for connections; bind EMAIL invitations on redeem` |
| Abhängigkeiten | keine; SMTP-Verifizierung läuft in Produktion |
| Befund | `redeem_invitation` (`services/connection_service.py:150-190`) prüft `invitee_email` **nicht**. Jeder Account mit dem Token kann eine `EMAIL`-Einladung einlösen; nur Decline prüft die Adresse (`:139-141`). Außerdem gibt es in den Connection-Routen keine Prüfung auf `users.email_verified_at` (`models/tables.py:77`). |

**Aufgabe**
1. Einen neuen Domain-Error `EmailVerificationRequired` in `services/errors.py` anlegen (HTTP 403, Code `EMAIL_VERIFICATION_REQUIRED`). Das ist bewusst kein 404, weil es um den eigenen Account geht und damit kein IDOR-Fall ist.
2. `create_invitation` und `redeem_invitation`: Beide werfen `EmailVerificationRequired`, wenn `user.email_verified_at is None`.
3. `redeem_invitation`: Bei `method == EMAIL` muss `redeeming_user.email` (case-insensitive, getrimmt) gleich `invitation.invitee_email` sein. Sonst wird `InvitationExpiredOrInvalid` geworfen, mit derselben Antwort wie bei einem ungültigen Token (Anti-Enumeration). **Wichtig:** Die Prüfung muss *vor* `claim_invitation_by_token_hash` laufen, damit ein Fehlversuch die Einladung nicht verbraucht. Also zuerst per Hash lesen, prüfen und erst dann atomar claimen.
4. `preview_invitation`: unverändert anonymisiert. Optional das Feld `requires_email_match: bool`.
5. Web: `connections/redeem/page.tsx` und `connections/invite/page.tsx` zeigen für `EMAIL_VERIFICATION_REQUIRED` einen ruhigen Hinweis mit „Bestätigungsmail erneut senden" (vorhandener Endpunkt `request-email-verification`). Die i18n-Keys kommen in de und en.
6. Tests in `apps/api/tests/integration/test_connections.py` und `test_connections_idor.py`:
   - unverifizierter Nutzer: create → 403, redeem → 403
   - `EMAIL`-Einladung, Redeem durch eine fremde verifizierte Adresse → gleiche Antwort wie ungültiger Token, und die Einladung bleibt `PENDING`
   - Redeem durch die korrekte Adresse → 200
   - `LINK`/`CODE` sind unverändert einlösbar (verifiziert)
7. Die RC2-Journey (`apps/web/e2e-system/…`) verifiziert die E-Mail der Testkonten bereits oder wird angepasst (Token aus `EMAIL_BACKEND=logging` bzw. der Test-Fixture).
8. OpenAPI und Schema neu generieren.

**Akzeptanz:** Alle Tests grün; eine fehlgeschlagene E-Mail-Bindung verbraucht keine Einladung; die Anti-Enumeration bleibt erhalten.
**Nicht-Ziele:** E-Mail-Versand der Einladung (L10, P1) und Eingangsliste (L11, P1).

---

## A4 · Entitlements serverseitig erzwingen und Beta-Whitelist

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | neu (Rollout-Steuerung) · **P0 für einen Whitelist-Rollout**, sonst P1 · 2–3 PT |
| Branch / PR-Titel | `feat/api-entitlement-enforcement` · `feat(api): enforce entitlements on V2 routers; v2_beta set + CLI assignment` |
| Abhängigkeiten | keine |
| Befund | `api-contract.md` §Entitlements: „Server-authoritative". Tatsächlich prüft kein Service `connections`, `relationship_workspaces`, `max_connections` oder `max_workspaces`; `beta_default` schaltet alles frei (Migration `bd410b4e2a76`). Flags wirken deshalb nur global. |

**Aufgabe**
1. In `deps.py` eine Dependency `require_entitlement(key: Literal[...])` anlegen, die `repositories/entitlements.py::get_effective_entitlement_set_for_user` nutzt. Fehlt die Berechtigung, gibt es `403 ENTITLEMENT_REQUIRED` mit `details.entitlement`.
2. Einbau **pro Route** (nicht auf Router-Ebene, weil die Flag-Dependency auf Router-Ebene zuerst greifen soll und die Flag-Probe dadurch `503` vor `401` behält):
   - Connections: Einladung erstellen und einlösen → `connections`
   - Relationship-Workspace-Routen → `relationship_workspaces`
   - Relationship-Analyse und Shadow Dynamics → `advanced_relationship_analysis`
   - Personal-Workspace-Routen → `personal_workspace`
3. Limits: `max_connections` beim Erstellen und Einlösen (aktive Connections plus offene Einladungen des Einladenden), `max_workspaces` beim Redeem. `NULL` bedeutet unbegrenzt. Fehler: `409 ENTITLEMENT_LIMIT_REACHED`.
4. Alembic-Migration: ein neues Set `v2_beta` (alles `true`, Limits `NULL`) anlegen und `beta_default` **nicht** ändern. Das Umschalten des Defaults auf „V2 gesperrt" ist eine spätere Operator-Entscheidung per Datenmigration (Kommentar im Runbook).
5. CLI `cli.py`: `numra entitlements assign --email <e> --set v2_beta`, `… revoke --email <e>` und `… list`. Das Muster kommt von `admin promote`. Jede Zuweisung schreibt ein `AdminAuditEvent` ohne PII-Details.
6. Web: `PhaseDisabledState` bzw. `states.tsx` kennt `ENTITLEMENT_REQUIRED` und `ENTITLEMENT_LIMIT_REACHED` als ruhige, erwartete Zustände mit i18n-Text.
7. Tests: Matrix aus Flag an/aus × Entitlement an/aus × Route; Limit-Tests; ein Test, dass die anonyme Probe weiterhin `503` bzw. `401` liefert (Reihenfolge Flag → Auth → Entitlement).

**Akzeptanz:** Mit `beta_default` bleibt das Verhalten unverändert (alles frei). Mit einem gesperrten Set sind genau die Routen gesperrt. Die CLI weist per E-Mail zu und nimmt die Zuweisung wieder zurück.
**Nicht-Ziele:** Billing, Admin-UI (später).

---

## A5 · Error Boundaries und Client-Timeout

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | L22 · **P0 vor Stufe 1** · 1,5–2 PT |
| Branch / PR-Titel | `feat/web-error-boundaries-timeouts` · `feat(web): route error boundaries, component boundary, request timeouts` |
| Kontext | kein `error.tsx` bzw. `ErrorBoundary` in `apps/web/src`; `api/client.ts` `request<T>()` ohne `AbortSignal` (0 Treffer); `ErrorState` in `components/ui/states.tsx` |

**Aufgabe**
1. `app/error.tsx` und `app/global-error.tsx` anlegen; beide nutzen `ErrorState` mit „Neu laden" (`reset()`) und „Zur Übersicht".
2. `components/ui/error-boundary.tsx` als eigene Klasse ohne neue Dependency, mit Fallback `ErrorState` und optionalem `onError`. Wrapper um: `workspaces/dynamics/analysis-section.tsx`, beide Copilot-Komponenten, `people/evidence/evidence-layer-content.tsx`, `workspace/checkins-content.tsx`, `reports/report-reader.tsx`.
3. `api/client.ts`: `request<T>(path, init & { timeoutMs?: number; signal?: AbortSignal })`. Default 30 000 ms über `AbortSignal.timeout`, kombinierbar mit einem externen Signal (`AbortSignal.any`, mit Fallback für ältere Browser). Ein Timeout wird zu `NetworkError` mit `code="TIMEOUT"`.
4. Lange Pfade: Copilot-POST bekommt `timeoutMs: 150_000`, Analyse- und Report-Launch 60 000. Im Copilot gibt es während des Wartens einen **„Abbrechen"**-Button.
5. Tests: ein Kind, das wirft, erzeugt eine `role="alert"`-Fehlerkarte und die Navigation bleibt nutzbar; ein hängender Fetch-Mock führt zu `TIMEOUT` → `ErrorState` mit Retry; Abbrechen setzt den Zustand zurück.

**Akzeptanz:** Kein Weiß-Screen bei geworfenem Render-Fehler; jeder Request endet spätestens nach seinem Timeout.

---

## A6 · Healthcheck: hängende Jobs erkennen

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | Grenze aus `numra-monitoring.md` §Bewusste Grenzen · **P0 vor Stufe 2** · 0,5 PT |
| Branch / PR-Titel | `ops/healthcheck-stale-queued-jobs` · `ops(healthcheck): alarm on stale QUEUED report/analysis jobs` |
| Kontext | `scripts/ops/numra-healthcheck.sh` (`probe_jobs`, Zeilen 68–95); `docs/ops/numra-monitoring.md` |

**Aufgabe**
1. In `probe_jobs` eine zweite Abfrage ergänzen: die Anzahl von `report_jobs` und `analysis_jobs` mit `status='QUEUED' AND created_at < now() - interval '${STALE_QUEUED_MINUTES:-15} minutes'`.
2. Ist die Anzahl größer als 0, gibt es `failures+=("$name:${n}_stale_queued_job(s)")`, und das Statusfeld `${name}_stale_queued_jobs` wird ergänzt.
3. `STALE_QUEUED_MINUTES` ist über `/etc/numra/healthcheck.env` konfigurierbar; die Doku wird angepasst.
4. Einen shellcheck-sauberen Testlauf mit einem Mock-`docker`-Skript im PATH ergänzen (Bats oder ein schlichtes Bash-Testskript unter `scripts/ops/tests/`).

**Akzeptanz:** Ein stehender `analysis-worker` löst binnen `STALE_QUEUED_MINUTES + 5` einen Alarm aus.

---

## A7 · LLM-Call-Log und Token-Nutzung

| Feld | Inhalt |
|---|---|
| Lücke / Prio / Aufwand | L07 · **P0 vor Dynamics in Produktion** (sonst Kosten unsichtbar), zwingend vor Copilot · 2–3 PT |
| Branch / PR-Titel | `feat/llm-generation-log` · `feat(llm): persist LLMGeneration for reports, analyses and copilot incl. token usage` |
| Befund | `LLMGeneration` (`models/tables.py:341-363`) wird nie geschrieben; `GenerationResult` (`llm/types.py:118-125`) hat weder Usage noch Latenz. Ollama liefert `prompt_eval_count`/`eval_count` in der Response. |

**Aufgabe**
1. `packages/engine-interpretation/.../llm/types.py`: `GenerationResult` um `usage: TokenUsage | None` (`prompt_tokens`, `completion_tokens`) und `latency_ms: int | None` erweitern. Das ist abwärtskompatibel mit Default `None`.
2. `ollama_provider.py` füllt beides; `mock_provider.py` liefert deterministische Werte; `disabled_provider.py` bleibt unverändert.
3. Alembic-Migration auf `llm_generations`: nullable FKs `analysis_job_id` (→ `analysis_jobs`, `ON DELETE CASCADE`) und `chat_message_id` (→ `chat_messages`, `ON DELETE SET NULL`), dazu `purpose String(40)` (`REPORT_SECTION | RELATIONSHIP_ANALYSIS | SHADOW_DYNAMICS | CHECKIN_ANALYSIS | COPILOT_TURN`) und einen Index `(created_at)`. Die Account-Löschkaskade (`repositories/account.py`) muss weiterhin vollständig löschen; der Test dazu wird erweitert.
4. Ein Repository `repositories/llm_generations.py::record_generation(...)` schreibt **nur Metadaten** (kein Prompt, keine Antwort; `prompt_hash` = SHA-256 des gerenderten Prompts).
5. Aufrufstellen: Report-Pipeline (je Sektion), `relationship_analysis_service.py` (Relationship und Shadow), Check-in-Analyse, `copilot_service.py` (je Turn, inkl. Corrective Retry als eigene Zeile). Fehlerpfade werden mit `status="FAILED"` und `error_code` geloggt.
6. Eine CLI `numra llm usage --since 24h` aggregiert Aufrufe, Tokens und Fehler je `purpose` und Modell. Optional ein Kostenfaktor pro Modell über `NUMRA_LLM_COST_PER_1K_{PROMPT,COMPLETION}_<MODEL>`.
7. Tests: je Aufrufstelle genau eine Zeile pro LLM-Call (mit Mock); kein Prompt- oder Antworttext in der Zeile; die Kaskade bei Account-Löschung funktioniert.

**Akzeptanz:** Nach einer Relationship-Analyse existiert eine `LLMGeneration`-Zeile mit Tokens und Latenz; `numra llm usage` zeigt die Summe.
**Nicht-Ziele:** Prometheus-Export (L21, P1), Budget-Abschaltung (später).

---

## 9. Reihenfolge, Parallelisierung, Freigaben

```text
Welle 1 (parallel, unabhängig):  A0-Review/Merge · A1 · A2 · A3 · A5 · A6
Welle 2:                          A7 (berührt Pipelines; nach A2, um Konflikte in Views zu vermeiden)
Optional parallel:                A4 (nur nötig, wenn Whitelist-Rollout gewünscht)

Freigabe Stufe 1 (Master)       ← A0 deployt, A1, A5 live            (Runbook §6)
Freigabe Stufe 2 (Conn + WS)    ← zusätzlich A2, A3, A6 live; A7 live ODER
                                   Kostenrisiko bewusst akzeptiert; LLM-Entscheidung (G6) (Runbook §7)
```

| Auftrag | Aufwand | kritischer Pfad |
|---|---|---|
| A0 | Review 0,25 PT | ja |
| A1 | 1 PT (+ Texte) | ja (Stufe 1) |
| A2 | 0,5–1 PT | ja (Stufe 2) |
| A3 | 1–1,5 PT | ja (Stufe 2) |
| A4 | 2–3 PT | nur bei Whitelist |
| A5 | 1,5–2 PT | ja (Stufe 1) |
| A6 | 0,5 PT | ja (Stufe 2) |
| A7 | 2–3 PT | ja (Stufe 2, sonst Risikoakzeptanz) |
| **Summe** | **7–10 PT** (ohne A4), **9–13 PT** mit A4 | |

## 10. Risiken für diese Welle

- **Merge-Konflikte** in `i18n/messages/*/app.ts` (A1, A2, A3, A4, A5 fügen Keys hinzu). Gegenmaßnahme: Keys jeweils am Ende des jeweiligen Namensraums anfügen und nach jedem Merge rebasen.
- **OpenAPI-Drift:** A3, A4 und A7 ändern die API bzw. Schemas. Gegenmaßnahme: Diese PRs nacheinander mergen und Schema neu generieren.
- **RC2-Journey:** A3 (verifizierte E-Mail) kann die Zwei-Account-Journey brechen. Gegenmaßnahme: Die Journey-Anpassung gehört in denselben PR.
- **PR #202 (CI-Split)** ist noch Draft. Ändern sich die Required Checks mitten in der Welle, blockieren die Merges. Gegenmaßnahme: vor Welle 1 entscheiden (rebasen und mergen oder schließen).
- **Operator-Gates:** Deploy, `numra.env` und Host-Compose sind root-only; kein Agent darf sie „nebenbei" ändern.
