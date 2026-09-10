# AVENYTH V2 — Check-in Spec

## Status

Frozen product decision (#8 in the decision log) — deviates from the recommended
default of a fixed five-dimension set. Check-in dimensions are **configurable**,
not hardcoded.

## Template model

```
CheckinTemplate
  id, workspace_id, version, created_at, active

CheckinDimension
  id, workspace_id, semantic_key, label, description,
  scale_min, scale_max, sort_order, active,
  created_at, retired_at (nullable)
```

Each `RelationshipWorkspace` gets its own `CheckinTemplate`, versioned. The default
template (version 1) ships with:

```
closeness
communication
understanding
autonomy
conflict_load
```

Scale: `1..10` for every dimension unless a dimension defines otherwise.

## Configuration rules

- Users may activate/deactivate a dimension, add a custom dimension, or change a
  dimension's `label`/`description`.
- A dimension's `semantic_key`, once used in any submitted `CheckinResponse`, is
  **never redefined retroactively** — changing its meaning requires retiring it
  (`retired_at`) and introducing a new `semantic_key`.
- Every historical response stays bound to the `checkin_template_version` active
  when it was submitted. Aggregation/trend logic must group by
  `(semantic_key, checkin_template_version)`, never blindly average across template
  versions with different meanings.
- Example additional dimensions: `trust`, `emotional_safety`, `quality_time`,
  `support`, `sexual_connection`.
- `sexual_connection` (and any dimension of that class) is **never available** in
  `PARENT_CHILD`, `SIBLINGS`, `WORK` relationship types, or in any workspace/context
  involving a managed minor profile — enforced server-side at dimension-activation
  time, not just hidden in the UI.

## Privacy (Section 19 — frozen)

Each participant submits separately. Raw answers are `SUBMITTER_ONLY` — a partner
can never read the other's raw numeric answers, at any point, through any endpoint.

Only after **both** participants have submitted for a given check-in cycle does
`CheckinAnalysisService` compute the shared derived result. Partners see only the
derived shared analysis, never raw values.

**Accepted trade-off:** `absolute_gap` is a difference of two raw values. A viewer
who already knows their own submitted value can trivially derive the two candidate
values for their partner's answer (`own_value ± absolute_gap`) — usually resolvable
to one, given the fixed scale. This is an inherent property of exposing *any*
two-party gap metric, not an implementation flaw; PR-V2-06's review confirmed no
other field (raw values, partial nulls, error messages) leaks the partner's answer.
Documented here so it is never mistaken for a closed gap in a later audit.

## Deterministic analysis (Section 20)

The LLM computes **none** of: gap, trend, mean, delta, sample size. A backend
service computes:

```
absolute_gap
direction
rolling_trend
sample_size
historical_delta
sufficient_evidence
```

as a `CheckinAnalysis` JSON document. The LLM only explains that already-computed
JSON — never recomputes or overrides it (same invariant as
`specs/v2/evidence-policy.md`).

## Acceptance checks

- A dimension's `semantic_key` is provably immutable once any response references
  it (migration/constraint-level, not just app-level convention).
- Neither participant's API responses ever include the other's raw
  `CheckinResponse` values, under any scope or role.
- `CheckinAnalysis` is only computable after both participants have submitted for
  the cycle; a request before that returns "awaiting partner", never partial raw
  data.
- Trend calculations correctly segment by `checkin_template_version` when a
  workspace has evolved its template over time.

## WEB-06a — verbindliche Contract-Präzisierung (2026-09-10)

Diese Regeln ersetzen die implizite Runden-Eröffnung aus PR-V2-06. Die Analyse bleibt
synchron, deterministisch und nach `(semantic_key, checkin_template_version)` segmentiert.
Kein LLM, Worker, Consent-Scope oder zusätzlicher Score wird eingeführt.

- `POST /v1/workspaces/{id}/checkins/rounds` eröffnet eine Runde ausdrücklich.
  Pflichtheader `Idempotency-Key` (1–200 Zeichen), kein Request-Body. Response 201
  `CheckinRoundOut` mit vollständigem Snapshot. Offene Runde: 409 `CHECKIN_ROUND_OPEN`;
  leere aktive Dimensionsmenge: 422 `CHECKIN_NO_ACTIVE_DIMENSIONS`.
- `POST /v1/workspaces/{id}/checkins` verlangt `round_id`, denselben Pflichtheader und
  genau eine Antwort je Snapshot-Dimension. Werte sind echte Integer (keine Booleans,
  keine String-Konvertierung). Unbekannte Felder (auch pro Antwort) sowie Start-Parameter
  werden mit 422 abgelehnt, nicht still ignoriert. Es entsteht niemals implizit eine Runde.
- Idempotenz-Identität: `(user_id, workspace_id, operation, key)`. Separater SHA-256
  über kanonisches JSON aus `round_id` und nach Dimensions-ID sortierten Antworten.
  Reihenfolge der Antworten ist irrelevant. Anderer Payload mit demselben Key:
  409 `CHECKIN_IDEMPOTENCY_CONFLICT`. Hash und fachliche Mutation werden atomar
  committed. Es gibt keinen persistierten Cache privater HTTP-Responses.
- Replay vor/nach Abschluss: 201 mit derselben Runden-ID und dem **aktuellen**,
  erneut autorisierten Zustand (eine inzwischen vorhandene Analyse kann hinzukommen).
  Ein Start-Replay eröffnet auch nach Abschluss keine neue Runde. Ein Submit mit
  anderem Key nach eigener Abgabe: 409 `CHECKIN_ALREADY_SUBMITTED`, auch nach Abschluss.
  Unbekannte/fremde oder sonst nicht abgebbare Runde: 409 `CHECKIN_ROUND_MISMATCH`.
- Fehlende/doppelte/zusätzliche/fremde Dimensions-IDs: einheitlich 422
  `CHECKIN_RESPONSES_INCOMPLETE` ohne Existenzhinweise fremder Dimensionen.
  Außerhalb der Snapshot-Skala: 422 `CHECKIN_VALUE_OUT_OF_RANGE` mit erlaubtem Bereich,
  ohne eingereichten Wert. Konfiguration muss `0 <= scale_min < scale_max <= 100`
  erfüllen (`CHECKIN_SCALE_INVALID` bzw. Schemafehler). Schemafehler enthalten
  `CHECKIN_REQUEST_INVALID`, nur Fehlerort/-typ, keine `input`-/`ctx`-Daten.
- `GET /checkins/current` liefert die offene, sonst die neueste abgeschlossene
  Runde. Ohne Runde: **200 mit JSON `null`**. Statische Route steht vor `/{checkin_id}`.
  Einzel-/Current-Response enthält nur `my_responses` des Aufrufers und ein
  `partner_submitted`-Bool. Die sechs Analysefelder bleiben unverändert.
- Snapshot: `dimension_id`, `semantic_key`, `label`, `description`, `scale_min`,
  `scale_max`, `sort_order`; die Version steht auf der Runde. `snapshot_origin`:
  `ROUND_START`, `MIGRATION_CURRENT` oder `LEGACY_MISSING`.
  `snapshot_recorded` bedeutet nur, dass Daten gespeichert sind; ausschließlich
  `ROUND_START` belegt den ursprünglichen Rundenstart. `MIGRATION_CURRENT` beweist
  keine früher gesehenen Texte. `LEGACY_MISSING` hat eine leere Dimensionsliste.
- `GET /checkin-template?version=N` liest eine historische Version; ohne Parameter
  die aktive. Nicht vorhandene Version: 404. Lazy-Erstellung ist nur im ACTIVE-
  Workspace möglich; DISSOLVED ohne gespeichertes Template liefert 404 ohne Mutation.
- Jede offene Runde sperrt Config-Änderungen und tatsächliche Typwechsel mit 409
  `CHECKIN_ROUND_OPEN`. PATCH auf den bereits vorhandenen Typ ist ein No-op. Dissolve
  bleibt erlaubt. Jede Config-Änderung nach Nutzung einer Version erzeugt eine Kopie
  aller Dimensionen in Version N+1. Erste Runde friert die Version ein; die Config-
  Sperre verhindert Änderungen schon vor einer ersten Antwort. Unbenutzte Versionen
  werden weiter in-place bearbeitet. Automatisches Retiren beim Typwechsel benutzt
  dieselbe Versionierung. Alte Dimensions-IDs bei PATCH adressieren über den
  unveränderten `semantic_key` dessen aktuelle Versionskopie.
- Bekannter Key `sexual_connection` wird zwingend `INTIMATE`, auch bei explizitem
  `null`. Andere Custom-Keys können als `INTIMATE` markiert werden. Die Klasse ist
  für PARENT_CHILD/SIBLINGS/WORK bei Erstellung und Reaktivierung gesperrt und wird
  beim Typwechsel deaktiviert. Frei formulierter, unklassifizierter Text wird nicht
  semantisch erkannt; keine Keyword-Heuristik. Managed-Minor-Profile können gemäß
  Minor-Spec strukturell keine Mitglieder dieses Zwei-Konten-Workspace sein.
- Mutationen prüfen Mitgliedschaft, sperren den Workspace, laden seinen Zustand
  frisch und prüfen die Mitgliedschaft erneut. Lock bis Commit vor Response.
  Reihenfolge: Connection (nur Dissolve) → Workspace → Check-in-Daten. Check-in-
  und Typwechselpfade erwerben keinen Connection-Lock. Bestehendes Dissolve-UPDATE
  serialisiert auf derselben Workspace-Zeile. Keine Zwischen-Commits, keine
  pauschalen IntegrityError-Retries.
- Nach DISSOLVED sind Config, Start, Submit **und POST-Replays** mit 409 gesperrt.
  Nicht-Mitglieder erhalten zuerst 404. Historische GETs bleiben für berechtigte
  Mitglieder lesbar; eigene Rohwerte und geteilte vorhandene Analyse bleiben getrennt.

Migration/Recovery und Nachweise: `docs/planning/pr-web-06a-evidence.md`.
