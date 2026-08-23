# Technical-Debt-Report — numra-v1

> **Bericht:** Erfassung, Bewertung und Priorisierung technischer Schulden
> **Stand:** 2026-08-23 · **Branch:** `main` · **Commit:** `f4be7ee7`
> **Konsistent mit:** [`gap-analyse.md`](./gap-analyse.md)
> **Zielgruppe:** Management und Entwicklungsteam

---

## 1. Management Summary

Das System `numra-v1` weist insgesamt eine **geringe bis mittlere technische Schuld** auf.
Die Architektur ist sauber geschichtet und durch 7 ADRs abgesichert; Tests (301, 0 failing),
deterministische Engines und eine breite CI (13 Jobs) halten die Qualität hoch. Gleichwohl
fallen zwei **kritische Schuldposten** ins Gewicht:

- **TD-ARCH-01 — Astrologie-Engine ohne Implementierung** (Feature unfertig, reines Interface).
- **TD-SEC-01** Live-LLM-Verifikation (Ollama) unverifiziert.

Beide tragen erhebliches Produkt- und Betriebsrisiko und sollten zuerst getilgt werden.
Daneben bestehen **architektur- und dokumentationsbezogene Schulden** (fehlende
Architektur-Doku, CHANGELOG, Produktions-IaC) sowie **ungedeckte Testflächen im Frontend**
und **fehlende Observability**. Die **laufenden Folgekosten** der Schulden sind moderat,
steigen aber mit jeder neuen Feature-Schicht (v. a. in Astrologie, Frontend-Forms und LLM).

**Gesamt-Tilgungsaufwand (Schätzung, ANNAHME): ca. 150–190 PT.** Davon entfallen
**~20 % (30–40 PT) auf kritische/halten Posten** (Astrologie, LLM-Verifikation). Die
**Quick Wins** (≤5 PT, niedriges Risiko, hoher Nutzen) umfassen Dokumentation, CHANGELOG,
CONTRIBUTING, API-Handbuch und ein kleines Refactoring der Form-Duplikate.

> **Hinweis:** Alle PT-Angaben sind **qualifizierte Schätzannahmen** ohne
> Team-/Kapazitätsdaten; vor Umsetzung je Posten neu zu bewerten.

---

## 2. Methodik und Vorgehensweise

Wie in der Gap-Analyse (§2) beschrieben: Messung via `projekt-diagnose`-Skripte
(`GEMESSEN`), Artefakt-Recherche (`BERICHTET`), Nicht-Bestimmbares (`UNVERIFIZIERT`),
fehlende Basis (`ANNAHME`). Technische Schulden wurden **konsistent zu den Gap-IDs**
klassifiziert; jede Gap mit Realisierungskosten und -risiko mündet hier als Schulposten.

**Fehlalarm-Bereinigung:** Die `sich_sql_verkettung`-Treffer (composer.py, page.tsx) wurden
verifiziert und als **Fehlalarme** ausgeschlossen (Text-/URL-Komposition, kein SQL).

**Geheimnis-Scoping:** `muster_scan` meldete 14 `geheim_url_zugangsdaten`-Treffer. Alle
betreffen **CI-/Test-/Dev-Konfigurationen** (ci.yml, config.py-Default, conftest, compose);
es wurden **keine Werte ausgelesen**. Diese werden nicht als reale Schuld, sondern als
**Härtung** geführt (TD-SEC-04, niedrig).

---

## 3. Technical-Debt-Inventar

### 3.1 Kategorien-Übersicht

| Kategorie                     | Anzahl Posten | davon kritisch | davon hoch |
| ----------------------------- | ------------- | -------------- | ---------- |
| Code-Schulden                 | 3             | 0              | 0          |
| Architektur-Schulden          | 2             | 1              | 1          |
| Infrastruktur-Schulden        | 2             | 0              | 1          |
| Test-Schulden                 | 3             | 0              | 1          |
| Dokumentations-Schulden       | 4             | 0              | 1          |
| Dependency-/Versions-Schulden | 2             | 0              | 0          |
| Sicherheits-Schulden          | 3             | 1              | 1          |
| **Gesamt**                    | **19**        | **2**          | **4**      |

### 3.2 Inventar je Kategorie

#### Code-Schulden

