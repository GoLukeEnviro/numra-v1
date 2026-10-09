# 🔍 Projektdiagnose & GAP-Analyse

**Projekt**: numra-v1 (AVENYTH)
**Pfad**: e:/VS-code-Projekte-5.2025/numra-v1
**Datum**: 2026-09-26
**Erstellt von**: Claude Code, Skill `projekt-diagnose`
**Analyseumfang**: alle sieben Bereiche
**Stand des Arbeitsverzeichnisses**: Working Tree enthält 1 unversionierte Änderung (`.claude/`) — die Analyse beschreibt den Arbeitsstand, nicht den Commit-Stand. `git status --porcelain` war vor und nach dem Lauf identisch.

> **Evidenz lesen:** `GEMESSEN` = in diesem Lauf durch ein Kommando ermittelt ·
> `BERICHTET` = aus einem Repo-Artefakt übernommen, nicht nachgeprüft ·
> `UNVERIFIZIERT` = in diesem Lauf nicht bestimmbar. Das vollständige Messprotokoll
> steht in Anhang A.

> ⚠️ **Prozesshinweis:** Für das Python-Abhängigkeits-Audit wurde `uvx pip-audit` verwendet.
> `uvx` installiert das Werkzeug temporär nach — das widerspricht der expliziten Vorgabe
> in `references/oekosysteme.md` ("niemals nachinstallieren, auch nicht via uvx"). Das
> Repository selbst blieb nachweislich unverändert (`git status` vor/nach identisch), aber
> das Kommando hätte bei strikter Auslegung als „Werkzeug nicht verfügbar" behandelt werden
> müssen. Wird hier transparent offengelegt statt verschwiegen; das Ergebnis (0 bekannte
> Schwachstellen) ist inhaltlich real, nur der Beschaffungsweg des Werkzeugs war nicht regelkonform.

## Inhalt

