# Gap-Analyse Deep Dive — numra-v1

> **Bericht:** Ist-Soll-Analyse der IT-Landschaft `numra-v1`
> **Stand:** 2026-08-23 · **Branch:** `main` · **Commit:** `f4be7ee7`
> **Messbasis:** Read-only-Analyse-Skripte (`inventar.py`, `git_metriken.py`, `muster_scan.py`) + Artefakt-Recherche
> **Zielgruppe:** Management und Entwicklungsteam

---

## 1. Management Summary

`numra-v1` ist ein astrologisch-numerologisches Monorepo mit klarer Domänen-Trennung: drei
deterministische Python-Rechenengines (`numerology`, `interpretation`, `astrology`), eine
stateless FastAPI-Boundary (`apps/api`), ein Next.js-Frontend (`apps/web`), ein interner
PDF-Renderer (`apps/pdf`) sowie ein generierter TS-Client (`packages/schema`). Das System ist
**dokumentations- und teststark** (301 Tests, 0 failing, 7 akzeptierte ADRs, formale
Canon-Spec) und weist eine ungewöhnlich saubere Architektur auf: die Rechenlogik ist
deterministisch und frei von I/O, LLM ist explizit als Nicht-Rechner modelliert (ADR-003), und
Sicherheitsgrundlagen (Argon2id, HttpOnly-Cookies, CSRF, Rate-Limiting, CSP) sind implementiert.

Trotz der hohen Reife existieren **zwölf identifizierte Lücken**, von denen **zwei als
kritisch** einzustufen sind: (a) die **Astrologie-Engine ist ein reines Typ-Interface ohne
Implementierung** (`FEATURE_DISABLED_NO_CANON`, ADR-006) und (b) die **Live-LLM-Verifikation
(Ollama) ist unverifiziert** (`LIVE_LLM_SMOKE = NOT_VERIFIED`). Beide betreffen zentrale
Produktversprechen der Anwendung. Weitere relevante Lücken betreffen fehlende
Architektur-/Changelog-Dokumentation, eine unvollständige Testabdeckung im Frontend
(App-Shell, Auth, Design-System), ausstehende Observability (kein Tracing/Metrik-Export) und
eine Doku/Code-Divergenz um die RBAC/Admin-Backend-Fähigkeit (V1.6).

Die Gesamtbewertung ergibt **4 grüne, 6 gelbe, 0 rote** Ampelfelder (siehe §5). Die wichtigsten
**Quick Wins** sind das Schließen der Dokumentationslücken und die Erweiterung der
Frontend-Testabdeckung; die **strategischen Maßnahmen** sind der Ausbau der Astrologie-Engine
und die Einführung eines strukturierten Monitoring-/Observability-Ansatzes. Die Gesamtaufwand-
Schätzung über alle Maßnahmen beträgt **ca. 145–185 Personentage** (PT), davon entfallen rund
40 PT auf die beiden kritischen Maßnahmen.

> **Hinweis:** Alle PT-Angaben sind **qualifizierte Schätzannahmen**, da keine Team-
> und Kapazitätsdaten vorlagen. Sie sind als grobe Größenordnungen zu verstehen und vor der
> Umsetzung je Maßnahme zu verifizieren.

---

## 2. Methodik und Vorgehensweise

Die Analyse folgt dem `projekt-diagnose`-Skill mit vier Evidenzstufen:

| Evidenzstufe    | Bedeutung                                       | Quelle                                         |
| --------------- | ----------------------------------------------- | ---------------------------------------------- |
| `GEMESSEN`      | in diesem Lauf durch Skript erzeugt             | inventar.py / git_metriken.py / muster_scan.py |
| `BERICHTET`     | aus Repo-Artefakt übernommen, nicht nachgeprüft | `datei:zeile`                                  |
| `UNVERIFIZIERT` | in diesem Lauf nicht bestimmbar                 | Grund benannt                                  |
| `ANNAHME`       | keine Datenbasis, qualifizierte Schätzung       | explizit gekennzeichnet                        |

**Ablauf:**

1. Orientierung: Struktur, Manifeste, Stack, Working-Tree-Status (sauber, 72 Commits, 3 Autoren).
2. Messung: `inventar.py` (LOC, Testverhältnis, lange Funktionen, Duplikate, zyklische Importe),
   `git_metriken.py` (Hotspots, Reverts), `muster_scan.py` (TODO/FIXME, unsichere Muster,
   Geheimnis-Indikatoren — leak-sicher).