| ID        | Komponente                              | Beschreibung                                                                            | Entstehungsursache                       | Schweregrad | Risiko bei Nichtbehebung           | Folgekosten        | Aufwand (PT) | Dringlichkeit |
| --------- | --------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------- | ----------- | ---------------------------------- | ------------------ | ------------ | ------------- |
| TD-COD-01 | `apps/web` Formulare (people/new, edit) | Lange Formular-Komponenten (EditPersonForm 243 Z., NewPersonForm 201 Z.) mit Duplikaten | Screens ohne Abstraktion parallel gebaut | **Mittel**  | Wartungs-/Merge-Konflikte, Drift   | moderate, steigend | 8            | Mittel        |
| TD-COD-02 | `engine-interpretation/pipeline.py`     | `_generate_section` 152 Z., `generate_report` 72 Z., 8 Parameter                        | organisch gewachsen                      | **Mittel**  | Refactoring-Risiko, Tests bindend  | moderat            | 5            | Mittel        |
| TD-COD-03 | CLI/Scripts                             | 17× `print` statt Logging (verify.py, cli.py, export_openapi.py)                        | Skript-Kultur                            | **Niedrig** | eingeschränkte Debug-Observability | gering             | 2            | Niedrig       |

#### Architektur-Schulden

| ID         | Komponente         | Beschreibung                                                            | Entstehungsursache                  | Schweregrad  | Risiko                                                                         | Folgekosten    | Aufwand | Dringlichkeit |
| ---------- | ------------------ | ----------------------------------------------------------------------- | ----------------------------------- | ------------ | ------------------------------------------------------------------------------ | -------------- | ------- | ------------- |
| TD-ARCH-01 | `engine-astrology` | Astrologie-Engine nur Interface (NotImplementedError), Feature unfertig | Scope-Entscheid, unfrozen (ADR-006) | **Kritisch** | Produktversprechen unerfüllt, Feature-Blocker, Integrationskosten später höher | hoch, wachsend | 20–30   | **Hoch**      |
| TD-ARCH-02 | System gesamt      | Doku/Code-Divergenz um RBAC/Admin (Runbook V1.6)                        | Versionierung über Repo hinaus      | **Hoch**     | falsche Sicherheits-/Fähigkeitsannahmen, Onboarding-Fehler                     | moderat        | 3       | Hoch          |

#### Infrastruktur-Schulden

| ID        | Komponente      | Beschreibung                                                                                 | Ursache                        | Schweregrad | Risiko                                   | Folgekosten      | Aufwand | Dringlichkeit |
| --------- | --------------- | -------------------------------------------------------------------------------------------- | ------------------------------ | ----------- | ---------------------------------------- | ---------------- | ------- | ------------- |
| TD-INF-01 | Prod-Deployment | `compose.production.yml` nur extern (VPS), nicht versioniert; kein Backup-/Retention-Konzept | Deployment über Runbook-Ad-hoc | **Hoch**    | Reproduktions-/Drift-/Datenverlustrisiko | hoch bei Ausfall | 8       | **Hoch**      |
| TD-INF-02 | Betrieb         | Kein Monitoring/Alerting, kein Metrik-Export, keine Log-Aggregation                          | Fokus auf Build                | **Hoch**    | Blindheit bei Störungen, SLA-frei        | hoch             | 10      | Hoch          |

#### Test-Schulden

| ID        | Komponente            | Beschreibung                                                                            | Ursache              | Schweregrad | Risiko                         | Folgekosten      | Aufwand | Dringlichkeit |
| --------- | --------------------- | --------------------------------------------------------------------------------------- | -------------------- | ----------- | ------------------------------ | ---------------- | ------- | ------------- |
| TD-TST-01 | Frontend              | Kern-Komponenten (AppShell, Auth, Forms, Design-System) ungetestet (nur 9 Unit-Dateien) | QA-Fokus auf Backend | **Hoch**    | UI-Regressionen unentdeckt     | moderat wachsend | 8       | Hoch          |
| TD-TST-02 | engine-interpretation | Nur Unit-Tests; kein integration/golden/property                                        | Fokus unit           | **Mittel**  | falsche Komposition unentdeckt | moderat          | 5       | Mittel        |
| TD-TST-03 | PDF, API-Coverage     | PDF-Suite minimal (4); Coverage-Gate nur Engine                                         | Fokus                | **Mittel**  | Edge-Fehler                    | moderat          | 4       | Mittel        |

#### Dokumentations-Schulden

| ID        | Komponente | Beschreibung                                            | Ursache       | Schweregrad | Risiko                              | Folgekosten    | Aufwand        | Dringlichkeit |
| --------- | ---------- | ------------------------------------------------------- | ------------- | ----------- | ----------------------------------- | -------------- | -------------- | ------------- |
| TD-DOK-01 | Repo       | Kein `CHANGELOG.md`                                     | Priorisierung | **Mittel**  | Versions-Nachvollziehbarkeit        | gering         | 2              | Mittel        |
| TD-DOK-02 | Repo       | Kein `docs/architecture.md` (kein Diagramm)             | nur Text      | **Mittel**  | Onboarding, Abhängigkeits-Erkennung | gering         | 2              | Mittel        |
| TD-DOK-03 | Repo       | Kein `CONTRIBUTING.md`, kein API-Handbuch (nur OpenAPI) | Fokus         | **Mittel**  | Beiträger-Einstieg erschwert        | moderat        | 3              | Mittel        |
| TD-DOK-04 | Repo       | Deployment-Manifest nicht im Repo                       | s. TD-INF-01  | **Hoch**    | Reproduzierbarkeit                  | (in TD-INF-01) | (in TD-INF-01) | Hoch          |