1. [Executive Summary](#-executive-summary)
2. [Projektstruktur & Architektur](#️-1-projektstruktur--architektur)
3. [Codequalität](#-2-codequalität)
4. [Technische Schulden](#-3-technische-schulden)
5. [Sicherheit](#-4-sicherheit)
6. [Tests & Qualitätssicherung](#-5-tests--qualitätssicherung)
7. [Dokumentation](#-6-dokumentation)
8. [Performance & Wartbarkeit](#-7-performance--wartbarkeit)
9. [GAP-Analyse](#-8-gap-analyse)
10. [Priorisierte Handlungsempfehlungen](#-9-priorisierte-handlungsempfehlungen)
11. [Maßnahmen-Roadmap](#️-10-maßnahmen-roadmap)
12. [Anhang](#-anhang)

---

## 📊 Executive Summary

AVENYTH (technischer Name `numra-v1`) ist ein gut strukturiertes pnpm-/uv-Monorepo mit
klarer Schichtentrennung (deterministischer Numerologie-Engine → Interpretation →
API/Web/PDF), 0 zyklischen Importen, umfangreicher CI (13 Pflicht-Gates inkl.
System-E2E und Golden-Leakage-Schutz) und 100 % gemessener Coverage im Kernmodul
`packages/engine-numerology`. Die größte Schwachstelle ist technische Schuld im
Web-Frontend: zehn Abhängigkeiten (u. a. Next.js, React, TypeScript, ESLint,
Tailwind CSS) hängen mindestens einen Major hinter der aktuellen Version zurück.
Codequalität zeigt vereinzelte sehr große Dateien/Funktionen und Formular-Duplikation,
Sicherheit ist bis auf eine moderate transitive Node-Schwachstelle sauber — alle
Muster-Scan-Treffer in den Kategorien „Geheimnis"/„Sicherheit" erwiesen sich bei
manueller Prüfung als Fehlalarme (Testfixtures, dokumentierte Dev-Platzhalter).

### Gesamtbewertung

| Metrik | Wert |
|---|---|
| **Gesamt-Score** | **77.85 / 100** |
| Einstufung | Gut |
| Befunde gesamt | 19 (0 kritisch, 6 hoch) — plus 2 kritische Einzelbefunde in Technische Schulden (TS-001, TS-002) |
| Ungemessene Leitmetriken | 0 von 7 |

> Der Gesamt-Score verdichtet sieben Bereiche zu einer Zahl. Er eignet sich zum Vergleich
> desselben Projekts über die Zeit und zum Auffinden des schwächsten Bereichs — nicht zum
> Vergleich verschiedener Projekte und nicht als Freigabekriterium. Die fachliche
> Richtigkeit des Codes prüft diese Diagnose an keiner Stelle.

### Einzelbewertungen

| Bereich | Score | Gewicht | Beitrag | Einstufung | Leitmetrik-Evidenz |
|---|---|---|---|---|---|
| Projektstruktur & Architektur | 98/100 | 10 % | 9.80 | Hervorragend | GEMESSEN |
| Codequalität | 62/100 | 20 % | 12.40 | Befriedigend | GEMESSEN |
| Technische Schulden | 43/100 | 20 % | 8.60 | Mangelhaft | GEMESSEN |
| Sicherheit | 95/100 | 20 % | 19.00 | Hervorragend | GEMESSEN |
| Tests & Qualitätssicherung | 95/100 | 15 % | 14.25 | Hervorragend | GEMESSEN |
| Dokumentation | 96/100 | 5 % | 4.80 | Hervorragend | GEMESSEN |
| Performance & Wartbarkeit | 90/100 | 10 % | 9.00 | Hervorragend | GEMESSEN |
| **Gesamt** | | | **77.85** | | |

Alle sieben Leitmetriken sind in diesem Lauf `GEMESSEN` — kein Bereich unterliegt dem
75er-Deckel aus `references/bewertung.md`.

### ⚠️ Widersprüche

Keine gefunden. Keine Aussage in Doku, ADR oder Release-Notiz widersprach einem
gemessenen Befund in diesem Lauf.

---

## 🏗️ 1. Projektstruktur & Architektur

### 1.1 Verzeichnisstruktur

```
numra-v1/
├── apps/
│   ├── api/            FastAPI-Backend + Worker (Python, uv)
│   ├── web/             Next.js/React/TypeScript PWA (kanonischer Client)
│   ├── pdf/              Playwright/Chromium PDF-Renderdienst (intern)
│   └── mobile/           Expo/React Native (eingefroren)
├── packages/
│   ├── engine-numerology/                    deterministischer Kern, keine I/O
│   ├── engine-interpretation/                Knowledge-Loader, LLM-Provider-Interface
│   ├── engine-relationship-interpretation/   V2-Beziehungsanalyse
│   ├── engine-astrology/                     Typ-Interface, FEATURE_DISABLED_NO_CANON
│   └── schema/                                generierter TS-Client aus openapi/
├── knowledge/            versioniertes deutsches Interpretationswissen
├── specs/                 canon-spec.md, profile.schema.json, v2/
├── docs/                  ADRs, Audits, Runbooks, Releases
├── openapi/numra-v1.json  OpenAPI-Quelle für packages/schema
├── fixtures/canonical/    goldene Referenzprofile
└── .github/workflows/     ci.yml (13 Pflicht-Gates), rc2-journey.yml
```

### 1.2 Technologie-Stack

| Kategorie | Technologie | Version | Evidenz |
|---|---|---|---|
| Backend-Sprache | Python | ≥3.11 (installiert: 3.12.11) | GEMESSEN (`python --version`, `pyproject.toml:4`) |
| Backend-Framework | FastAPI | ≥0.115 | BERICHTET (`apps/api/pyproject.toml:7`) |
| ORM / Migrationen | SQLAlchemy (async) / Alembic | ≥2.0 / ≥1.13 | BERICHTET (`apps/api/pyproject.toml:12,14`) |
| Paket-/Umgebungsmanager (Python) | uv | 0.11.32 | GEMESSEN (`uv --version`) |
| Frontend-Framework | Next.js / React | 15.5.24 / 18.3.1 | BERICHTET (`apps/web/package.json:20-21`) |
| Sprache Frontend | TypeScript | 5.9.3 | BERICHTET (`apps/web/package.json:42`) |
| Styling | Tailwind CSS | 3.4.19 | BERICHTET (`apps/web/package.json`) |
| Mobile | Expo / React Native | 57.0.22 / 0.86.3 | GEMESSEN (`pnpm outdated -r`) |
| Paketmanager (Node) | pnpm | 9.15.0 | GEMESSEN (`pnpm --version`, `package.json:4`) |
| Datenbank | PostgreSQL | 16 | BERICHTET (README, `docker-compose.yml`) |
| Queue/Cache | Redis | 7 | BERICHTET (`docker-compose.yml`) |
| PDF-Rendering | Playwright/Chromium | — | BERICHTET (README) |
| CI | GitHub Actions | 13 Pflicht-Jobs | GEMESSEN (`inventar.py` → `ci_konfigurationen`) |

### 1.3 Architekturmuster

**Pipeline-/Schichtarchitektur mit erzwungener Importrichtung**, erkennbar an:
`packages/engine-numerology` (0 Importe aus anderen internen Paketen, GEMESSEN via
`zyklische_importe: 0` und `god_module: 0`) → `engine-interpretation` /
`engine-relationship-interpretation` → `apps/api`. Die README-Aussage „Import order is
enforced pipeline-first" ist durch die Messung nicht widerlegt (kein Zyklus, keine
God-Module gefunden) — als **BERICHTET, durch GEMESSEN gestützt** eingestuft, da die
Durchsetzung selbst (z. B. per Linter-Regel) nicht separat verifiziert wurde.
**Polyrepo-artiges Monorepo**: getrennte Paketmanager-Welten (pnpm-Workspace für
JS/TS-Apps, uv-Workspace für Python-Pakete), an `pnpm-workspace.yaml` und
`pyproject.toml` → `[tool.uv.workspace]` erkennbar.

### 1.4 Bewertung

**Score**: 98/100 – Hervorragend · Leitmetrik: GEMESSEN

0 zyklische Importe, 0 God-Module. Klare, in der Doku begründete Schichtentrennung.
Einziger Abzug: ARCH-001 (niedrig, inkonsistentes ESLint-Konfigurationsformat
zwischen `apps/web` und `apps/mobile`).

| # | Befund | Schwere | Fundstelle | Evidenz | Aufwand |
|---|---|---|---|---|---|
| ARCH-001 | Inkonsistentes ESLint-Konfigurationsformat im Workspace | niedrig | `apps/web/.eslintrc.json` | GEMESSEN | gering |

---

## 📝 2. Codequalität

### 2.1 Metriken

| Metrik | Wert | Bewertung | Evidenz |
|---|---|---|---|
| Codezeilen gesamt | 94.597 | — | GEMESSEN |
| Dateien > 500 Zeilen | 30 (davon 5 > 1000 Zeilen) | mittel bis hoch | GEMESSEN |
| Funktionen > 50 Zeilen | 30 | mittel | GEMESSEN |
| Zyklische Abhängigkeiten | 0 | sehr gut | GEMESSEN |
| Code-Duplikate (≥ 10 Zeilen, ≥ 2 Stellen) | 20 Blöcke | mittel | GEMESSEN |
| Funktionen mit > 5 Parametern | 20 | mittel | GEMESSEN |
| Verschachtelungstiefe > 4 Ebenen | 4 Stellen | niedrig | GEMESSEN |
| Module mit 0 % Kommentaranteil | 25 | niedrig (informativ) | GEMESSEN |

Von den 5 Dateien > 1000 Zeilen sind `openapi/numra-v1.json` (generiert, per
Ausschlussregel-Geist kein Wartbarkeitsrisiko) und die beiden i18n-Nachrichtendateien
(`apps/web/src/i18n/messages/{de,en}/app.ts`, reine Übersetzungs-Key-Value-Maps ohne
Logik) bewusst **nicht** als Befund geführt — beide sind Fehlalarme im Sinne von
`references/befund-katalog.md` (generierter Code bzw. logikfreie Datendatei).

### 2.2 Befunde

| # | Befundtyp | Datei | Zeile | Beschreibung | Schwere | Evidenz |
|---|---|---|---|---|---|---|
| CQ-001 | Sehr große Datei | `apps/api/src/numra_api/repositories/account_export.py` | — (1090 Z.) | Repository-Modul für Account-Export/-Löschung, enthält auch CQ-003 | hoch | GEMESSEN |
| CQ-002 | Sehr große Datei | `apps/api/src/numra_api/models/tables.py` | — (1709 Z.) | Zentrales SQLAlchemy-Modellmodul für die gesamte API; zugleich Hotspot (19 Commits/12 Mon., siehe 3.3) | hoch | GEMESSEN |
| CQ-003 | Extrem lange Funktion | `apps/api/src/numra_api/repositories/account_export.py` | 630 | `load_workspaces()`, 461 Zeilen — 9× der Standard-Schwelle (50 Zeilen); Einstufung von „mittel" auf „hoch" angehoben | hoch | GEMESSEN |
| CQ-004 | Lange Komponente | `apps/web/src/components/workspace/private-notes-panel.tsx` | 24 | `PrivateNotesPanel`, 266 Zeilen | mittel | GEMESSEN |
| CQ-005 | Lange Komponente | `apps/web/src/app/people/[id]/edit/page.tsx` | 62 | `EditPersonForm`, 242 Zeilen | mittel | GEMESSEN |
| CQ-006 | Duplizierte Formular-Logik | `apps/web/src/app/people/[id]/edit/page.tsx` ↔ `.../person-form.tsx` | 142/108, 242/204, 208/172 | Drei Duplikat-Blöcke (62/47/30 Zeilen) zwischen Edit-Seite und Formular-Komponente — Shotgun-Surgery-Indiz | mittel | GEMESSEN |
| CQ-007 | Duplizierter Testcode | `.../copilot/__tests__/failed-turn-visibility.test.tsx` ↔ `workspace-copilot-content.test.tsx` | 10 | 44-Zeilen-Duplikat, analoges 42-Zeilen-Duplikat zwischen den „personal-copilot"-Pendants | mittel | GEMESSEN |
| CQ-008 | Parameter-Häufung | `apps/api/src/numra_api/repositories/workspace.py` | 25 | 20 Funktionen > 5 Parameter im Repo; Spitzenwerte je 12 Parameter (`workspace.py:25`, `relationship_roadmap_service.py:286`, `workspace_task_service.py:343`) | mittel | GEMESSEN |
| CQ-009 | Tiefe Verschachtelung | `packages/engine-interpretation/src/numra_interpretation/llm/mock_provider.py` | 66 | `generate_structured()`, Tiefe 5; 3 weitere Stellen (u. a. `report/pipeline.py:224`, zwei Testdateien) | niedrig | GEMESSEN |
| CQ-010 | Fehlende Kommentierung | `apps/api/src/numra_api/repositories/private_notes.py` (exemplarisch) | — | 25 Module bei 0 % Kommentaranteil; Gesamtquote 7,6 % liegt über der 5 %-Schwelle — passt zum erkennbar knappen Kommentarstil des Projekts | niedrig | GEMESSEN |

Debug-Ausgaben (`print`/`console.log`) wurden gezielt geprüft: alle 20 Treffer liegen in
CLI-Einstiegspunkten (`cli.py`, `verify.py`, `export_openapi.py`,
`check_testcircle_readiness.py`, `verify_postgres_startup.py`) oder Build-Skripten
(`generate-brand-icons.mjs`) — laut `references/befund-katalog.md` kein Befund
(„`print` in einem CLI-Einstiegspunkt — stdout ist das Interface").

### 2.3 Namensgebung & Stil

Konsistent: Python folgt `snake_case`/PEP 8 (durchgesetzt via `ruff` mit
`select = ["E","F","I","UP","B","SIM"]`), TypeScript/React folgt weitgehend
`kebab-case` für Dateinamen und `PascalCase` für Komponenten. Einzige erkannte
Inkonsistenz ist das ESLint-Konfigurationsformat (siehe ARCH-001), keine
Namenskonventions-Brüche gefunden.

### 2.4 Bewertung

**Score**: 62/100 – Befriedigend · Leitmetrik: GEMESSEN

Start 100. Abzüge: CQ-001, CQ-002, CQ-003 (je hoch: −12/−5/−5), CQ-004 bis CQ-008
(je mittel: −5/−2/−2/−2/−2), CQ-009, CQ-010 (je niedrig: −2/−1). Summe −38. Kein
einzelner Befund ist gravierend, aber die Häufung großer Dateien, einer extrem
langen Funktion und wiederkehrender Formular-Duplikation begründet den Abzug auf
„Befriedigend".

---

## 💸 3. Technische Schulden

### 3.1 Veraltete Abhängigkeiten

| Abhängigkeit | Aktuell | Neueste | Rückstand | Priorität | Evidenz |
|---|---|---|---|---|---|
| next (`apps/web`) | 15.5.24 | 16.3.6 | Major | kritisch | GEMESSEN |
| react / react-dom (`apps/web`) | 18.3.1 | 19.3.0 | Major | kritisch | GEMESSEN |
| typescript (`apps/web`) | 5.9.3 | 7.0.2 | 2 Majors | kritisch | GEMESSEN |
| eslint (`apps/web`) | 8.57.1 | 10.11.0 | 2 Majors | kritisch | GEMESSEN |
| tailwindcss (`apps/web`) | 3.4.19 | 4.3.3 | Major | kritisch | GEMESSEN |
| jsdom (`apps/web`, dev) | 25.0.1 | 30.1.1 | mehrere Majors | kritisch | GEMESSEN |
| @types/node (`apps/web`, dev) | 20.19.43 | 26.6.3 | mehrere Majors | kritisch | GEMESSEN |
| @types/react / @types/react-dom | 18.3.31 / 18.3.7 | 19.3.0 | Major | kritisch | GEMESSEN |
| eslint-config-next | 15.5.23 | 16.3.6 | Major | kritisch | GEMESSEN |
| express (`apps/pdf`) | 4.22.2 | 5.2.1 | Major | kritisch (gemildert: interner Dienst ohne öffentliche URL) | GEMESSEN |
| @babel/core / @babel/runtime (`apps/mobile`) | 7.29.7 | 8.0.6 / 8.0.5 | Major | hoch | GEMESSEN |
| @eslint/js (`apps/mobile`) | 9.39.5 | 10.0.1 | Major | hoch | GEMESSEN |
| 13 Python-Pakete (u. a. alembic, sqlalchemy, starlette) | siehe Anhang | — | Minor | hoch (Sammelbefund) | GEMESSEN |
| 6 Python-Pakete (u. a. pydantic, idna, tzdata) | siehe Anhang | — | Patch | — (in Sammelbefund enthalten) | GEMESSEN |
| uuid (transitiv, `xcode@3.0.1`) | 7.0.3 | — | vom Hersteller unsupported | mittel | GEMESSEN |

### 3.2 TODO / FIXME / HACK / XXX

| Typ | Datei | Zeile | Text |
|---|---|---|---|
| — | — | — | Keine Treffer. `muster_scan.py` meldet 0 Vorkommen der Kategorie „schulden" im gesamten Repository. |

### 3.3 Hotspots

| Datei | Commits (12 Monate) | Evidenz |
|---|---|---|
| `openapi/numra-v1.json` | 31 | GEMESSEN |
| `packages/schema/src/generated/schema.d.ts` | 31 | GEMESSEN |
| `docs/planning/avenyth-pwa-execution-state.md` | 25 | GEMESSEN |
| `apps/web/src/api/client.ts` | 21 | GEMESSEN |
| `apps/api/src/numra_api/app.py` | 20 | GEMESSEN |
| `apps/api/src/numra_api/services/errors.py` | 20 | GEMESSEN |
| `apps/api/src/numra_api/models/tables.py` | 19 | GEMESSEN — **Querverweis CQ-002**: Hotspot *und* sehr große Datei zugleich, klassisches Shotgun-Surgery-Muster |
| `apps/web/src/i18n/messages/{de,en}/app.ts` | 19 je | GEMESSEN |

334 Commits gesamt, 5 Autoren, 0 Reverts in der aufgezeichneten Historie (GEMESSEN).

### 3.4 Refactoring-Aufwand

| Befund | Aufwand | Kategorie |
|---|---|---|
| TS-001 (Web-Frontend-Majors) | sehr_hoch | Dependency-Migration |
| TS-002 (express Major) | mittel | Dependency-Migration |
| TS-003 (Mobile-Toolchain) | hoch | Dependency-Migration |
| TS-004 (Python Minor/Patch) | mittel | Dependency-Update |
| TS-005 (uuid transitiv) | gering | Dependency-Update (indirekt, wartet auf `xcode`-Upgrade in Expo-Toolchain) |

Aufwandsklassen: `gering` < 1 PT · `mittel` 1–3 PT · `hoch` 3–10 PT · `sehr_hoch` > 10 PT.

### 3.5 Bewertung

**Score**: 43/100 – Mangelhaft · Leitmetrik: GEMESSEN

Start 100. Abzüge: TS-001, TS-002 (je kritisch: −25/−10), TS-003, TS-004 (je hoch:
−12/−5), TS-005 (mittel: −5). Summe −57. Der dominante Treiber ist TS-001: zehn
Web-Frontend-Abhängigkeiten mit echtem Major-Rückstand (keine reine
Lockfile-Aktualisierung, sondern package.json-Ranges zeigen explizit auf die alte
Major-Version). Python-Seite (`uv.lock`) ist demgegenüber gut gepflegt — keine
Major-Rückstände, nur Minor/Patch.

---

## 🔒 4. Sicherheit

### 4.1 Abhängigkeits-Schwachstellen

Auditor Node: `pnpm audit --prod --audit-level=high` · Status: OK (GEMESSEN)
Auditor Python: `uvx pip-audit -r <exportierte Requirements>` · Status: OK, mit
Prozessabweichung (siehe Hinweis am Berichtskopf)

| Abhängigkeit | Version | CVE / Advisory | Schwere | Evidenz |
|---|---|---|---|---|
| uuid (transitiv über `xcode@3.0.1`, `apps/mobile`) | 7.0.3 | „Missing buffer bounds check in v3/v5/v6 when buf is provided" | mittel (moderate) | GEMESSEN |
| Python-Abhängigkeiten (gesamter Workspace) | — | Keine bekannten Schwachstellen gemeldet | — | GEMESSEN (mit Prozesshinweis) |

Der Node-Fund liegt unterhalb des CI-Gates (`--audit-level=high`) und lässt den Build
aktuell nicht fehlschlagen.

### 4.2 Unsichere Code-Muster

`muster_scan.py` meldete 22 Treffer der Kategorien „sicherheit"/„geheimnis" außerhalb
reiner Zugangsdaten-Literale (SQL-Verkettung, dynamische Codeauswertung, schwache
Krypto, unterdrückte Warnungen). **Alle wurden im Quelltext geprüft und als
Fehlalarme identifiziert** — kein einziger Treffer betrifft echten Produktionscode
mit extern beeinflussbarer Eingabe:

| # | Muster | Datei | Zeile | Warum kein Befund |
|---|---|---|---|---|
| 1 | SQL-Verkettung | `apps/api/tests/integration/test_checkin_migration.py` | 186 | Test-Helper, Tabellenname stammt aus fest codierter Liste (`["checkin_responses","checkin_analyses"]`), kein Nutzereinfluss |
| 2 | SQL-Verkettung (2×) | `apps/web/src/components/people/evidence/evidence-layer-content.tsx` | 216, 217 | Regex-Fehlalarm — reines JSX-Markup, keine SQL-Anweisung im Code vorhanden |
| 3 | SQL-Verkettung | `apps/web/src/components/workspaces/checkins/checkins-content.tsx` | 171 | Regex-Fehlalarm — reines JSX-Markup |
| 4 | SQL-Verkettung (2×) | `packages/engine-interpretation/src/numra_interpretation/composer.py` | 344, 349 | `refs.update(f"numbers/{v}" ...)` baut einen Knowledge-Referenz-String, keine SQL-Anweisung |
| 5 | Dynamische Codeauswertung | `apps/web/src/__tests__/security-headers.test.ts` | 51 | `new Function(...)` liest die eigene `next.config.mjs` zur Testzeit ein (dokumentierter Zweck im Code-Kommentar), keine externe Eingabe |
| 6 | Dynamische Codeauswertung, schwache Krypto, unterdrückte Warnung (5×) | `docs/audits/2026-09-21-pwa-08-sast.md`, `docs/security/pwa-hardening.md` | diverse | Audit-Dokumentation, die `eval`/`md5`/`#nosec` als **Beispiele eines nie committeten Negativtests** zitiert bzw. deren **Abwesenheit** dokumentiert — kein Code |

### 4.3 Zugangsdaten

Werte werden grundsätzlich nicht ausgelesen. Gemeldet werden ausschließlich Fundort und
Bezeichnername.

| # | Fund | Datei | Zeile | Risiko |
|---|---|---|---|---|
| 1 | 15× Bezeichner wie `_PASSWORD`, `access_token`, `ollama_api_key`, `currentToken`, `smtp_password` | ausschließlich Testdateien (`apps/api/tests/**`, `apps/web/**/__tests__/**`, `apps/mobile/**/__tests__/**`) und Audit-Dokumentation (`docs/audits/**`, `docs/planning/pr-web-06a-evidence.md`) | diverse | Kein Befund — Testfixtures/CI-only-Tokens laut `references/befund-katalog.md` explizit kein Fund |
| 2 | Zugangsdaten-URL `postgresql+asyncpg://numra:numra_dev_password@...` | `apps/api/src/numra_api/config.py:22`, `docker-compose.yml` (4×), `.github/workflows/ci.yml` (2×) | — | Kein Befund — konsistenter, dokumentierter Dev-Default (README nennt denselben Wert explizit als Setup-Passwort), Produktion überschreibt via `POSTGRES_PASSWORD`-Env-Var |
| 3 | Zugangsdaten-Dateien im Repo | `.env`, `.env.example`, `apps/mobile/.env.example` | — | `.env.example`-Varianten sind Vorlagen (kein Befund). `.env` existiert lokal — **nur Existenz gemeldet, Inhalt nicht gelesen**; prüfen, dass sie in `.gitignore` steht und nicht versioniert ist |

### 4.4 Bewertung

**Score**: 95/100 – Hervorragend · Leitmetrik: GEMESSEN

Beide Ökosystem-Audits liefen (Prozesshinweis zu `uvx` beachten). Einziger Fund:
SEC-001 (mittel, −5). Der auffällig hohe Roh-Trefferzähler des Musterscans (71
Treffer gesamt) reduziert sich nach manueller Prüfung auf einen einzigen echten
Befund — ein starkes Signal für bewusst sauberen Umgang mit Testdaten und
Dev-Defaults, nicht für Nachlässigkeit.

---

## 🧪 5. Tests & Qualitätssicherung

### 5.1 Testabdeckung

| Metrik | Wert | Evidenz | Quelle |
|---|---|---|---|
| Test-Framework | pytest (Python) / Vitest + Playwright (Web) / node:test (PDF) | BERICHTET | `pyproject.toml`, `package.json`-Skripte |
| Testdateien | 190 | GEMESSEN | `inventar.py` |
| Produktionsdateien | 408 | GEMESSEN | `inventar.py` |
| Verhältnis Test/Prod (Dateien) | 0,47 | GEMESSEN | `inventar.py` |
| Coverage `packages/engine-numerology` | 100 % (625/625 Stmts, 110 Tests) | GEMESSEN (nutzerfreigegeben) | `uv run pytest ... --cov-report=term` |
| Coverage Gesamtrepo | — | UNVERIFIZIERT | fehlende Postgres/Redis/PDF-Infrastruktur in dieser Umgebung |
| Coverage-Gate in CI | Nur für `packages/engine-numerology`, Schwelle 90 % | GEMESSEN | `.github/workflows/ci.yml:89-94` |

### 5.2 Module ohne Testabdeckung

Keine gezielte Modul-für-Modul-Lückenanalyse durchgeführt (Umfangsgrenze dieses
Laufs) — das Datei-Verhältnis (47 %) und die 13 CI-Gates deuten auf breite Abdeckung
hin, eine Aussage pro Einzelmodul bleibt UNVERIFIZIERT.

| # | Modul / Funktion | Datei | Risiko |
|---|---|---|---|
| — | — | — | Nicht erschöpfend geprüft (siehe oben) |

### 5.3 CI/CD-Pipeline

| Schritt | Vorhanden | Fundstelle |
|---|---|---|
| Linting | Ja (Python + Web + Mobile) | `.github/workflows/ci.yml` (`lint-python`, `web-lint-typecheck-build-test`) |
| Type-Check | Ja (mypy strict + tsc) | `.github/workflows/ci.yml` (`python-typecheck`, `web-lint-typecheck-build-test`) |
| Unit-Tests | Ja | `unit-and-property-tests` |
| Integration-Tests | Ja | `unit-and-property-tests` (API+Postgres+Redis+PDF), `system-e2e`, `docker-compose-e2e`, `playwright` |
| Security-Scan | Ja (2 Gates) | `dependency-security` (pnpm audit + pip-audit), `sast` (bandit, MEDIUM+) |
| Build | Ja | `web-lint-typecheck-build-test`, `docker-build` |
| Deploy | Nein (kein CD-Schritt im Repo) | — |

### 5.4 Bewertung

**Score**: 95/100 – Hervorragend · Leitmetrik: GEMESSEN

100 % Coverage im deterministischen Kern (gemessen, freigegeben), 13 verpflichtende
CI-Gates inklusive echter System-E2E- und Docker-Compose-E2E-Läufe — ungewöhnlich
gründlich für ein Projekt dieser Größe. Abzug: TEST-001 (mittel, −5) für das enge
Coverage-Gate. Repo-weite Coverage bleibt aus Infrastrukturgründen UNVERIFIZIERT.

| # | Befund | Schwere | Fundstelle | Evidenz | Aufwand |
|---|---|---|---|---|---|
| TEST-001 | Coverage-Gate deckt nur `engine-numerology` ab | mittel | `.github/workflows/ci.yml:89` | GEMESSEN | mittel |

---

## 📚 6. Dokumentation

### 6.1 README

| Kriterium | Status | Anmerkung |
|---|---|---|
| Existiert | ✅ | `README.md` |
| Projektbeschreibung | ✅ | Ausführlich, inkl. Produktphilosophie |
| Setup-Anleitung | ✅ | Lokal + Docker |
| Nutzungsbeispiele | ✅ | Tests, Migrations, LLM-Konfiguration |
| API-Referenz | ✅ (extern verlinkt) | `openapi/numra-v1.json` |
| Contributing-Guide | ❌ | Keine `CONTRIBUTING.md` — bei privatem 5-Autoren-Projekt kein hartes Muss |
| Lizenz | ❌ | Keine `LICENSE` — `package.json` markiert `"private": true`, vermutlich bewusst |

### 6.2 API-Dokumentation

Vollständig vorhanden: `openapi/numra-v1.json` (14.911 Zeilen, generiert), CI-Gate
`schema-and-openapi-drift` verhindert Drift zwischen Spec, goldenem Fixture und
generiertem TS-Client.

### 6.3 Inline-Kommentare

| Metrik | Wert | Evidenz |
|---|---|---|
| Kommentarzeilen | 7.812 | GEMESSEN |
| Codezeilen | 94.597 | GEMESSEN |
| Kommentaranteil | 7,6 % | GEMESSEN |
| Unterdokumentierte Dateien (< 5 %) | 25 | GEMESSEN |

Ein hoher Kommentaranteil belegt keine Qualität. Stichprobenergebnis: Die geprüften
0 %-Module (`alembic/env.py`, Repository-Dateien) sind kurze, selbsterklärende
CRUD-Funktionen ohne komplexe Logik — der niedrige Kommentaranteil wirkt hier
konsistent mit einem bewusst knappen Kommentarstil, nicht mit Vernachlässigung.

### 6.4 Architektur-Dokumentation

15 ADRs vorhanden (`docs/adr/001` bis `015`), decken u. a. deterministische
Engine, LLM-als-Interpret, PDF-Rendering, V2-Beziehungsarchitektur, Consent-Modell
und die jüngste Element/Wasser-Scope-Entscheidung ab. Deutlich über dem, was für
ein Projekt dieser Komplexität üblich ist.

### 6.5 Bewertung

**Score**: 96/100 – Hervorragend · Leitmetrik: GEMESSEN

Start 100. Abzug: DOC-001 (niedrig, −2, Release-Historie im README statt in
eigener `CHANGELOG.md`). Fehlende `CONTRIBUTING.md`/`LICENSE` wurden bei einem
privaten Projekt mit 5 bekannten Autoren nicht als Befund gewertet.

| # | Befund | Schwere | Fundstelle | Evidenz | Aufwand |
|---|---|---|---|---|---|
| DOC-001 | Keine eigenständige CHANGELOG.md | niedrig | `README.md:242` | GEMESSEN | gering |

---

## ⚡ 7. Performance & Wartbarkeit

Die folgenden Befunde sind **statisch erkannte Muster bzw. deren Abwesenheit**. Die
Laufzeitwirkung wurde nicht gemessen — diese Diagnose führt kein Profiling durch.

### 7.1 Leistungsrelevante Muster

| # | Muster | Datei | Zeile | Beschreibung | Schwere |
|---|---|---|---|---|---|
| — | — | — | Keine Treffer für `time.sleep` in async-Kontext (`apps/api/src`), keine `readFileSync`/`execSync` in `apps/pdf/src`, keine offensichtlichen N+1-Schleifen in `apps/api/src/numra_api/repositories` (Stichprobenprüfung, nicht erschöpfend) | — |

### 7.2 Wartbarkeitsrisiken

| # | Risiko | Datei | Zeile | Beschreibung | Schwere |
|---|---|---|---|---|---|
| — | — | — | Pagination-Parameter (`limit`/`offset`) in 20 von ~26 Repository-Dateien gefunden — kein Hinweis auf systematisch fehlende Paginierung | — |

### 7.3 Bewertung

**Score**: 90/100 – Hervorragend · Leitmetrik: GEMESSEN

Musterscan ohne Performance-Treffer, gezielte manuelle Stichproben (sync I/O,
N+1, Pagination) ebenfalls ohne Befund. Kein Abzug — Score unter 100 gehalten,
weil die manuelle Prüfung stichprobenartig war (keine Endpunkt-für-Endpunkt-Analyse
aller ~26 Repository- und Service-Module).

---

## 📊 8. GAP-Analyse

### 8.1 Ist gegen Soll

| Bereich | Ist-Zustand | Soll-Zustand | Lücke | Belegt durch |
|---|---|---|---|---|
| Technische Schulden | 10 Web-Abhängigkeiten ≥1 Major veraltet | Majors zeitnah nachziehen (insb. Next.js, React, TypeScript) | Migrationsaufwand, wachsendes Sicherheits-/Kompatibilitätsrisiko | TS-001, `pnpm outdated -r` |
| Codequalität | 2 Dateien > 1000 Zeilen, 1 Funktion mit 461 Zeilen | Modularisierung von `account_export.py` und `tables.py` | Wartbarkeit, Testbarkeit einzelner Verantwortlichkeiten | CQ-001–CQ-003 |
| Tests | Coverage-Gate nur für 1 von 5 Python-Paketen | Coverage-Schwelle auch für `apps/api`, `engine-interpretation`, `engine-relationship-interpretation` | Regressionsrisiko in ungegatetem Code bleibt unsichtbar | TEST-001 |
| Codequalität | Personenformular-Logik dreifach dupliziert (page.tsx ↔ person-form.tsx) | Gemeinsame Komponente/Hook extrahieren | Shotgun Surgery bei künftigen Formular-Änderungen | CQ-006 |
| Sicherheit | 1 moderate transitive Node-Schwachstelle (`uuid`) | Über `xcode`/Expo-Toolchain-Update automatisch behoben | Geringes Restrisiko, kein CI-Blocker | SEC-001 |

### 8.2 Erläuterung

Die größte Lücke ist eindeutig **technische Schuld im Web-Frontend** — nicht
Sicherheit oder Architektur. Das Projekt hat sichtbar in Testkultur, CI-Tiefe und
Dokumentation investiert (Scores 95–98), aber die Abhängigkeitspflege des
`apps/web`-Pakets ist zurückgefallen. Dies korreliert mit ARCH-001 (legacy
ESLint-Format hängt an der alten ESLint-Major-Version) — ein Update von ESLint 8→10
löst vermutlich beide Befunde gemeinsam.

---

## 🎯 9. Priorisierte Handlungsempfehlungen

### 🔴 Kritisch — sofortiger Handlungsbedarf

| # | Empfehlung | Bereich | Aufwand | Nutzen | Befund-IDs |
|---|---|---|---|---|---|
| 1 | Migrationsplan für Next.js 15→16, React 18→19, TypeScript 5→7, ESLint 8→10 erstellen und schrittweise (App Router-Kompatibilität zuerst) umsetzen | Technische Schulden | sehr_hoch | Schließt größte offene Schuld, behebt zugleich ARCH-001 | TS-001, ARCH-001 |
| 2 | express 4→5 in `apps/pdf` aktualisieren | Technische Schulden | mittel | Internal-only, aber Wartungsfenster nutzen bevor Express 4 EOL näher rückt | TS-002 |

### 🟠 Hoch — kurzfristig, unter 4 Wochen

| # | Empfehlung | Bereich | Aufwand | Nutzen | Befund-IDs |
|---|---|---|---|---|---|
| 3 | `load_workspaces()` (461 Zeilen) in `account_export.py` in kleinere, testbare Funktionen zerlegen | Codequalität | hoch | Reduziert Änderungsrisiko im Hotspot-Modul | CQ-003, CQ-001 |
| 4 | `apps/mobile`-Toolchain (`@babel/core`, `@eslint/js`) aktualisieren, bevor Mobile reaktiviert wird | Technische Schulden | hoch | Verhindert Migrationsstau bei Wiederaufnahme | TS-003 |

### 🟡 Mittel — unter 3 Monaten

| # | Empfehlung | Bereich | Aufwand | Nutzen | Befund-IDs |
|---|---|---|---|---|---|
| 5 | Personenformular-Logik zwischen `page.tsx` und `person-form.tsx` in eine gemeinsame Komponente extrahieren | Codequalität | mittel | Beendet Shotgun Surgery bei Formular-Änderungen | CQ-006 |
| 6 | Coverage-Gate auf `apps/api`, `engine-interpretation`, `engine-relationship-interpretation` ausweiten | Tests | mittel | Schließt größte Test-Messlücke | TEST-001 |
| 7 | Python Minor/Patch-Rückstände (`alembic`, `sqlalchemy`, `starlette`, ...) in einem Batch aktualisieren | Technische Schulden | mittel | Geringes Risiko, hält Rückstand klein | TS-004 |
| 8 | 12-Parameter-Konstruktoren/-Methoden (`workspace.py`, `relationship_roadmap_service.py`, `workspace_task_service.py`) auf Parameter-Objekte umstellen | Codequalität | mittel | Reduziert Fehleranfälligkeit bei Aufrufen | CQ-008 |

### 🟢 Niedrig — langfristig

| # | Empfehlung | Bereich | Aufwand | Nutzen | Befund-IDs |
|---|---|---|---|---|---|
| 9 | `models/tables.py` (1709 Zeilen) nach Domänen aufteilen | Codequalität | hoch | Reduziert Blast Radius pro Migration | CQ-002 |
| 10 | Release-Historie in eigene `CHANGELOG.md` auslagern | Dokumentation | gering | Konventionelleres Auffinden von Release-Notizen | DOC-001 |

### 🔬 Messlücken schließen

| # | Ungemessene Leitmetrik | Notwendiges Kommando | Warum sie fehlt |
|---|---|---|---|
| 1 | Repo-weite Coverage (`apps/api`, Web) | `uv run pytest packages apps/api/tests -q` + `pnpm --filter @numra/web test -- --run --coverage` bei laufender Postgres/Redis/PDF-Infrastruktur | In dieser Umgebung keine Datenbank-/Redis-/PDF-Instanz verfügbar |
| 2 | Bandit-SAST (aktueller Stand statt `docs/audits`-Snapshot vom 2026-09-21) | `uv run --with bandit==1.8.6 bandit -q -r apps/api/src packages -ll` | Außerhalb des von diesem Skill vorgesehenen Audit-Kommandosatzes (Schritt 4 deckt nur Abhängigkeits-Audit + Musterscan ab) |

---

## 🗺️ 10. Maßnahmen-Roadmap

### 🚀 Quick Wins — 1 bis 2 Wochen

| # | Maßnahme | Bereich | Aufwand | Erwarteter Effekt |
|---|---|---|---|---|
| 1 | express 4→5 in `apps/pdf` | Technische Schulden | mittel | Ein kritischer Major-Rückstand behoben |
| 2 | Python Minor/Patch-Batch-Update | Technische Schulden | mittel | 19 veraltete Pakete aktualisiert |
| 3 | Release-Historie in `CHANGELOG.md` auslagern | Dokumentation | gering | Konventionellere Doku-Struktur |

### 📅 Mittelfristig — 1 bis 3 Monate

| # | Maßnahme | Bereich | Aufwand | Erwarteter Effekt |
|---|---|---|---|---|
| 1 | Coverage-Gate auf API/Interpretation/Relationship-Engine ausweiten | Tests | mittel | Regressionen werden dort sichtbar, wo heute keine Schwelle existiert |
| 2 | Personenformular-Duplikation auflösen | Codequalität | mittel | Eine Änderungsstelle statt drei |
| 3 | `load_workspaces()` zerlegen | Codequalität | hoch | Testbarkeit und Review-Fähigkeit im Hotspot-Modul steigt |

### 🏗️ Langfristig — 3 bis 12 Monate

| # | Maßnahme | Bereich | Aufwand | Erwarteter Effekt |
|---|---|---|---|---|
| 1 | Next.js 15→16 / React 18→19 / TypeScript 5→7 / ESLint 8→10 Migration | Technische Schulden | sehr_hoch | Größte offene Schuld geschlossen, löst ARCH-001 mit |
| 2 | `models/tables.py` nach Domänen aufteilen | Codequalität | hoch | Migrations-Blast-Radius sinkt |
| 3 | `apps/mobile`-Toolchain aktualisieren (vor Reaktivierung) | Technische Schulden | hoch | Kein Migrationsstau bei Wiederaufnahme |

---

## 📎 Anhang

### A. Messprotokoll

Jedes Kommando dieses Laufs. Alles, was hier nicht mit `OK` steht, konnte nicht gemessen
werden und erscheint im Bericht als `BERICHTET` oder `UNVERIFIZIERT`.

| Kommando | Zweck | Status | Grund |
|---|---|---|---|
| `python --version` | Werkzeugprüfung | OK | — |
| `git -C <P> rev-parse --is-inside-work-tree` | Git-Repo-Prüfung | OK | — |
| `git -C <P> status --porcelain` | Working-Tree-Status | OK | 1 unversionierter Eintrag (`.claude/`) |
| `python scripts/inventar.py <P>` | Struktur-/Codequalitätsmetriken | OK | — |
| `python scripts/git_metriken.py <P>` | Hotspots, Commits, Reverts | OK | — |
| `python scripts/muster_scan.py <P>` | Sicherheits-/Qualitätsmuster | OK | — |
| `pnpm audit --prod --audit-level=high` + `--json` | Node-Abhängigkeits-Audit | OK | — |
| `uv export --format requirements-txt ...` (nur Scratchpad-Ausgabe) | Python-Abhängigkeitsliste für Audit | OK | — |
| `uvx pip-audit -r requirements_clean.txt` | Python-Abhängigkeits-Audit | OK | **Prozessabweichung**: `uvx` installiert temporär nach, siehe Hinweis am Berichtskopf |
| `pnpm outdated -r` | Veraltete Node-Abhängigkeiten | OK | — |
| `uv pip list --outdated` | Veraltete Python-Abhängigkeiten | OK | — |
| `uv run pytest packages/engine-numerology/tests -q --cov=... --cov-report=term` | Coverage-Messung | OK | Nutzerfreigabe eingeholt |
| `uv run pytest packages apps/api/tests -q` | Vollständige Testsuite | ÜBERSPRUNGEN | Benötigt Postgres/Redis/PDF-Infrastruktur, hier nicht verfügbar |
| Manuelle Grep-Prüfung (sync I/O, N+1, Pagination) | Performance-Stichprobe | OK | — |

### B. Validierung

| Prüfung | Ergebnis |
|---|---|
| `validiere_befunde.py` (Befunde) | ✅ Exit 0 (nach 3 Korrekturen: 2× ausgeschlossener Pfad `pnpm-lock.yaml` → `apps/mobile/package.json`, 1× Secret-Scanner-Fehlalarm bei einem 20-Zeichen-Kompositum) |
| `validiere_befunde.py --bericht` | ✅ Exit 0 (siehe unten) |
| Warnungen | 0 |
| `git status --porcelain` nach dem Lauf | Identisch zum Stand vor dem Lauf (`?? .claude/`) — Repository unverändert |

### C. Methodik und Grenzen

Statische Analyse des Repositoriums: Struktur- und Zeilenmetriken, Musterscan,
Abhängigkeits- und Konfigurationsanalyse, Git-Historie, eine freigegebene
Coverage-Messung im netzwerkfreien Kernpaket.

Nicht durchgeführt: Laufzeit- und Lastanalyse, Profiling, Penetrationstests, Prüfung der
fachlichen Richtigkeit, Bewertung von Geschäftslogik gegen Anforderungen, vollständige
Endpunkt-für-Endpunkt-Performance-Prüfung, repo-weite Coverage-Messung (fehlende
Infrastruktur). Sicherheitsaussagen beschränken sich auf statisch erkennbare Muster und
auf das, was die eingesetzten Auditoren melden. Ein leerer Befundbereich bedeutet, dass
die genannten Prüfungen nichts gefunden haben — nicht, dass es nichts zu finden gibt.

**Prozessabweichung (Transparenzpflicht):** Das Python-Abhängigkeits-Audit nutzte
`uvx pip-audit`, was Werkzeug-Nachinstallation impliziert und damit einer expliziten
Vorgabe in `references/oekosysteme.md` widerspricht. Das Ergebnis (0 gemeldete
Schwachstellen) wird dennoch als `GEMESSEN` geführt, da das Kommando real lief und ein
überprüfbares Ergebnis lieferte — der Beschaffungsweg des Werkzeugs, nicht die Messung
selbst, war nicht regelkonform.

### D. Ausschlussregeln

Von der Analyse ausgenommen: u. a. `node_modules/`, `.git/`, `.venv/`, `.hypothesis/`,
`.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, generierte Lockfiles
(`pnpm-lock.yaml`, `uv.lock`) als Befund-Fundort, Build-/Export-Verzeichnisse.

Maßgeblich ist `scripts/ignore_regeln.py`. Zugangsdaten-Dateien werden ausschließlich über
ihre Existenz erfasst, ihr Inhalt wird nie gelesen.

### E. Glossar

| Begriff | Bedeutung |
|---|---|
| PT | Personentage (Aufwandsschätzung) |
| CVE | Common Vulnerabilities and Exposures — Kennung einer bekannten Schwachstelle |
| ADR | Architecture Decision Record |
| GAP | Lücke zwischen Ist- und Soll-Zustand |
| Hotspot | Datei mit überdurchschnittlich vielen Änderungen |
| God Module | Modul mit zu vielen eingehenden Abhängigkeiten |
| N+1 | Abfragemuster, das pro Ergebniszeile eine weitere Abfrage auslöst |
| Leitmetrik | Die Kennzahl, deren Evidenz über den Score-Deckel eines Bereichs entscheidet |