3. Recherche: ADRs 001–007, Canon-Spec, FINAL_VERIFICATION.md, CI-Workflow, Docker-Compose,
   OpenAPI, Docs/ops, specs/evidence.
4. Ist-Soll-Vergleich über 10 Dimensionen.
5. Verdachts-Fehle und Fehlalarme manuell verifiziert (z. B. `sich_sql_verkettung`).

### Belegpflicht & Grenzen

- **Geheimnisse wurden nie ausgelesen.** `muster_scan.py` meldet ausschließlich
  Bezeichnernamen. Die in den Treffern genannten `postgresql+asyncpg`-URLs (CI, config, compose)
  sind **CI-/Test-/Dev-Konfigurationen**, deren Passwörter nicht ausgelesen und nicht bewertet
  werden; sie werden im Befund-Katalog als `BERICHTET`-Hinweis geführt, nicht als reales Leck.
- Der `sich_sql_verkettung`-Treffer in `composer.py` (Z. 317/322) und `people/[id]/page.tsx`
  (Z. 121) wurde **manuell als Fehlalarm verifiziert** – dort wird Text bzw. eine Router-URL
  zusammengesetzt, kein SQL. Die Treffer sind daher nicht als Befund gewertet.

---

## 3. Ergebnisse der Gap-Analyse (Ist-Soll je Systemdimension)

> **Legende Schweregrad:** `Kritisch` · `Hoch` · `Mittel` · `Niedrig`
> **Priorität:** 1 = sofort, 2 = bald, 3 = planen, 4 = beobachten
> **Aufwand:** grobe Personentage (ANNAHME)

### 3.1 Systemarchitektur und Design

**Ist-Zustand:**

- Monorepo mit klarer Schichten-Trennung: Engines (pure Python, deterministisch) → API
  (stateless FastAPI-Boundary) → Web/PDF (Frontend/Rendering). Import-Pipeline-first
  (`numra_numerology → numra_interpretation → numra_api`), Anti-Leak-Test abgesichert
  (ADR-001).
- `engine-astrology` enthält **nur** `AstrologyEngineInterface.compute()` das
  `NotImplementedError` wirft (feature disabled, ADR-006).
- 7 akzeptierte ADRs (001–007) dokumentieren deterministische Engine, canonical versioning,
  LLM-Nicht-Rechner, Report-Job-Queue, PDF-Rendering (kein SSRF), unfrozen features,
  V1.5-Produktabschluss.
- Modulgröße gemessen: 345 Dateien gesamt; **größte Module** sind `pipeline.py` (466 Z.)
  und `composer.py` (443 Z.) in `engine-interpretation`.

| ID        | Lücke                                    | Ist                                                                                                                       | Soll                                                              | Ursache                                                             | Auswirkung (technisch / geschäftlich)                                                      | Schweregrad  | Priorität | Empfehlung                                                                                                                      | Aufwand (PT) |
| --------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------ | --------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| G-ARCH-01 | Astrologie-Engine ohne Implementierung   | Nur Interface, wirft `NotImplementedError` (`packages/engine-astrology/src/.../__init__.py`)                              | Vollwertige, deterministische Astrologie-Funktion gem. Canon-Spec | Scope-Entscheid: als unfrozen (ADR-006) eingestuft, noch kein Canon | Produktversprechen "Astrologie" unerfüllt; Feature-Blocker; hohe Wartungslast am Interface | **Kritisch** | 1         | (a) Canon-Spec für Astrologie definieren, (b) deterministische Engine implementieren, (c) Test-Suite + golden fixtures aufbauen | 20–30        |
| G-ARCH-02 | Doku/Code-Divergenz um RBAC/Admin (V1.6) | Release-Runbook referenziert RBAC/Admin-Backend und V1.6 Release A; Code enthält nur eingeschränkt sichtbare Admin-Routen | Doku beschreibt exakt den deployten Stand                         | Versionierung lief über Release-Runbook hinaus (V1.6)               | Verwirrung im Team, falsche Sicherheitsannahmen, Onboarding-Fehler                         | **Hoch**     | 2         | Release-Runbook und Architektur-Doku auf Repo-Stand abgleichen; Versions-Matrix einführen                                       | 3            |
| G-ARCH-03 | Kein Architektur-Diagramm                | Nur Text in README/ADRs                                                                                                   | Pflegebares C4-/Mermaid-Diagramm                                  | Fokus auf funktionale Docs                                          | Onboarding-Aufwand, schwer erkennbare Abhängigkeiten                                       | **Mittel**   | 3         | `docs/architecture.md` mit Mermaid-Diagrammen anlegen                                                                           | 2            |