#### Dependency-/Versions-Schulden

| ID        | Komponente       | Beschreibung                                                                     | Ursache       | Schweregrad | Risiko                                             | Folgekosten      | Aufwand | Dringlichkeit |
| --------- | ---------------- | -------------------------------------------------------------------------------- | ------------- | ----------- | -------------------------------------------------- | ---------------- | ------- | ------------- |
| TD-DEP-01 | Toolchain        | Kein Renovate/Dependabot; Versionen gepinnt, aber keine automatische Update-Bots | Initial-Setup | **Mittel**  | Dependabot-Alerts nicht proaktiv, manuelle Updates | gering, steigend | 2       | Mittel        |
| TD-DEP-02 | Playwright-Drift | Playwright (pdf) war Version-driftig (Fix: gepinnt)                              | Docker-Basis  | **Niedrig** | Drift-Rückfall                                     | gering           | 1       | Niedrig       |

#### Sicherheits-Schulden

| ID        | Komponente      | Beschreibung                                            | Ursache             | Schweregrad  | Risiko                               | Folgekosten | Aufwand | Dringlichkeit |
| --------- | --------------- | ------------------------------------------------------- | ------------------- | ------------ | ------------------------------------ | ----------- | ------- | ------------- |
| TD-SEC-01 | LLM-Pfad        | Live-Ollama-Verifikation `NOT_VERIFIED` (kein API-Key)  | fehlender CI-Secret | **Kritisch** | unverifizierter Produktions-LLM-Pfad | moderat     | 2       | **Hoch**      |
| TD-SEC-02 | Web-CSP         | CSP ohne `nonce`/`strict-dynamic` (`unsafe-inline`)     | Next-14-Kompromiss  | **Hoch**     | XSS-Risiko erhöht                    | moderat     | 5       | Hoch          |
| TD-SEC-03 | SAST            | Kein SAST-Job im CI (nur audit)                         | Fokus               | **Mittel**   | neue Schwachstellen unentdeckt       | moderat     | 3       | Mittel        |
| TD-SEC-04 | Dev-Credentials | Zugangsdaten in CI/Dev-URLs (kein reales Leck, Härtung) | Dev-Konvention      | **Niedrig**  | Falls commitet, Leak-Gefahr          | gering      | 1       | Niedrig       |

---

## 4. Priorisierungsmatrix (Auswirkung × Aufwand)

**Legende Aufwand:** `S` ≤ 3 PT · `M` 4–9 PT · `L` ≥ 10 PT · `XL` ≥ 20 PT
**Auswirkung:** `K` kritisch, `H` hoch, `M` mittel, `N` niedrig

| ID              | Posten               | Auswirkung | Aufwand | Priorität |
| --------------- | -------------------- | ---------- | ------- | --------- |
| TD-ARCH-01      | Astrologie-Engine    | K          | L       | **1**     |
| TD-SEC-01       | LLM-Verifikation     | K          | S       | **1**     |
| TD-SEC-02       | CSP nonce            | H          | M       | **2**     |
| TD-TST-01       | Frontend-Tests       | H          | M       | **2**     |
| TD-INF-01       | Prod-IaC/Backup      | H          | M       | **2**     |
| TD-INF-02       | Monitoring           | H          | L       | **2/3**   |
| TD-ARCH-02      | Doku-RBAC            | H          | S       | **2**     |
| TD-COD-01       | Form-Duplikate       | M          | M       | 3         |
| TD-COD-02       | Pipeline             | M          | M       | 3         |
| TD-TST-02       | Interpretation-Tests | M          | M       | 3         |
| TD-TST-03       | PDF/Coverage         | M          | S       | 3         |
| TD-DOK-01/02/03 | Docs                 | M          | S/M     | 3         |
| TD-DEP-01/02    | Dependency-Bot       | M          | S       | 3         |
| TD-SEC-03       | SAST                 | M          | M       | 3         |
| TD-COD-03       | Logging              | N          | S       | 4         |
| TD-SEC-04       | Dev-Härtung          | N          | S       | 4         |

### Quick Wins (hohe Wirkung / geringer Aufwand)

- **TD-SEC-01** (LLM-Smoke, 2 PT, kritisch)
- **TD-ARCH-02** (Doku-Konsistenz, 3 PT)
- **TD-DOK-01/02/03** (CHANGELOG/Arch/CONTRIBUTING, ~7 PT)
- **TD-DEP-01** (Renovate, 1 PT)

### Strategische Langfristmaßnahmen

