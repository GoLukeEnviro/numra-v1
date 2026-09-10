# PR-WEB-06 — Configurable Check-ins (Plan)

Basis `main` @ `b2c0c9e`. Web-Anteil von `PR-V2-06` (`specs/v2/api-contract.md`
§53) — **nicht** deckungsgleich mit der gemergten Backend-Phase (`9b42ce9`, #26).

**Status: PLAN — keine Feature-Implementierung, kein Merge vor Freigabe.**
Aufteilung: **PR-WEB-06a** (Backend-Fix-Paket, zuerst) → **PR-WEB-06b**
(Frontend, danach). Diese Fassung integriert die Freigabe-Vorgaben; die
früheren offenen Entscheidungen D1–D5 sind entschieden (§6).

Maßgebliche Contracts: `specs/v2/checkin-spec.md` (Frozen Decision #8),
`specs/v2/privacy-spec.md` §49, `specs/v2/dissolution-policy.md` (#11),
`specs/v2/minor-profile-policy.md`, `specs/v2/evidence-policy.md`.

---

## Verbindliche Präzisierungen aus der WEB-06a-Übergabe

Die folgenden Festlegungen ersetzen abweichende Empfehlungen/IST-Angaben weiter unten:

1. Eigene Idempotenz-Tabelle mit Schlüssel `(Akteur, Workspace, Operation, Key)`;
   kanonischer Payload-Hash wird separat verglichen. Start **und** Submit benötigen
   den Header. Replay liefert den aktuellen autorisierten Zustand derselben Runde,
   auch nach Abschluss. Nach Dissolve werden sämtliche POST-Replays abgewiesen.
2. Workspace-Row-Lock, frisch geladener Zustand und erneute Mitgliedschaftsprüfung
   nach Lock-Wartezeit. Er deckt Start, Submit, Config/Versionierung und Typwechsel
   ab; Dissolve serialisiert durch sein bestehendes Workspace-UPDATE. Kein breiter
   IntegrityError-Catch und kein Rollback mit blindem Retry.
3. Tatsächlicher Typwechsel bei offener Runde: `CHECKIN_ROUND_OPEN`; gleicher Typ:
   No-op. Automatisches Retiren nach Abschluss verwendet ebenfalls Versionskopien.
4. Template-Version ist ab erster Runden-Nutzung eingefroren. Config-Sperre deckt
   schon den Zeitraum ohne erste Antwort ab. Unique-Key umfasst Workspace, Version
   und semantic_key; Versionskopien erhalten neue IDs. PATCH alter IDs adressiert
   dieselbe fachliche Identität in der aktuellen Version.
5. Altrunden: `ANALYZED` behält Analyse/Antworten unverändert, ohne erfundene
   Snapshots. `AWAITING` wird vorab auf vollständige, passende Abgaben geprüft.
   Kompatible Backfills tragen ausdrücklich `MIGRATION_CURRENT`, niemals
   `ROUND_START`. `snapshot_recorded=true` allein beweist keinen Original-Snapshot.
   Inkompatible Altrunden führen zum atomaren Abbruch; kein stilles Reparieren.
6. `/current` ohne Runde: 200/JSON null. Historisches Template `?version=N` und
   bestehende Runden bleiben lesbar. DISSOLVED ohne Template: 404, ohne Lazy-Write.
7. Fehlerantworten spiegeln keine eingereichten Rohwerte; Schemafehler werden für
   Check-in-Routen reduziert. Die Analyse-Privacy bleibt beim akzeptierten Trade-off.

Vollständiger finaler API-Contract: `specs/v2/checkin-spec.md`, Abschnitt WEB-06a.
Migration und Prüfprotokoll: `docs/planning/pr-web-06a-evidence.md`.

---

## 1. Vorhandener Backend-Contract (IST, `9b42ce9`)

Router `/v1/workspaces/{id}`, Flag `require_v2_phase("checkins")`
(`avenyth_v2_enabled` + `avenyth_checkins_enabled`). **Kein Consent-Scope,
kein Entitlement-Gate, kein Rate-Limit.** Nicht-Member → 404.

| # | Endpunkt | Body ein | Body aus |
|---|---|---|---|
| 1 | `GET /checkin-template` | — | `CheckinTemplateOut{id, version, active, dimensions[]}` — **alle** inkl. retired |
| 2 | `POST /checkin-dimensions` (CSRF, 201) | `{semantic_key ^[a-z][a-z0-9_]*$, label, description?, scale_min=1, scale_max=10, sort_order=0}` | `CheckinDimensionOut` |
| 3 | `PATCH /checkin-dimensions/{id}` (CSRF) | `{label?, description?, active?}` | `CheckinDimensionOut` |
| 4 | `POST /checkins` (CSRF, 201) | `{responses:[{dimension_id, value:int}]}` — **kein round_id, kein Idempotency-Key** | `CheckinOut{id, checkin_template_version, status, cycle_started_at, my_responses[], analysis?}` |
| 5 | `GET /checkins/{id}` | — | `CheckinOut` |
| 6 | `GET /checkins?limit&offset` | — | `CheckinSummaryOut[]{id, checkin_template_version, status, cycle_started_at}` — **kein `analysis`** |

`CheckinStatus`: `AWAITING_SUBMISSIONS` / `ANALYZED`.
`DimensionAnalysisOut` je `semantic_key`: `absolute_gap:int`,
`direction: NO_PRIOR_DATA|CONVERGING|DIVERGING|STABLE`, `rolling_trend:float`,
`sample_size:int`, `historical_delta:float?`, `sufficient_evidence:bool`
(`= sample_size >= 3`). **`direction` ist zeitlich** (aktueller vs. voriger
Gap) — legt das Vorzeichen von `a−b` nicht offen.

Fehler: `CHECKIN_ALREADY_SUBMITTED` 409, `SEMANTIC_KEY_IMMUTABLE` 409,
`DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE` 422, `WORKSPACE_DISSOLVED` 409
(**nur Submit**), 404.

Runden-Modell IST: höchstens eine `AWAITING_SUBMISSIONS`-Runde je Workspace
(partieller Unique-Index). Submit ohne offene Runde → Server **eröffnet
implizit** eine. `create/update_dimension` mutieren die (einzige) Template-
Version **in-place**. Analyse **synchron beim zweiten Submit** (kein Worker).

---

## 2. Antworten auf die 7 Pflichtfragen (Contract-IST)

| Frage | Antwort |
|---|---|
| A/B-Zuordnung derselben Runde | 0 oder 1 offene Runde je Workspace; beide Submits landen auf derselben. **Kein `round_id` im Request** → Zuordnung rein serverseitig-implizit. |
| Template-Version einer laufenden Runde | Als Integer bei Runden-Start eingefroren (`RelationshipCheckin.checkin_template_version`). Praktisch existiert nur Version 1. |
| Template-Änderung zwischen beiden Abgaben | `create/update_dimension` mutieren **in-place**, keine neue Version. Submit lädt `active_only=True` **je Submit frisch** → A und B können **unterschiedliche Fragen** bekommen; eine nur von A beantwortete, dann deaktivierte Dimension wird bei der Analyse **still verworfen**. **Contract-Lücke.** |
| Editierbarkeit / Doppel-Submit | Antworten append-only, nicht editierbar. 2. Submit desselben Users in derselben Runde → 409. 2. Submit **nach `ANALYZED`** → **eröffnet sofort eine neue Runde**. **Contract-Lücke.** |
| Wer darf Dimensionen/Templates ändern | Jeder ACTIVE-Member einzeln. Kein Consent, keine Rolle, **kein DISSOLVED-Check**, **kein Lock während offener Runde**. **Contract-Lücke.** |
| Was sieht jede Person vor / nach beidseitiger Abgabe | Vor: nur `my_responses` (eigene Rohwerte), `analysis: null`, **kein** Partner-Feld (auch nicht als Null-Platzhalter). Nach: `analysis.result[semantic_key]` = die 6 abgeleiteten Felder, nie Roh-Partnerwerte. |
| Was darf im geteilten Analyse-Response stehen | Exakt die 6 `DimensionAnalysisOut`-Felder je Dimension. |

### Privacy — kein Widerspruch, keine Contract-Änderung

`partner ∈ {own+gap, own−gap}` ist in `checkin-spec.md:61-67` **ausdrücklich
als akzeptierter Trade-off** dokumentiert; `direction` ist zeitlich und
verrät das Vorzeichen nicht; der exhaustive Feldcheck bestätigt: kein
weiteres Feld / keine Fehlermeldung leakt einen Roh-Partnerwert. **→ keine
neue Produktentscheidung am Contract.** UX-Auflage: die 06b-Ergebnisansicht
**verspricht keine vollständige Geheimhaltung** der Partnerwerte
(zurückhaltende Formulierung, kein „nur ihr beide seht das").

**Datenschutz-Prüfmethode (verbindlich, statt DOM-Ziffernsuche):** Tests
prüfen die **Response-Felder und ihre Herkunft**, nicht ob eine bestimmte
Zahl irgendwo vorkommt (dieselbe Zahl kann legitim `absolute_gap` oder der
**eigene** Wert sein). Konkret:
- Whitelist-Assertion: `set(analysis.result[key].keys())` == exakt die 6
  erlaubten Feldnamen — für **jede** Dimension, in jedem Rollen-/Scope-Fall.
- Response-Schema-Assertion: kein Feld, dessen Name/Position einen
  Partner-Rohwert bezeichnet (auch nicht `null`), auf **keiner** Ebene von
  `CheckinOut` / `CheckinSummaryOut` / dem neuen `GET /checkins/current`.
- Herkunfts-Assertion: jeder Wert in `my_responses` stammt aus einer
  `CheckinResponse` **mit `user_id == caller`** (Query-Ebene geprüft).
- Fehlerpfade: 404/409/422-Bodies enthalten Dimension-`label`/`semantic_key`
  und ids, aber **keinen** eingereichten `value` (weder eigenen noch
  fremden) — als Feld-Assertion, nicht als Regex auf Ziffern.
- Negativ: A ruft jeden Endpunkt in jeder Phase (vor eigener Abgabe / nach
  eigener, vor B / nach beiden) → die Feld-Whitelist hält durchgehend.

---

## 3. PR-WEB-06a — Backend-Fix-Paket

Rein `apps/api` + `packages`. Additive Migration. OpenAPI/TS-Client
regenerieren. Jede Position mit echten Zwei-Konten-Integrationstests. **Keine
Frontend-Änderung.** Reihenfolge: 06a zuerst mergen, Post-Merge-`main`-CI
grün, **dann** 06b (D4).

### A1 — Runden-Dimensions-Snapshot (unveränderlich)

**Problem:** offene Runde hat keine stabile Fragegrundlage
(`checkin_service.py:254-259` lädt je Submit frisch; A-only-Werte werden
`:288-296` still verworfen).

**Lösung:** Bei Runden-Eröffnung wird die vollständige aktive
Dimensions-Liste auf die Runde gesnapshottet — **je Dimension:
`dimension_id`, `semantic_key`, `label`, `description`, `scale_min`,
`scale_max`, `sort_order`** (dazu die `checkin_template_version`). Umsetzung:
neue Tabelle `checkin_round_dimensions` (FK auf `relationship_checkins`,
CASCADE), append-only, **nie mutiert**. Submit validiert `dimension_id`
gegen den Snapshot (nicht gegen `CheckinDimension.active`). Analyse liest
Werte + Labels aus dem Snapshot. Historische Snapshots bleiben unverändert,
auch wenn die Dimension später umbenannt/retired/gelöscht wird.

### A2 — `assert_workspace_active` bei Konfiguration

`create_custom_dimension` / `update_dimension` (`checkin_service.py:111-194`)
erhalten `assert_workspace_active_by_id` → `WORKSPACE_DISSOLVED` 409. Lesen
(`GET /checkin-template`, `GET /checkins`, `GET /checkins/current`) bleibt in
DISSOLVED erlaubt (`dissolution-policy.md`: historische Artefakte read-only).

### A3 — Explizite Runden + serverseitige Idempotenz *(D1)*

`expected_round_id` allein genügt nicht (Vorgabe). Umsetzung:

- **Neuer `POST /checkins/rounds`** (CSRF, 201) — eröffnet **explizit** eine
  `AWAITING_SUBMISSIONS`-Runde, snapshottet die Dimensionen (A1), gibt
  `CheckinRoundOut{id, checkin_template_version, status, cycle_started_at,
  dimensions: CheckinRoundDimensionOut[]}` zurück. **409 `CHECKIN_ROUND_OPEN`**,
  wenn bereits eine offene Runde existiert. Es gibt **keine** implizite
  Runden-Eröffnung mehr über `POST /checkins`.
- **`POST /checkins`** verlangt jetzt **`round_id` im Body** (Pflicht) und
  einen **`Idempotency-Key`-Header** (Pflicht, gleiches Muster wie
  `reports.create` / `relationship-analysis.create`).
  - Falsche/veraltete `round_id` (Runde nicht `AWAITING` oder unbekannt) →
    **409 `CHECKIN_ROUND_MISMATCH`**, keine neue Runde.
  - Wiederholter Request mit **demselben** `Idempotency-Key` → **derselbe
    `CheckinOut` idempotent zurück** (kein 409, keine Doppelverarbeitung).
    Persistierung des Keys pro `(round_id, user_id)` (neue Spalte/Tabelle
    `checkin_submissions_idempotency` oder `CheckinResponse.idempotency_key`
    denormalisiert auf Zeilenebene mit Unique).
  - Zweiter Submit desselben Users mit **anderem** Key für dieselbe Runde →
    weiterhin **409 `CHECKIN_ALREADY_SUBMITTED`** (kein Überschreiben).
- „Neue Check-in-Runde" = ausdrücklicher `POST /checkins/rounds` (durch die
  06b-UI mit Bestätigung). Kein Scheduler, keine Kadenz (kein neues
  Lifecycle jenseits `AWAITING`/`ANALYZED`).

### A4 — `value`-Range-Validierung

Submit prüft je Response `scale_min <= value <= scale_max` der
Snapshot-Dimension → **422 `CHECKIN_VALUE_OUT_OF_RANGE`** (Body nennt
Dimension-`label` + erlaubten Bereich, **nicht** den eingereichten Wert).

### A5 — „Beide beantworten dieselbe Snapshot-Menge"

Nach A1: `POST /checkins` verlangt je Runde Antworten für **alle**
Snapshot-Dimensionen (keine Teilabgabe). Fehlende/überzählige `dimension_id`
→ **422 `CHECKIN_RESPONSES_INCOMPLETE`**. Damit beantworten A und B garantiert
dieselben Fragen; das stille Verwerfen entfällt.

### A6 — Automatische Template-Versionierung *(neu in Scope, kein UI)*

**Problem:** `version` bleibt immer 1, In-place-Mutation; die Spec-Regel
„Aggregation nach `(semantic_key, checkin_template_version)`" ist faktisch
nicht auslösbar.

**Lösung:** `create_custom_dimension` / `update_dimension` bumpen die
Template-Version **automatisch**, sobald die aktuelle Version bereits von
**irgendeiner** eingereichten `CheckinResponse` referenziert wird
(„eingefroren durch Nutzung"). Bump = neue `CheckinTemplate`-Zeile
`version = N+1`, `active = True` (alte → `active = False`), **Kopie aller
aktuellen `CheckinDimension`-Datensätze** auf die neue Version, dann die
angeforderte Änderung auf der Kopie. Solange die aktuelle Version noch
**keine** Response hat, wird weiterhin in-place mutiert (kein Versions-Spam
vor der ersten Nutzung). Neue Runden (`POST /checkins/rounds`) nutzen die
neueste `active` Version; laufende/historische Runden bleiben über ihren
Snapshot (A1) + `checkin_template_version` gebunden. `GET /checkin-template`
liefert die neueste `active` Version; ein optionaler Query-Param
`?version=N` erlaubt das Lesen einer historischen Version (für die
06b-Trend-Segmentierung). **Kein Versionierungs-UI**, nur korrekte Daten.

### A7 — Config-Lock während offener Runde *(D3, Backend-hart)*

`create_custom_dimension` / `update_dimension` → **409 `CHECKIN_ROUND_OPEN`**,
solange eine `AWAITING_SUBMISSIONS`-Runde im Workspace existiert. Die
Fragegrundlage einer laufenden Runde ist damit unveränderlich — auch der
Version-Bump (A6) kann erst nach Abschluss der offenen Runde passieren.
`auto_retire_restricted_dimensions` (Hook aus `patch_relationship_type`)
ist davon ausgenommen (systemseitig, nicht user-getrieben) — **aber**: ein
Relationship-Type-Wechsel während einer offenen Runde muss die laufende
Runde konsistent behandeln (Empfehlung: `patch_relationship_type` blockt
ebenfalls mit `CHECKIN_ROUND_OPEN`, solange eine offene Runde existiert, und
retiret die Dimension erst danach — oder die offene Runde wird
systemseitig abgebrochen; **im 06a-Review festzulegen**).

### A8 — Dimension-Klasse (Pflicht-Klassifikation) *(D2)*

- Additive Spalte `CheckinDimension.dimension_class: str | None`
  (`INTIMATE` als erster Wert). Die Default-Dimension `sexual_connection`
  trägt **zwingend** `dimension_class = "INTIMATE"` (Migration + Seed).
- Die Restriktion (`_is_restricted`) prüft **die Klasse**, nicht mehr den
  Literal-Key: `dimension_class == "INTIMATE"` und
  `relationship_type ∈ {PARENT_CHILD, SIBLINGS, WORK}` → verboten
  (Create + Reaktivierung + Auto-Retire bei Typwechsel).
- `POST /checkin-dimensions` akzeptiert optional `dimension_class`; ohne
  Angabe → `null` (keine Restriktion).
- **Ehrliche Grenze (dokumentiert in Spec-Kommentar + 06b-UI-Hinweis):**
  Der Server kann eine **frei formulierte** Custom-Dimension, die inhaltlich
  intim ist, aber vom Nutzer **nicht** als `INTIMATE` klassifiziert wurde,
  **nicht** erkennen und **nicht** blocken. Keine Keyword-Heuristik (würde
  Bedeutung raten). Bekannte/Default-Keys sind zwingend klassifiziert; für
  User-Keys ist die Klasse eine bewusste Nutzer-Angabe.
- Managed-Minor: für einen `RelationshipWorkspace` **strukturell
  ausgeschlossen** (`minor-profile-policy.md:62` — nie shared workspace mit
  zwei Accounts), daher **kein** Minor-Check in diesem Pfad. Als
  Spec-Kommentar festhalten.

### A9 — Analyse-Race transaktional absichern *(Vorgabe 7)*

**Problem:** `create_analysis` (`repositories/checkins.py:266-282`) ist nicht
im `IntegrityError`-`try`; exakt gleichzeitiger Zweit-Submit kann 500 werfen
oder — je nach Isolation — einen hängenden `AWAITING`-Zustand hinterlassen.

**Lösung:** Beim Submit ein **Row-Lock auf die Runde** (`SELECT … FOR UPDATE`
auf `RelationshipCheckin` bzw. Postgres-Advisory-Lock auf `round_id`) für den
Abschnitt „Response schreiben → Submitter zählen → ggf. Analyse berechnen →
Status setzen". Damit serialisieren parallele Submits auf derselben Runde.
Zusätzlich `IntegrityError` um den Analyse-Block → re-fetch existierende
`CheckinAnalysis`, idempotent. **Test mit echten parallelen Transaktionen**
(zwei DB-Connections / `asyncio.gather` auf getrennten Sessions), nicht per
Monkeypatch: Ergebnis muss sein — **genau eine Runde, genau eine
`CheckinAnalysis`, kein hängender `AWAITING`, kein 500**, beide Aufrufer
bekommen ein wohldefiniertes Ergebnis (der „Verlierer" des Locks entweder
die fertige Analyse oder ein sauberes `202/200`).

### A10 — `GET /checkins/current` + Typ-Re-Exports

- `GET /checkins/current` → die offene `AWAITING`-Runde (inkl.
  `dimensions`-Snapshot + `my_responses` + „hat Partner abgegeben?"-Flag als
  **abgeleitetes Bool, kein Rohwert**: `partner_submitted: bool`) oder, wenn
  keine offen ist, die neueste `ANALYZED`-Runde mit `analysis`. Ein
  `partner_submitted`-Bool verrät nichts über Werte und macht den Zustand
  „Partner wartet auf mich" von „niemand hat abgegeben" unterscheidbar.
- `CheckinAnalysisOut` / `DimensionAnalysisOut` / `CheckinResponseOut` /
  `CheckinRoundOut` / `CheckinRoundDimensionOut` in `apps/web/src/api/client.ts`
  re-exportieren.

### Migration & Bestandsdaten *(Vorgabe 4)*

- Alle neuen Tabellen/Spalten **additiv**, `nullable` wo Bestandsdaten
  betroffen sind.
- **Bestehende `RelationshipCheckin`-Zeilen** (aus `9b42ce9`):
  - `status == ANALYZED`: die Analyse-JSON ist bereits persistiert →
    **kein** rekonstruierter Snapshot. `checkin_round_dimensions` bleibt für
    diese Runde **leer**; ein Flag `snapshot_recorded: bool` (default
    `false` für Bestandszeilen, `true` ab 06a) markiert das. 06b zeigt für
    solche Runden die Ergebnisfelder, aber **keine** rekonstruierten
    Dimension-Details/Labels als wären sie original — stattdessen die im
    Analyse-JSON enthaltenen `semantic_key`s + ein Hinweis „Dimensions-
    details für diese frühere Runde wurden nicht gespeichert".
  - `status == AWAITING` zum Migrationszeitpunkt (Randfall): Snapshot aus
    den **aktuell aktiven** Dimensionen, markiert `snapshot_recorded=true`
    (das ist der einzig verfügbare Wahrheitsstand; keine Erfindung).
- `CheckinDimension.dimension_class`: Migration setzt `INTIMATE` **nur** für
  `semantic_key == "sexual_connection"`, sonst `null`. Keine Heuristik über
  Bestands-Custom-Keys.
- `CheckinTemplate`: Bestand hat genau Version 1 → unverändert; A6 greift
  erst bei der nächsten Config-Änderung nach Nutzung.
- Kein Backfill von `Idempotency-Key` für historische Responses.

### 06a — Fehler-Codes (neu)

`CHECKIN_ROUND_OPEN` 409 · `CHECKIN_ROUND_MISMATCH` 409 ·
`CHECKIN_VALUE_OUT_OF_RANGE` 422 · `CHECKIN_RESPONSES_INCOMPLETE` 422.
(`DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE`, `CHECKIN_ALREADY_SUBMITTED`,
`SEMANTIC_KEY_IMMUTABLE`, `WORKSPACE_DISSOLVED` bleiben.)

---

## 4. PR-WEB-06b — Frontend (nach 06a-Merge)

### Route & Navigation
- `apps/web/src/app/workspaces/[id]/checkins/page.tsx` (Muster
  `dynamics/page.tsx`: `"use client"`, `useParams`, `AppShell`, `useAsync`
  auf `api.workspaces.get`, State-Isolation, `isPhaseDisabledError` →
  `PhaseDisabledState`).
- 4. Tab „Check-ins" in `workspace-nav-tabs.tsx`, Key
  `app.relationshipWorkspace.tabCheckins`.
- Hub-Stub-Card „Check-ins" → echter Link (übrige Stubs bleiben).

### Dimensionen-/Template-Konfiguration
- `GET /checkin-template` (neueste `active` Version) → aktive/retirte
  Dimensionen clientseitig trennen.
- Editieren `label`/`description` (PATCH), deaktivieren (PATCH `active:false`),
  Custom anlegen (POST) mit clientseitiger `semantic_key`-Pattern-Prüfung,
  optionaler `dimension_class`-Auswahl (`INTIMATE`) und dem
  **Immutabilitäts-Hinweis** „Bedeutung ist nach der ersten Antwort
  unveränderlich — zum Ändern neue Dimension anlegen" sowie dem
  **Ehrlichkeits-Hinweis** aus A8 (Server erkennt nicht-klassifizierte
  intime Custom-Dimensionen nicht).
- Retirte Dimension read-only, reaktivierbar sofern Klasse × Typ es zulässt.
- `DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE` 422 → Inline-Fehler.
- **Config gesperrt, solange eine Runde offen ist**: `CHECKIN_ROUND_OPEN` 409
  → die gesamte Config-UI ist read-only mit Hinweis „Konfiguration nach
  Abschluss der laufenden Check-in-Runde wieder möglich".
- `WORKSPACE_DISSOLVED`: Config read-only, historische Analysen lesbar.

### Erfassung & gemeinsame Runde
- `GET /checkins/current` → Zustand:
  - **Keine offene Runde:** „Neue Check-in-Runde beginnen"-Button (mit
    Bestätigung) → `POST /checkins/rounds` → Formular über die
    Snapshot-Dimensionen.
  - **Offene Runde, ich habe nicht abgegeben:** Formular über
    `dimensions`-Snapshot, Eingabe je Dimension im Bereich
    `scale_min..scale_max` (clientseitige Validierung, alle Dimensionen
    Pflicht — A5), „Abgeben" → `POST /checkins` mit `round_id` +
    per-Versuch-`Idempotency-Key` (`useRef`, gleiches Muster wie
    `analysis-launcher`).
  - **Offene Runde, ich habe abgegeben, Partner nicht**
    (`my_responses.length>0`, `partner_submitted===false`): Wartezustand
    „Auf {Name} warten", eigene Werte read-only, kein erneutes Abgeben.
  - **Beide abgegeben** (`status===ANALYZED`, `analysis` gesetzt): Ergebnis.
- Kein „Antwort ändern" (append-only). Retry bei Netzwerkfehler nutzt
  **denselben** `Idempotency-Key` (kein Doppel-Submit).

### Ergebnis-Ansicht (nur Anzeige)
- Je Dimension die 6 Felder **verbatim**; `direction` als lokalisierte
  Labels. UI berechnet **kein** gap/trend/mean/score.
- `sufficient_evidence:false` → gedämpfter „noch zu wenige Runden"-Hinweis.
- `absolute_gap` zurückhaltend formuliert (keine Geheimhaltungs-Zusage).
- Kein Compatibility-Score, kein Prozent, kein `role="progressbar"` für
  gap/trend.

### Trend über Runden
- `GET /checkins` → je `(semantic_key, checkin_template_version)` **getrennte**
  Serie (nie über Versionen mischen). Für Bestandsrunden ohne Snapshot:
  nur `semantic_key`-Ebene, mit dem Hinweis aus der Migrations-Sektion.
- Darstellung: schlichte Verlaufsliste/Sparkline der `absolute_gap`-Werte;
  keine Achsen-Beschriftung, die einen Rohwert nahelegt.

### Zustände (vollständig)
Loading · keine offene Runde · Formular · „ich abgegeben, warte auf
Partner" · „Partner abgegeben, ich noch nicht" (falls unterscheidbar über
`partner_submitted`) · Ergebnis · `sufficient_evidence:false` ·
`V2_PHASE_DISABLED` · `WORKSPACE_DISSOLVED` (Config read-only) ·
Inline-Fehler (`CHECKIN_ALREADY_SUBMITTED`, `CHECKIN_ROUND_MISMATCH`,
`CHECKIN_ROUND_OPEN`, `CHECKIN_VALUE_OUT_OF_RANGE`,
`CHECKIN_RESPONSES_INCOMPLETE`, `SEMANTIC_KEY_IMMUTABLE`,
`DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE`).

### i18n
Neuer Block `app.checkin.*` (DE+EN paarweise), Default-Dimensions-Labels,
`direction`-Labels, alle Fehlertexte. `catalog-parity`-Test.

### Nicht in 06b
Kein Versionierungs-UI. Kein Scheduler. Keine Backend-Änderung.

---

## 5. Prüfplan

### PR-WEB-06a (Backend) — Zwei-Konten-Integrationstests

| Fall | Erwartung |
|---|---|
| A1 Snapshot | Runde speichert `id/semantic_key/label/description/scale/sort_order` je Dimension; nach Dimension-Rename/Retire bleibt der Snapshot der alten Runde **byte-identisch**. |
| A2 DISSOLVED-Config | `POST /checkin-dimensions` + `PATCH /checkin-dimensions/{id}` in dissolved Workspace → 409 `WORKSPACE_DISSOLVED`; `GET /checkin-template` + `GET /checkins*` → 200. |
| A3 explizite Runde | `POST /checkins/rounds` zweimal → 2. → 409 `CHECKIN_ROUND_OPEN`. `POST /checkins` ohne `round_id` → 422. Mit `round_id` einer `ANALYZED`-Runde → 409 `CHECKIN_ROUND_MISMATCH`, **keine** neue Runde (`GET /checkins` unverändert). |
| A3 Idempotenz | Zweimal `POST /checkins` mit **gleichem** `Idempotency-Key` (gleiche Runde, gleicher User) → identischer `CheckinOut`, **eine** Response-Zeilengruppe, kein 409. Anderer Key, gleicher User, gleiche Runde → 409 `CHECKIN_ALREADY_SUBMITTED`. |
| A4 Range | `value = scale_min-1` bzw. `scale_max+1` → 422 `CHECKIN_VALUE_OUT_OF_RANGE`; Body enthält **keinen** `value`. |
| A5 Vollständigkeit | Submit mit fehlender/überzähliger `dimension_id` → 422 `CHECKIN_RESPONSES_INCOMPLETE`. Nach korrektem A- und B-Submit: Analyse über **alle** Snapshot-Dimensionen, nichts still verworfen. |
| A6 Versionierung | Vor erster Response: `update_dimension` mutiert Version 1 in-place. Nach einer Response (Runde abgeschlossen): `update_dimension` → neue Version 2, alte Dimensionen kopiert, alte Version `active=false`, alte Runde weiter an Version 1 + Snapshot gebunden. `GET /checkin-template?version=1` liefert den alten Stand. |
| A7 Config-Lock | Offene Runde vorhanden → `POST /checkin-dimensions` / `PATCH` → 409 `CHECKIN_ROUND_OPEN`. Nach Runden-Abschluss → wieder erlaubt (+ ggf. Version-Bump). Relationship-Type-Wechsel bei offener Runde: definiertes Verhalten (Review-Festlegung), kein stiller Zustand. |
| A8 Klasse | Default `sexual_connection` hat `dimension_class="INTIMATE"`. Create einer Custom-Dimension mit `dimension_class="INTIMATE"` in `WORK` → 422. Ohne Klasse → 201 (dokumentierte Grenze). Auto-Retire bei Typwechsel greift über die Klasse. |
| **A9 Analyse-Race (echte parallele Transaktionen)** | Zwei getrennte DB-Sessions submitten via `asyncio.gather` als A und B auf dieselbe offene Runde → **genau eine `RelationshipCheckin`**, **genau eine `CheckinAnalysis`**, Status `ANALYZED`, **kein hängender `AWAITING`**, **kein 500**; beide Aufrufer erhalten ein wohldefiniertes 200/201. Wiederholung 20× ohne Flake. |
| A10 current | `GET /checkins/current` liefert offene Runde mit `partner_submitted` (Bool, kein Wert) bzw. neueste `ANALYZED` mit `analysis`. |
| Migration | Test-DB mit Bestands-`RelationshipCheckin` (kein Snapshot) → 06a-Migration legt keine erfundenen Snapshot-Zeilen an; `snapshot_recorded=false`; `GET` funktioniert; kein 500. |
| **Privacy-Regression** | Alle bestehenden Section-49-Tests grün. Zusätzlich die Feld-Whitelist-Assertions aus §2 über **alle** neuen Endpunkte/Felder (`/checkins/rounds`, `/checkins/current`, `round_id`, `partner_submitted`, `dimensions`-Snapshot): kein Roh-Partnerwert, keine Partnerwert-förmige Struktur, `partner_submitted` ist reines Bool. |

Alle 12 Required Checks. OpenAPI/TS-Client-Drift **erwartet** → Regenerat
committen. Unabhängiger Review mit Fokus Privacy-Felder, Transaktions-/
Lock-Korrektheit, Migrations-Sicherheit.

### PR-WEB-06b (Frontend)

- **Vitest** (`vi.mock("@/api/client")`): Config (Create/Edit/Deactivate/
  Reactivate, 422-restricted, Immutabilitäts- + Ehrlichkeits-Hinweis,
  Config-Lock bei offener Runde, DISSOLVED-read-only), Runde beginnen
  (`POST /checkins/rounds`), Submit-Formular (Range, alle Dimensionen
  Pflicht, Idempotency-Key stabil pro Versuch), Wartezustände **beide
  Richtungen** über `partner_submitted`, Ergebnis (6 Felder verbatim, **kein**
  `role="progressbar"`/`%`/Score), `sufficient_evidence:false`-Hinweis,
  Trend-Segmentierung nach `(semantic_key, version)` inkl. Bestandsrunden-
  Hinweis, `V2_PHASE_DISABLED`.
- **`pr-web-06-visual-baseline.spec.ts`** (gemockt, kuratierte Fixtures) —
  Desktop 1440×900 **und** Mobile 390×844: keine-Runde, Config, Submit-
  Formular, „warte auf Partner", Ergebnis (mit/ohne `sufficient_evidence`),
  Trend, DISSOLVED, Config-Lock.
- **RC2 — vollständige Check-in-Journey auf Desktop UND Mobile** (Vorgabe 8):
  `rc2-two-account-journey.spec.ts`, echter Stack. Auf **beiden** Viewports:
  A beginnt eine Runde → A gibt über die UI ab → Wartezustand → B gibt über
  die UI ab (zweiter Kontext) → Ergebnis erreicht `ANALYZED` → Assertions:
  Ergebnisfelder vorhanden, `direction`-Label lokalisiert, kein Score/`%`.
  **Datenschutz auf API-Ebene, feldbasiert** (nicht DOM-Ziffernsuche): A
  ruft `GET /checkins/current` und `GET /checkins/{id}` → Response enthält
  nur die erlaubten Felder, `my_responses` nur A's Werte, kein Feld mit B's
  Rohwert; `partner_submitted` ist Bool. (Der Mock-Provider ist hier
  irrelevant — die Check-in-Analyse ist deterministischer Backend-Code, kein
  LLM.)
- Template-Wechsel/Config-Versuch bei offener Runde → UI zeigt
  `CHECKIN_ROUND_OPEN` sauber; kein Datenverlust.
- Doppel-/Parallel-Submit über die UI → 409 als Inline-Fehler, eigene
  abgegebene Werte bleiben sichtbar.
- Desktop + Mobile alle Fehlerfälle, `catalog-parity`, Required Checks,
  Post-Merge-`main`-CI, Execution-State + Evidence-Datei.

---

## 6. Getroffene Entscheidungen (waren D1–D5)

| Nr | Entscheidung |
|---|---|
| **D1** Runden-Lebenszyklus | Explizites `POST /checkins/rounds` + `round_id` (Pflicht) im Submit + **`Idempotency-Key` (Pflicht)** für idempotente Wiederholung. Keine implizite Runden-Eröffnung, kein Scheduler. (A3) |
| **D2** `sexual_connection`-Klasse | Additive `dimension_class`-Spalte, Default-Key **zwingend** `INTIMATE`, Restriktion über die Klasse; Grenze frei formulierter Custom-Dimensionen wird **ehrlich dokumentiert** (Server erkennt sie nicht). (A8) |
| **D3** Config-Sperre bei offener Runde | **Backend-hart** (409 `CHECKIN_ROUND_OPEN`). (A7) |
| **D4** Reihenfolge | **06a zuerst** als eigener PR, Merge, Post-Merge-`main`-CI grün, **dann** 06b-Umfang final vorlegen. 06b nicht auf den Lücken aufbauen. |
| **D5** RC2-Erweiterung | In **06b**, und dort als **vollständige Journey auf Desktop UND Mobile**. |
| Template-Versioning (war A9) | **In 06a** als automatischer Bump bei Nutzung, **ohne UI**. (A6) |

### Verbleibend im 06a-Review festzulegen
- A7: Verhalten von `patch_relationship_type` bei gleichzeitig offener
  Check-in-Runde (blocken vs. Runde abbrechen).
- A3: Ablageform des `Idempotency-Key` (eigene Tabelle vs. Spalte auf
  `CheckinResponse` / einem neuen `CheckinSubmission`-Aggregat).
- A9: Lock-Mechanismus (`SELECT … FOR UPDATE` auf die Runde vs.
  `pg_advisory_xact_lock`).

---

## 7. Zusammenfassung

- **Kein Widerspruch** Analyse ↔ Privacy; keine Contract-Änderung.
  Datenschutztests **feldbasiert** (Whitelist der 6 abgeleiteten Felder +
  Herkunfts-Assertion), **nicht** DOM-Ziffernsuche.
- **PR-WEB-06a** (Backend-Fix-Paket, zuerst): A1 Snapshot (id/key/label/
  description/scale/order, unveränderlich) · A2 DISSOLVED-Config-Sperre ·
  A3 explizite Runden + Idempotenz · A4 Range · A5 vollständige Abgabe ·
  A6 automatische Template-Versionierung (kein UI) · A7 Config-Lock bei
  offener Runde · A8 Dimension-Klasse (Pflicht + ehrliche Grenze) ·
  A9 Analyse-Race transaktional + Test mit echten parallelen Transaktionen ·
  A10 `/checkins/current` + Typ-Re-Exports · migrationssichere Bestandsdaten
  (keine rekonstruierten Originaldaten).
- **PR-WEB-06b** (Frontend, danach): Route + Tab, Config-UI, Runde beginnen/
  erfassen, Warte-/Ergebnis-/Trend-Ansicht, alle Zustände, **keine
  Browser-Berechnung**, **vollständige Journey Desktop + Mobile**.
- Nach 06a-Merge: Backend-Ergebnis + finaler 06b-Umfang vorlegen; **06b
  nicht** vorher implementieren.