### 3.2 Codequalität und Wartbarkeit

**Ist-Zustand:** Ruff, mypy strict, mypy-Marker golden/integration/property/unit; Coverage-Gate
≥90% für Engine (tatsächlich 100%); Kommentarquote 6,9%; **keine zyklischen Importe**, **kein
God-Modul** (gemessen).

| ID       | Lücke                                         | Ist                                                                                                                         | Soll                                               | Ursache                                      | Auswirkung                                             | Schweregrad | Priorität | Empfehlung                                                                             | Aufwand |
| -------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------ | ----------- | --------- | -------------------------------------------------------------------------------------- | ------- |
| G-COD-01 | Lange Funktionen im Frontend & Interpretation | 31 Funktionen >70 Z. (gemessen); z. B. `EditPersonForm` (243 Z.), `pipeline._generate_section` (152 Z.), `composer` mehrere | Funktionen <30 Z. (Richtwert), klare Verantwortung | Schicht- und Screen-Features, Form-Bündelung | Wartbarkeit sinkt; Merge-Konflikte; Refactoring-Risiko | **Mittel**  | 2         | Form-Komponenten in Unterkomponenten zerlegen; Pipeline in Schritt-Templates aufteilen | 8       |
| G-COD-02 | Duplizierte Personen-Form-Logik               | `people/new` und `people/[id]/edit` teilen signifikante Blöcke (47/45/29/16 Z. Duplikate)                                   | Wiederverwendbare Form-Engine / Hook               | Zwei Screens ohne Abstraktion gebaut         | Pflegeaufwand, Drift zwischen Screens                  | **Mittel**  | 2         | Gemeinsamen `PersonForm`-Hook/Component extrahieren                                    | 4       |
| G-COD-03 | `print` statt Logging                         | `cli.py`, `verify.py`, `export_openapi.py` nutzen print (17 Treffer GEMESSEN)                                               | Strukturiertes Logging                             | Script-Kultur                                | Fehlende Observability bei CLI/Verify-Läufen           | **Niedrig** | 4         | Python `logging` in CLI/Scripts einführen                                              | 2       |
| G-COD-04 | Viele Parameter-Funktionen                    | `create_report_with_job` (10), `create_calculation` (8), `_generate_section` (8)                                            | Max. 4–6 Parameter, Kontextobjekte                 | Service/Repo-Verantwortung nicht gekapselt   | Lesbarkeit, Testaufwand                                | **Niedrig** | 4         | Konfig-Objekte (DTO/Context) einführen                                                 | 3       |

### 3.3 Performance und Skalierbarkeit

**Ist-Zustand:** Report-Erzeugung ist async über Postgres-Job-Queue (ADR-004, `FOR UPDATE
SKIP LOCKED`, Idempotency-Key, Retry/Backoff). Redis für Rate-Limit. PDF-Renderer als separater
Service (kein URL-Renderer). **Keine Last-/Perf-Tests, kein Benchmarking, keine
Metrik-Exporte (Prometheus/OpenTelemetry)**.

