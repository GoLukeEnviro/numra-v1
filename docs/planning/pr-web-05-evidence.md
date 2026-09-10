# PR-WEB-05 — Nachweise & Abschluss

**Merge:** PR #48 → `main` @ `969898b` · **Post-Merge-`main`-CI:** Run
`34476331782` — alle 12 Required Checks grün (1. Lauf).
Plan: `docs/planning/pr-web-05-plan.md`.

## Was jetzt zusätzlich funktioniert

Der Relationship Workspace hat eine neue Unterseite
`/workspaces/[id]/dynamics` (Nav-Tab „Dynamiken", plus Hub-Karte statt
`ComingSoonState`-Stub):

- **Relationship Analysis** je Frame-Dimension eine Aussage mit
  aufklappbarer Provenance (Kanonische Werte / Wissenseinträge /
  Workspace-Belege — leere Gruppen sichtbar), lokalisierte
  Dimensions-Labels, Versions-Footer.
- **Shadow Dynamics** alle 7 Result-Felder, neutrale Labels „Person A" /
  „Person B", `pattern_intensity` als Text-Label (nie Zahl/Balken),
  `recommended_micro_tasks` als Liste mit Herkunftshinweis.
- Start je Abschnitt (`POST`, per-Versuch-`Idempotency-Key`, CSRF),
  Job-Polling (`GET /v1/analysis-jobs/{id}`), Progress-/FAILED-Zustände
  (`error_code` verbatim + Retry), ruhige `PhaseDisabledState` für
  `CONSENT_NOT_GRANTED` / `RELATIONSHIP_TYPE_NOT_SET` /
  `SELF_PROFILE_REQUIRED` / `KNOWLEDGE_FRAME_NOT_AVAILABLE` /
  `WORKSPACE_DISSOLVED`.

Kein Backend-/OpenAPI-/TS-Generat-/Alembic-Change. Kein
Compatibility-Score, keine Diagnose-Sprache, nichts ohne Provenance.
Feature-Flags default-off.

## Verifikation

| Prüfung | Ergebnis |
|---|---|
| `pnpm lint` / `typecheck` / `build` | PASS |
| `pnpm test` (Vitest) | **244 passed** (Baseline 194 + 50 neu): Polling-Hook mit Fake-Timers (9 Fälle inkl. Idempotency-Key-Verhalten bei Netzwerk- vs. Phasen-Fehler, `reload()`-Race), Narrowing-Guards, Views (Provenance inkl. leerer Arrays, kein Score, kein `role="progressbar"` im Shadow-Inhalt), Page, nav-tabs, states |
| `pr-web-05-visual-baseline` (gemockt, kuratierte Fixtures `src/fixtures/analysis/`) | **16 passed** — 8 Szenarien (empty · pending · relationship-complete · shadow-complete · failed · CONSENT_NOT_GRANTED · RELATIONSHIP_TYPE_NOT_SET · DISSOLVED) × Desktop 1440×900 + Mobile 390×844. Visuell geprüft: markenkonform, korrekte ruhige Gate-States, Provenance-Disclosure, Versions-Footer. |
| RC2-Zweikonten-Journey (echter Stack) | **2 passed** (desktop 58s / mobile 34s). Desktop-Abschnitt startet **beide** Analysen gegen den echten `analysis-worker` und asserted die reale End-to-End-Kette: Relationship → Erfolgspfad (Provenance-Disclosure aufgeklappt, Versions-Footer); Shadow → terminaler Zustand (COMPLETE mit Person-A/B-Blöcken **oder** FAILED mit `error_code` verbatim + Retry); Kontext B liest dieselben Zeilen read-only ohne Fehler. |
| Unabhängiger Review (`feature-dev:code-reviewer`) | **GO-MIT-AUFLAGEN** → Sicherheit/Leak/Spec sauber (kein Score, neutrale Labels, keine ungefilterte `result`-Ausgabe, korrekte Gate-States). 2 MEDIUM (Idempotency-Key-Verwerfen bei `create`-Fehler → Doppel-Job-Risiko; geteilter `cancelledRef` → `reload()`-Race) behoben + Regressionstests. |

**Hinweis Mock-Provider:** Bei `NUMRA_LLM_PROVIDER=mock` gibt die
Relationship-Pipeline den rohen Grounding-Text als „Prosa" aus. Der
RC2-Real-Stack-Lauf ist daher ein **struktureller Smoke** (Sektionen,
Provenance-Disclosure, Footer, terminale Zustandsbehandlung), **kein**
Prosa-/Layout-Nachweis — dafür dient die kuratierte Visual-Baseline.

## Offene Einschränkung (Backend, nicht WEB-05 — Follow-up)

Die **Shadow-Dynamics-Generierung** schlägt mit
`UNEXPECTED_ERROR: No shadow interaction rule found for theme` fehl, wenn
ein Profil eine **Meisterzahl-Lebenszahl (11 / 22 / 33)** hat.
`knowledge/shadow-interaction/rules.yaml` deckt laut eigenem
Datei-Kommentar nur Life Path 1–9 ab; `context.py::_primary_shadow_theme`
liefert für eine Meisterzahl ein Thema, das nicht in der Tabelle steht.

- **WEB-05-Frontend ist korrekt:** zeigt die `AnalysisFailedView` mit dem
  `error_code` verbatim + „Neue Analyse starten".
- **Fix gehört in einen eigenen PR:** Shadow-Interaction-Rules für
  Meisterzahlen ergänzen oder die Pipeline auf ein `INSUFFICIENT_EVIDENCE`-
  bzw. Fallback-Framing degradieren lassen statt `UNEXPECTED_ERROR` zu
  werfen. Betrifft `packages/engine-relationship-interpretation`
  (`pipeline.py`, `context.py`) + `knowledge/shadow-interaction/`.

## Nächster Schritt (Segment C)

Laut `specs/v2/api-contract.md` §53: **PR-V2-06 — Configurable
Check-ins** (`GET/POST /v1/workspaces/{id}/checkins`, `checkinDimensions`,
`checkinTemplate` — Client-Methoden bereits typisiert). Nicht Teil dieses
Auftrags.