- **TD-ARCH-01** (Astrologie-Engine, 20–30 PT) — Kern-Produktausbau
- **TD-INF-02** (Monitoring/Observability, ~10 PT)
- **TD-INF-01** (Produktions-IaC/Backup, 8 PT)
- **TD-TST-01** (Frontend-Test-Kultur, ~8 PT)

---

## 5. Gesamtbewertung je Kategorie (Ampel)

| Kategorie                     | Ampel | Begründung                                                                |
| ----------------------------- | ----- | ------------------------------------------------------------------------- |
| Code-Schulden                 | 🟢    | Wenige lange Funktionen/Duplikate; kein God-Modul, kein zyklischer Import |
| Architektur-Schulden          | 🟡    | Saubere Schichtung + ADR, aber Astrologie unfertig (kritisch)             |
| Infrastruktur-Schulden        | 🟡    | Compose-Dev sauber, aber Prod-IaC/Monitoring fehlt                        |
| Test-Schulden                 | 🟢    | 301 Tests, 0 fail, Golden/Prop/System-E2E; UI-Lücke aber lokal            |
| Dokumentations-Schulden       | 🟡    | ADR+Spec stark; CHANGELOG/Arch/CONTRIBUTING fehlt                         |
| Dependency-/Versions-Schulden | 🟢    | gepinnt, frozen-lockfile, Audit-Jobs; Bot fehlt                           |
| Sicherheits-Schulden          | 🟡    | Solide Basis, aber LLM-Smoke unverifiziert + CSP nonce                    |

**Gesamt-Trend:** geringe bis mittlere Schuld, zwei kritische Einzelposten (Astrologie,
LLM-Verifikation) → **konsolidiert: gelb bis grün**, mit klarer Priorität auf die zwei
kritischen Posten.

---

## 6. Priorisierte Handlungsempfehlungen

1. **TD-ARCH-01 + TD-SEC-01 sofort** — Astrologie-Spez + deterministische Engine (20–30 PT);
   LLM-Smoke via Managed Secret (2 PT).
2. **TD-SEC-02 (CSP nonce)** — 5 PT, schnell tilgbar.
3. **TD-TST-01 (Frontend-Tests)** — 8 PT; verhindert UI-Regressionen.
4. **TD-INF-01/02 (Prod-IaC + Monitoring)** — ~18 PT; Reproduzierbarkeit + Blindheit.
5. **TD-DOK-01/02/03** — ~7 PT; Onboarding/Nachvollziehbarkeit (Quick Wins).
6. **TD-COD-01/02 (Refactoring)** — 13 PT; senkt Wartung.
7. **TD-DEP-01 (Renovate)** — 1 PT.

---

## 7. Maßnahmen-Roadmap (Zeithorizonte)

### Kurzfristig (0–3 Monate)

- TD-ARCH-01 Start (Spec + Prototyp), TD-SEC-01, TD-SEC-02, TD-TST-01, TD-DOK-01/02/03.

### Mittelfristig (3–6 Monate)

- TD-ARCH-01 Fortführung (Engine + golden), TD-INF-01 (Prod-IaC/Backup), TD-TST-02,
  TD-DEP-01 (Renovate).

### Langfristig (6–12 Monate)

- TD-INF-02 (Monitoring/Observability), TD-COD-01/02 (Refactoring), TD-TST-03, TD-SEC-03 (SAST).

---

## 8. KPIs zur Erfolgsmessung (Abgestimmt mit Gap-Analyse §8)

| KPI                | Ziel                          | Quelle           |
| ------------------ | ----------------------------- | ---------------- |
| Astrologie-Feature | Engine + Golden in production | engine-astrology |
| LLM-Smoke          | `VERIFIED`                    | CI               |
| CSP-Stärke         | nonce aktiv                   | next.config      |
| Frontend-Coverage  | >50 % UI                      | Vitest           |
| P95-Latenz         | Metrik + SLO                  | Perf-Test        |
| Observability      | Alerts aktiv                  | Prom/Grafana     |
| Gesamt-Coverage    | API ≥90 %                     | pytest-cov       |

---

## 9. Anhang / Glossar

- **ADR** — Architecture Decision Record
- **Canon-Spec** — deterministische Berechnungsspezifikation
- **CSP** — Content-Security-Policy
- **SAST** — Static Application Security Testing
- **IaC** — Infrastructure as Code
- **Golden Test** — deterministischer Referenztest
- **Job-Queue** — Postgres-Queue (ADR-004), `FOR UPDATE SKIP LOCKED`
- **unfrozen feature** — nicht-deterministisches, ausgeschlossenes Feature (ADR-006)
- **PT** — Personentage (Aufwandsschätzung = ANNAHME)

---

_Bericht erstellt nach `projekt-diagnose`-Methode; alle PT-Angaben = ANNAHME. Konsistent mit
`gap-analyse.md`._