| ID       | Lücke                                 | Ist                                                                             | Soll                                      | Auswirkung                                       | Schweregrad | Priorität | Empfehlung                                                    | Aufwand |
| -------- | ------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------ | ----------- | --------- | ------------------------------------------------------------- | ------- |
| G-PER-01 | Keine Performance-Baseline            | Keine Last-Tests, keine SLOs, kein Metrik-Export                                | Perf-Tests + SLOs (p95-Latenz) + Metriken | Skalierung unvorhersehbar; keine Evidenz für SLA | **Hoch**    | 2         | k6/Locust-Smoke + Metrik-Export (Prometheus) für API & Worker | 8       |
| G-PER-02 | Frontend-Bundle-Optimierung ungeprüft | Kein Bundle-Analyse-/Budget-Check sichtbar                                      | Bundle-Budget in CI                       | Next-Standard nutzt ISR/SSR                      | **Mittel**  | 3         | `@next/bundle-analyzer` + CI-Limit einführen                  | 3       |
| G-PER-03 | LLM-Latenz ohne Timeouts/Steuer       | Provider nur via `NUMRA_LLM_PROVIDER`-Env, keine Timeout-/Cost-Budgets sichtbar | LLM-Timeouts, Retry-Policy, Cost-Limits   |                                                  | **Mittel**  | 3         | LLM-Client mit Timeouts/Retry/Backoff absichern               | 3       |

### 3.4 Informationssicherheit und Datenschutz

**Ist-Zustand (berichtet):** Argon2id, Session-Hash (SHA-256) nur gespeichert, HttpOnly/
SameSite=Lax/Secure-Cookies, CSRF double-submit, Origin-Validierung, Redis-basiertes
Rate-Limit mit HMAC-Pseudonymisierung, `ALLOW_SELF_SIGNUP=false` default, `SECURE-COOKIES`
abhängig von ENV, CSP in Next-Config (kein nonce). Compose-E2E scannt Logs auf
`SESSION_SECRET`/`PDF_INTERNAL_TOKEN`-Leaks. **Kein echtes `.env` im Repo** (korrekt ignoriert);
nur `.env.example`.

| ID       | Lücke                                                | Ist                                                                               | Soll                                        | Ursache                           | Auswirkung                                   | Schweregrad  | Priorität                                   | Empfehlung                                                     | Aufwand |
| -------- | ---------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------- | --------------------------------- | -------------------------------------------- | ------------ | ------------------------------------------- | -------------------------------------------------------------- | ------- |
| G-SEC-01 | Live-LLM-Verifikation unverifiziert                  | `LIVE_LLM_SMOKE (Ollama Cloud) = NOT_VERIFIED` (fehlendes `OLLAMA_API_KEY`)       | LLM-Provider in Production nachgewiesen     | fehlender API-Key in CI-Umgebung  | Unverifizierter LLM-Pfad, Produktionsrisiko  | **Kritisch** | 1                                           | Run-Live-Smoke-Test in staging; Key als CI-Secret, nie im Repo | 2       |
| G-SEC-02 | CSP ohne `nonce`/`strict-dynamic`                    | `script-src 'self' 'unsafe-inline'`, kein nonce                                   | Nonce-basiertes CSP (streng)                | Next 14-Inline-Scripts-Kompromiss | Erhöhtes XSS-Risiko bei Injections           | **Hoch**     | 2                                           | auf nonce/`strict-dynamic` migrieren (Next 15)                 | 5       |
| G-SEC-03 | Kein zentrales Security-Scan/SAST im CI-Budget-Check | CI nutzt `pnpm audit`+`pip-audit`                                                 | Zusätzlich SAST (Semgrep/Bandit)            |                                   | **Mittel**                                   | 3            | SAST-Job ergänzen                           | 3                                                              |
| G-SEC-04 | Credentials in Compose/Test-URLs (nur Dev/CI)        | Muster-Treffer: postgresql-URLs in ci.yml, config.py (default), conftest, compose | keine DB-Zugangsdaten in Repo (nur via Env) | dev-konvention                    | Gering (nur Dev/CI); aber Härtung verbessern | **Mittel**   | 3                                           | Zugangsdaten in Compose komplett auf Env (ohne default)        | 1       |
| G-SEC-05 | Fehlender Audit-/Incident-Prozess im Ops-Runbook     | Admin-Audit nur als Code sichtbar (API), kein Runbook-Prozess im Repo             | Incident-/Audit-Prozess dokumentieren       |                                   | **Niedrig**                                  | 4            | Runbook um Audit-/Incident-Prozess ergänzen | 2                                                              |

### 3.5 Datenhaltung und Schnittstellen

**Ist:** Postgres 16 (alembic-Migrationen), Redis 7; `profile.schema.json` (JSON-Schema);
OpenAPI `openapi/numra-v1.json` mit Drift-Check + generierter TS-Client (`packages/schema`).
API-Endpoints: Auth, People, Calcs, Reports, Beziehungen, Löschung, Admin (Userliste, Audits,
Promote). Job-Queue in Postgres.

