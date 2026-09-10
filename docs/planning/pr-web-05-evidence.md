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

## Offene Einschränkung — BEHOBEN (PR #50, `main` @ `1c7075d`)

Die **Shadow-Dynamics-Generierung** schlug mit
`UNEXPECTED_ERROR: No shadow interaction rule found for theme` fehl, wenn
ein Profil eine **Meisterzahl-Lebenszahl (11 / 22 / 33)** hatte — und
zusätzlich (gleicher Mechanismus, ASCII/Umlaut-Mismatch in `rules.yaml`)
für **jedes Life-Path-4/6/7-Profil**.

Behoben in **PR #50** (`fix: Shadow Dynamics bricht bei Meisterzahl-
Lebenszahlen`), Merge `1c7075d`, Post-Merge-`main`-CI Run `34485925733`
alle 12 grün:

- `knowledge/shadow-interaction/rules.yaml`: Umlaut-Angleich der 3
  Theme-Keys + **33 neue Meisterzahl-Zeilen** (78 Regeln = C(12,2)+12 über
  Life Path {1–9, 11, 22, 33}), abgeleitet aus den kuratierten
  `knowledge/master-numbers/*.yaml`-Themen (keine Reduktion auf 2/4/6,
  keine Sammelregel), grammatisch eingebettete Templates für die
  22er-Nominalphrase, ganze Datei auf echte Umlaute normalisiert.
  `manifest.yaml` `0.1.0` → `0.2.0`.
- `context.py`: neue `ShadowInteractionRuleMissing(AnalysisGenerationError)`
  statt nacktem `ValueError` → Service klassifiziert als terminales
  `ANALYSIS_GENERATION_ERROR` (`retryable=False`) + `logger.warning`.
- `repositories/workspaces.py`: `list_workspace_members` deterministisch
  geordnet (`joined_at, id`) — stabilisiert die A/B-Zuordnung.
- Regressionstest (RED→GREEN, gegengeprüft): Completeness-Check über alle
  78 Paare gegen die echten Knowledge-Dateien; `primary_shadow_theme`
  LP 11/22/33; Master-Paar + LP-6-Umlaut-Paar lösen auf; A/B-Swap;
  Backend-E2E `COMPLETE` für LP **11** (`1960-01-03`) / **22**
  (`1986-07-18`) / **33** (`1960-04-22`); FAILED-Pfad via monkeypatch.
- RC2-Zweikonten-Journey: Shadow-Dynamik erreicht jetzt **COMPLETE auf
  Desktop UND Mobile** gegen den echten Worker (Master-22-Fixture); die
  frühere „COMPLETE oder FAILED"-Toleranz ist entfernt. 2 passed
  (desktop 50s / mobile 48s).

Unabhängiger Review: GO-MIT-AUFLAGEN → H1 (22er-Grammatik) + M1
(Encoding-Konsistenz) + L1/L2 vor Merge behoben und re-verifiziert
(66 Tests grün, ruff clean).

## Nächster Schritt (Segment C)

Laut `specs/v2/api-contract.md` §53: **PR-V2-06 — Configurable
Check-ins** (`GET/POST /v1/workspaces/{id}/checkins`, `checkinDimensions`,
`checkinTemplate` — Client-Methoden bereits typisiert). Nicht Teil dieses
Auftrags.