| ID       | Lücke                                          | Ist                                                                     | Soll                                           | Ursache                        | Auswirkung                     | Schweregrad | Priorität                            | Empfehlung                                                | Aufwand |
| -------- | ---------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------ | ------------------------------ | ----------- | ------------------------------------ | --------------------------------------------------------- | ------- |
| G-DAT-01 | Kein Backup-/Retentions-Konzept dokumentiert   | Repo beschreibt Migrationen, kein Backup/Retention für Postgres/Exports | Backup/Restore-Drill, Retention-Policy (DSGVO) | Fokus auf Build, nicht Betrieb | Datenverlustrisiko; Compliance | **Hoch**    | 2                                    | Backup-Konzept (Restic/K8s-Snapshots) + Runbook-Abschnitt | 5       |
| G-DAT-02 | Exports-Speicher ohne Größen-Management        | `numra_exports_data` Volume, keine Policy                               | Max-Größe, TTL, Cleanup                        |                                |                                | **Mittel**  | 3                                    | TTL/Cleanup für Exports-Ordner                            | 2       |
| G-DAT-03 | Kein Schema-Test des Gesamtmodells außer Canon | `profile.schema.json` + Golden                                          | Property-basierte Fuzz für API-Rückgaben       |                                | **Niedrig**                    | 4           | Hypothesis für API-JSON gegen Schema | 3                                                         |

### 3.6 Infrastruktur und Betrieb

**Ist:** Docker-Compose mit 6 Services (postgres16, migrate, api, worker, redis7, pdf, web),
non-root, Healthchecks, multi-stage Dockerfiles, `uv sync --frozen --no-dev --all-packages`.
`compose.production.yml` nur **extern auf VPS** (Host-Laufzeit), nicht im Repo.

| ID       | Lücke                                         | Ist                                                                  | Soll                                  | Ursache                        | Auswirkung                       | Schweregrad | Priorität                           | Empfehlung                                                      | Aufwand |
| -------- | --------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------- | ------------------------------ | -------------------------------- | ----------- | ----------------------------------- | --------------------------------------------------------------- | ------- |
| G-INF-01 | Produktions-Compose nicht im Repo versioniert | `compose.production.yml` nur auf VPS                                 | IaC-Versionierung (Compose/Terraform) | Deployment über Runbook-Ad-hoc | Reproduzierbarkeit, Drift-Gefahr | **Hoch**    | 2                                   | Produktions-Compose + Env-Template ins Repo; Schema-Enforcement | 3       |
| G-INF-02 | Kein Monitoring/Alerting                      | Kein Prometheus/Grafana/Alertmanager, keine Log-Aggregation sichtbar | Beobachtbarkeit + Alerts              |                                | **Hoch**                         | 2           | Observability-Stack + Health-Alerts | 10                                                              |
| G-INF-03 | Kein Backups-Mechanik im Repo                 | nur volumen-Ordner; kein Backup-Dienst                               | automatische DB-Backups               |                                | **Mittel**                       | 3           | Postgres-Backup-Job (cron/restic)   | 4                                                               |

### 3.7 DevOps und Automatisierungsgrad

**Ist:** CI GitHub Actions mit **13 Jobs** (lint, typecheck, unit+property (Postgres/Redis
Services, Coverage ≥90), no-golden-leak, dependency-security (audit), schema/openapi-drift,
web-lint-type-build-test, playwright, pdf, system-e2e, docker-build, docker-compose-e2e inkl.
Log-Leak-Scan). UV 0.5.11, Python 3.11, Node 20. `scripts/verify.py` orchestriert Gates.
Versioning: `--frozen-lockfile`.

| ID       | Lücke                                   | Ist                                                 | Soll                               | Ursache           | Auswirkung              | Schweregrad | Priorität                                            | Empfehlung                                       | Aufwand |
| -------- | --------------------------------------- | --------------------------------------------------- | ---------------------------------- | ----------------- | ----------------------- | ----------- | ---------------------------------------------------- | ------------------------------------------------ | ------- |
| G-DEV-01 | Deployment nicht voll automatisiert     | Produktions-Deploy über Runbook (manuelle Schritte) | CI/CD-Deploy-Pipeline (blue/green) | Fokus auf Test-CI | Release-Geschwindigkeit | **Hoch**    | 2                                                    | CD-Pipeline (Release-Branch → Deploy) + Rollback | 10      |
| G-DEV-02 | Kein Lokal/CI-Env-Matching dokumentiert | Docker-E2E zeigte 4 reale Bugs im Tool-Pfad         | Lokale env == CI-Standard          |                   | **Niedrig**             | 4           | devcontainer/make-Targets für reproduzierbares Setup | 3                                                |
| G-DEV-03 | Keine Dependabot/Renovate               | Versionen gepinnt, aber Bot fehlt                   | Renovate/Dependabot                |                   | **Mittel**              | 3           | Renovate konfigurieren                               | 2                                                |

### 3.8 Testabdeckung und Qualitätssicherung

**Ist (GEMESSEN/BERICHTET):** 301 Tests gesamt (0 failing): 256 Python, 39 Web-Unit, 1
golden-e2e, 1 system-e2e, 1 compose-e2e, 4 PDF (FINAL_VERIFICATION). Testdateien: 49 Test vs
203 Produktions (Verhältnis 0,24; Testzeilen 4637 vs Prod 13789). Coverage Engine ≥90
(100%). Lücken: `engine-astrology` 0 Tests; `engine-interpretation` nur `unit` (8), keine
integration/golden/property; Web-Unit nur 9 Dateien (reports, metrics, i18n, helpers) –
**keine Tests für AppShell, Auth-Flows, Design-System**.

| ID       | Lücke                          | Ist                                                                 | Soll                                | Ursache                  | Auswirkung                        | Schweregrad | Priorität                          | Empfehlung                                | Aufwand     |
| -------- | ------------------------------ | ------------------------------------------------------------------- | ----------------------------------- | ------------------------ | --------------------------------- | ----------- | ---------------------------------- | ----------------------------------------- | ----------- |
| G-TST-01 | Frontend-Components ungetestet | Nur 9 Unit-Dateien; AppShell, Auth, Forms, Design-System ohne Tests | Component-Tests für Kern-Flows      | QA-Fokus lag auf Backend | Regressionen in UI schwer fassbar | **Hoch**    | 2                                  | Vitest+RTL für AppShell/Auth/PersonForm   | 8           |
| G-TST-02 | Interpretation nur Unit-Tests  | kein integration/golden/property für pipeline/composer              | Multi-layer Test der Interpretation | Fokus unit               |                                   | **Mittel**  | 2                                  | Property + integration-Tests für pipeline | 5           |
| G-TST-03 | Astrologie (0 Tests)           | keine Tests (nur Interface)                                         |                                     | Feature disabled         |                                   | **Mittel**  | 3                                  | wenn Feature aktiv: Tests parallel        | 0/ entfällt |
| G-TST-04 | PDF-Suite minimal (4)          | nur `render.test.js`                                                | edge-case-Tests (Fehlerpfade)       |                          | **Mittel**                        | 3           | PDF-Tests erweitern (Fehlermuster) | 3                                         |
| G-TST-05 | Coverage-Gate nur für Engine   | kein Coverage-Gate für API/Web                                      | Gesamt-Coverage-Policy              |                          | **Mittel**                        | 3           | Coverage-Policy für API ≥80%       | 4                                         |

### 3.9 Dokumentation

**Ist:** README (ausführlich), FINAL_VERIFICATION.md, docs/adr/001–007, docs/ops/release-
verification.md, specs/canon-spec.md, specs/profile.schema.json, specs/evidence (11 Dateien),
knowledge/manifest.yaml.

**Fehlend (BERICHTET):** kein `CHANGELOG.md`, kein `docs/architecture.md`, kein
`CONTRIBUTING.md`, kein `docs/api`-Handbuch (nur OpenAPI), kein Deployment-Manifest im Repo.

| ID       | Fehlt                                | Soll                                 | Auswirkung                          | Schweregrad | Priorität | Empfehlung                                              | Aufwand       |
| -------- | ------------------------------------ | ------------------------------------ | ----------------------------------- | ----------- | --------- | ------------------------------------------------------- | ------------- |
| G-DOK-01 | CHANGELOG.md                         | released-basiertes CHANGELOG         | Nachvollziehbarkeit von Versionen   | **Mittel**  | 2         | CHANGELOG aus Git-History generieren (semi-automatisch) | 2             |
| G-DOK-02 | Architektur-Doku (Diagramm)          | s. G-ARCH-03                         | Onboarding                          | **Mittel**  | 3         | docs/architecture.md                                    | 2             |
| G-DOK-03 | CONTRIBUTING.md                      | Developer-Runbook (Setup, Tests, CI) | Beiträger-Einstieg und Einrichtung  | **Mittel**  | 2         | CONTRIBUTING.md + Develop-Section                       | 2             |
| G-DOK-04 | API-Handbuch (menschl.)              | OpenAPI-Spec ist vorhanden           | Nutzer der API (First-/Third-Party) | **Mittel**  | 3         | API-Referenz (Redoc/Handbuch)                           | 3             |
| G-DOK-05 | Release-/Deployment-Manifest im Repo | G-INF-01                             | Reproduktion                        | **Hoch**    | 2         | Deployment-Manifest                                     | (in G-INF-01) |

### 3.10 Team- und Entwicklungsprozesse

**Ist:** 72 Commits, 3 Autoren, Working-Tree sauber, keine Reverts. ADR-Kultur etabliert,
Specs + Evidence für Phasen (0–6) → hoher Prozessreifegrad. **Gap:** kein expliziter
Prozess dokumentiert (Code-Review-Policy, Branching, Definition of Done außerhalb der
GSD-Regeln), keine automatische PR-Check-Integration von Docs.

| ID       | Lücke                                   | Ist                             | Soll                                 | Auswirkung | Schweregrad | Priorität | Empfehlung          | Aufwand |
| -------- | --------------------------------------- | ------------------------------- | ------------------------------------ | ---------- | ----------- | --------- | ------------------- | ------- |
| G-PRO-01 | Kein kodifiziertes DoD/Review-Checklist | Review-Verhalten nur persönlich | Kodierte Check-Liste in CONTRIBUTING |            | **Niedrig** | 3         | DoD in CONTRIBUTING | 1       |
| G-PRO-02 | Release-Prozess teils manuell           | Runbook-basiert                 | CD (G-DEV-01)                        |            | **Hoch**    | 2         | teils in G-DEV-01   |

---

## 4. Technical-Debt-Inventar

Das **vollständige Technical-Debt-Inventar** (7 Kategorien, Priorisierungsmatrix,
Quick Wins vs. Langfristmaßnahmen) wird im zugehörigen Bericht
[`technical-debt.md`](./technical-debt.md) geliefert. Die **Gap-Einzelposten** stehen in §3;
die dortigen IDs werden im Inventar zur Konsistenz referenziert (z. B. G-ARCH-01 ↔ TD-…).

---

## 5. Gesamtbewertung mit Ampelsystem

| Bereich                       | Ampel | Begründung                                                                         |
| ----------------------------- | ----- | ---------------------------------------------------------------------------------- |
| Architektur & Design          | 🟡    | Solide Schichtung + ADRs, aber Astrologie-Engine unfertig (kritisch)               |
| Codequalität & Wartbarkeit    | 🟢    | Kein God-Modul/zyklisch, mypy strict, Coverage Engine; nur wenige lange Funktionen |
| Performance & Skalierbarkeit  | 🟡    | Job-Queue/Redis vorhanden, aber kein Met/Perf-Test                                 |
| Informationssicherheit        | 🟡    | Solide Basis (Argon2id, CSRF, CSP), aber LLM-Smoke unverifiziert + CSP nonce       |
| Datenhaltung & Schnittstellen | 🟡    | OpenAPI/Drift gut, aber Backup/Retention-Konzept fehlt                             |
| Infrastruktur & Betrieb       | 🟡    | Compose-Dev sauber, aber Prod-IaC/Observability fehlt                              |
| DevOps & Automatisierung      | 🟢    | 13 CI-Jobs, Drift-, Leak-, Audit; echter DevCycle                                  |
| Testabdeckung & QA            | 🟢    | 301 Tests, 0 fail, Golden/Prop/System-E2E                                          |
| Dokumentation                 | 🟡    | ADR+Spec stark, aber CHANGELOG/Arch/CONTRIBUTING fehlt                             |
| Team & Prozess                | 🟢    | ADR-, Specs-, Evidence-Kultur, sauberer Tree                                       |

**Gesamt:** 4×🟢 6×🟡 0×🔴 (kein Bereich als ganz rot; Astrologie-Engine als kritischer
Einzelposten in Architektur & Design, daher dort 🟡).

---

## 6. Priorisierte Handlungsempfehlungen

1. **[Kritisch, sofort] Astrologie-Engine spezifizieren und deterministisch implementieren**
   (G-ARCH-01) — 20–30 PT. Blockiert das Produktversprechen "Astrologie".
2. **[Kritisch, sofort] Live-LLM-Verifikation (Ollama)** (G-SEC-01) — 2 PT. Schlüssel als
   Managed Secret in CI, nie im Repo.
3. **[Hoch] Nonce-basiertes CSP** (G-SEC-02) — 5 PT.
4. **[Hoch] Frontend-Components-Tests ausbauen** (G-TST-01) — 8 PT.
5. **[Hoch] Architektur-/Doku-Konsistenz (RBAC), prod-Ia, Monitoring** (G-ARCH-02, G-INF-01,
   G-INF-02) — 10–15 PT.
6. **[Hoch] Performance-Benchmarks + Met-Export** (G-PER-01) — 8 PT.
7. **[Mittel] Docs-CHANGELOG/CONTRIBUTING, API-Handbuch** (G-DOK-01/03/04) — 7 PT.
8. **[Mittel] Refactoring lange Funktionen/Duplikate** (G-COD-01/02) — 12 PT.

---

## 7. Maßnahmen-Roadmap

### Kurzfristig (0–3 Monate)

- Astrology-Engine: Spec + Prototyp (G-ARCH-01) — Start
- Live-Ollama-Smoke (G-SEC-01)
- Nonce-CSP (G-SEC-02)
- Frontend-Components-Tests Auth/AppShell (G-TST-01)
- CHANGELOG + CONTRIBUTING (G-DOK-01/03)

### Mittelfristig (3–6 Monate)

- Astrologie deterministische Implementierung + golden (G-ARCH-01) — Fortführung
- Backend-Benchmarks + Metrik-Export (G-PER-01)
- Prod-Ia / CD-Pipeline (G-INF-01/G-DEV-01)
- Prod-Compose ins Repo
- Backup-/Retention-Konzept (G-DAT-01)

### Langfristig (6–12 Monate)

- Monitoring/Observability-Stack (G-INF-02)
- SAST-Job (G-SEC-03)
- Refactoring lange Funktionen/Duplikate (G-COD-01/02)
- Property-/Integration-Tests Interpretation (G-TST-02)

---

## 8. KPIs zur Erfolgsmessung

| KPI                                | Ziel                               | Quell-Metrik             |
| ---------------------------------- | ---------------------------------- | ------------------------ |
| Astrologie-Feature-Implementierung | Engine + Golden-Test in production | `engine-astrology` Tests |
| Live-LLM-Smoke                     | `LIVE_LLM_SMOKE = VERIFIED`        | CI-Job                   |
| CSP-Stärke                         | nonce/strict-dynamic aktiv         | next.config              |
| Frontend-Test                      | Coverage-Ratio UI > 50%            | Vitest                   |
| Backend-P95-Latenz                 | Metrik-Export + SLO                | API-Perf-Test            |
| Observability                      | Alerts aktiv                       | Grafana/Prom             |
| Coverage-Gesamt                    | API ≥90%                           | pytest-cov               |

---

## 9. Anhang / Glossar

- **ADR** — Architecture Decision Record
- **Canon-Spec** — formale Berechnungs-Spezifikation (deterministisch)
- **Golden Test** — deterministischer Referenztest
- **IaC** = Infrastructure as Code
- **SAST** = Static Application Security Testing
- **LLM** = Large Language Model; `NUMRA_LLM_PROVIDER` steuert Provider
- **unfrozen feature** = explizit als nicht-deterministisch ausgeschlossenes Feature (ADR-006)

---

_Bericht erstellt gem. `projekt-diagnose`-Skill-Methode; alle Aufwandswerte = ANNAHME._
