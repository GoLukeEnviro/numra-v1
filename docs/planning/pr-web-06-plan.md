# PR-WEB-06 — Configurable Check-ins (Plan)

Basis `main` @ `b2c0c9e`. Entspricht dem Web-Anteil von `PR-V2-06` aus
`specs/v2/api-contract.md` §53 — **nicht** deckungsgleich mit der
bereits gemergten Backend-Phase (`9b42ce9`, #26).

**Status: PLAN — keine Implementierung, kein Merge vor Freigabe.**

Maßgebliche Contracts: `specs/v2/checkin-spec.md` (Frozen Decision #8),
`specs/v2/privacy-spec.md` §49, `specs/v2/dissolution-policy.md` (#11),
`specs/v2/minor-profile-policy.md`, `specs/v2/evidence-policy.md`.

---

## 1. Vorhandener Backend-Contract (IST)

Backend komplett aus `9b42ce9`. Router `/v1/workspaces/{id}`, Flag
`require_v2_phase("checkins")` (prüft `avenyth_v2_enabled` +
`avenyth_checkins_enabled`), **kein Consent-Scope, kein Entitlement-Gate,
kein Rate-Limit**. Nicht-Member → 404.

| # | Endpunkt | Body ein | Body aus |
|---|---|---|---|
| 1 | `GET /checkin-template` | — | `CheckinTemplateOut{id, version, active, dimensions[]}` — **alle** Dimensionen inkl. retired |
| 2 | `POST /checkin-dimensions` (CSRF, 201) | `CheckinDimensionCreateRequest{semantic_key ^[a-z][a-z0-9_]*$, label, description?, scale_min=1, scale_max=10, sort_order=0}` | `CheckinDimensionOut` |
| 3 | `PATCH /checkin-dimensions/{id}` (CSRF) | `{label?, description?, active?}` — **nur diese 3** | `CheckinDimensionOut` |
| 4 | `POST /checkins` (CSRF, 201) | `CheckinSubmitRequest{responses:[{dimension_id, value:int}]}` — **kein round_id, kein template_version** | `CheckinOut{id, checkin_template_version, status, cycle_started_at, my_responses[], analysis?}` |
| 5 | `GET /checkins/{id}` | — | `CheckinOut` |
| 6 | `GET /checkins?limit&offset` | — | `CheckinSummaryOut[]{id, checkin_template_version, status, cycle_started_at}` — **kein `analysis`** |

`CheckinStatus`: nur `AWAITING_SUBMISSIONS` / `ANALYZED`.
`DimensionAnalysisOut` (je `semantic_key`): `absolute_gap:int`,
`direction: NO_PRIOR_DATA|CONVERGING|DIVERGING|STABLE`, `rolling_trend:float`,
`sample_size:int`, `historical_delta:float?`, `sufficient_evidence:bool`
(= `sample_size >= 3`). **`direction` ist zeitlich** (aktueller vs. voriger
gap), **nicht** „wer höher" → legt das Vorzeichen von `a−b` nicht offen.

Fehler: `CHECKIN_ALREADY_SUBMITTED` 409, `SEMANTIC_KEY_IMMUTABLE` 409,
`DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE` 422, `WORKSPACE_DISSOLVED` 409
(**nur Submit**), 404 (Nicht-Member / unbekannte id / inaktive dimension_id
im Submit).

Client (`apps/web/src/api/client.ts`): `api.workspaces.checkinTemplate.get`,
`checkinDimensions.{create,update}`, `checkins.{list,submit,get}`.
Typen `CheckinAnalysisOut`/`DimensionAnalysisOut`/`CheckinResponseOut`
**nicht** re-exportiert (nur inline über `CheckinOut`).

Runden-Modell: **höchstens eine `AWAITING_SUBMISSIONS`-Runde je Workspace**
(partieller Unique-Index). Submit ohne offene Runde → Server **eröffnet**
eine mit der aktuellen `template.version` als Snapshot-Integer. Beide Member
dürfen konfigurieren (einzeln, keine Zustimmung). Antworten **append-only**,
nicht editierbar. Analyse wird **synchron beim zweiten Submit** berechnet
(kein Worker, kein Polling).

---

## 2. Antworten auf die 7 Pflichtfragen

| Frage | Antwort (Contract-IST) |
|---|---|
| A/B-Zuordnung derselben Runde | Server-seitig: es gibt 0 oder 1 offene Runde je Workspace; beide Submits landen auf derselben. Kein `round_id` im Request. |
| Template-Version einer laufenden Runde | Beim Runden-Start als Integer eingefroren (`RelationshipCheckin.checkin_template_version`). **Aber:** es existiert praktisch nur Version 1 (kein Re-Versioning-Pfad). |
| Template-Änderung zwischen beiden Abgaben | `create/update_dimension` mutieren **in-place**, keine neue Version. Der Submit-Pfad lädt bei jedem Submit `active_only=True` **frisch** → A und B können **unterschiedliche Fragen** bekommen; eine nur von A beantwortete (dann deaktivierte) Dimension wird bei der Analyse **still verworfen** (kein Fehler). **Contract-Lücke.** |
| Editierbarkeit / Doppel-Submit | Antworten nicht editierbar (append-only). 2. Submit desselben Users in derselben Runde → 409, kein Überschreiben. 2. Submit **nach `ANALYZED`** → **eröffnet sofort eine neue Runde** (mit 1 Submitter). **Contract-Lücke.** |
| Wer darf Dimensionen/Templates ändern | Jeder ACTIVE-Member, einzeln. Kein Consent, keine Rolle, **kein DISSOLVED-Check bei `create/update_dimension`**. **Contract-Lücke.** |
| Was sieht jede Person vor / nach beidseitiger Abgabe | Vor: nur `my_responses` (eigene Rohwerte), `analysis: null`, **kein** Partner-Feld (auch nicht als Null-Platzhalter). Nach: `analysis.result[semantic_key]` mit den 6 abgeleiteten Feldern, nie Roh-Partnerwerte. |
| Was darf im geteilten Analyse-Response stehen | Exakt die 6 `DimensionAnalysisOut`-Felder je Dimension. Von Test `test_privacy_user_a_reads_after_both_submit_only_own_and_aggregate` abgesichert. |

### Privacy — keine Contract-Änderung nötig

Die Rückrechnung `partner ∈ {own+gap, own−gap}` ist in `checkin-spec.md:61-67`
**ausdrücklich als akzeptierter Trade-off** dokumentiert; `direction` ist
zeitlich und verrät das Vorzeichen nicht. Der Explore-Feldcheck bestätigt:
kein weiteres Feld (Rohwerte, Teil-Nulls, Fehlermeldungen) leakt den
Partnerwert. **Kein Widerspruch Analyse ↔ Privacy → keine neue
Produktentscheidung am Contract.** Einzige UX-Regel daraus: die WEB-06-UI
darf **keine vollständige Geheimhaltung** der Partnerwerte versprechen
(Formulierung im Ergebnis-Screen entsprechend zurückhaltend).

---

## 3. Notwendige Backend-Ergänzungen — **PR-WEB-06a (vorgeschaltet)**

Rein Backend, eigener Fix-PR **vor** der Oberfläche. Jede Position mit
echten Zwei-Konten-Regressionstests.

| # | Ergänzung | Beleg der Lücke | Vorgeschlagene Lösung (zu bestätigen) |
|---|---|---|---|
| **A1** | **Runden-Dimensions-Snapshot.** Eine offene Runde muss eine stabile Fragegrundlage haben; A und B beantworten dieselbe Menge. | `checkin_service.py:254-259` lädt `active_only=True` je Submit frisch; A-only-Werte werden `checkin_service.py:288-296` still verworfen. | Bei Runden-Eröffnung die aktive Dimensionsliste (ids + semantic_keys + scale) auf die Runde snapshotten (neue Tabelle `checkin_round_dimensions` **oder** `RelationshipCheckin.dimension_snapshot_json`). Submit validiert gegen den Snapshot, nicht gegen `active`. Analyse nutzt den Snapshot. |
| **A2** | **`assert_workspace_active` bei Konfiguration.** | `create_custom_dimension` / `update_dimension` (`checkin_service.py:111-194`) haben keinen Status-Check; `dissolution-policy.md` verbietet „new inference / new aggregation" nach Dissolution und listet Check-in-Config nicht als weiter erlaubt. | `assert_workspace_active_by_id` in beide Funktionen; → `WORKSPACE_DISSOLVED` 409. Regressionstest: Config in dissolved Workspace → 409; Lesen (`GET /checkin-template`, `GET /checkins`) bleibt erlaubt. |
| **A3** | **Runden-Lebenszyklus / kein versehentliches Neu-Eröffnen.** | Submit nach `ANALYZED` eröffnet sofort Runde N+1 (`checkin_service.py:229-235`); kein Signal, keine Kadenz. | Entscheidung nötig (siehe §6, Entscheidung D1). Minimal: Submit-Endpunkt akzeptiert optional `expected_round_id`; stimmt es nicht mit der offenen Runde überein (oder es gibt keine) → 409 `CHECKIN_ROUND_MISMATCH` statt stiller Neu-Eröffnung. UI schickt die id der Runde, die sie dem Nutzer gezeigt hat. |
| **A4** | **`value`-Range-Validierung** gegen `scale_min..scale_max` der Dimension. | `schemas/checkin.py:56-58` (`value:int` ohne Bounds), `build_response_rows` prüft nicht. | Serverseitige Prüfung im Submit → 422 `CHECKIN_VALUE_OUT_OF_RANGE`. UI validiert zusätzlich clientseitig. |
| **A5** | **„Beide beantworten dieselben Dimensionen"-Invariante** explizit machen. | s. A1; kein Fehler wenn B eine von A nicht beantwortete Dimension liefert oder umgekehrt. | Nach A1: Submit verlangt Antworten für **alle** Snapshot-Dimensionen (oder markiert bewusste „skip"). Analyse nur wenn beide für dieselbe Dimension abgegeben haben — bei asymmetrischer Abgabe klarer Zustand statt stillem Verwerfen. |
| **A6** | **Analyse-Race absichern.** | `create_analysis` (`repositories/checkins.py:266-282`) nicht im `IntegrityError`-`try`; paralleler Zweit-Submit kann 500 werfen. | `IntegrityError` um den Analyse-Block fangen → re-fetch existierende `CheckinAnalysis`, idempotent zurückgeben. Test: gleichzeitiger Zweit-Submit beider → genau eine Analyse, kein 500. |
| **A7** | **`analysis` in `CheckinSummaryOut`** *oder* neuer `GET /checkins/current` für die offene/letzte Runde; `CheckinAnalysisOut`/`DimensionAnalysisOut` in `client.ts` re-exportieren. | `schemas/checkin.py:100-106`; `client.ts:81-89`. | Klein; erspart der UI Liste + N Detail-Fetches. `GET /checkins/current` gibt die offene Runde oder (falls keine) die neueste `ANALYZED`. |
| **A8** | **Dimension-Klasse statt Einzel-Key** für die `sexual_connection`-Restriktion. | `checkin_service.py:39` `frozenset({"sexual_connection"})`; Spec `checkin-spec.md:47-48` „and any dimension of that class"; `minor-profile-policy.md:54-55`. | Entscheidung nötig (§6, D2). Minimal-Variante: `CheckinDimension.dimension_class: str|None` (`INTIMATE` o.ä.), Default-`sexual_connection` trägt sie; Restriktion prüft die Klasse. Managed-Minor ist für RelationshipWorkspaces **strukturell ausgeschlossen** (`minor-profile-policy.md:62` — nie shared workspace), daher kein Minor-Check in diesem Pfad nötig. |
| **A9** | *(optional)* **Kein echtes Template-Versioning.** | `tables.py:882-884`. | Für WEB-06 **nicht** zwingend — solange A1 (Snapshot je Runde) existiert, braucht die UI keine Template-Historie. `checkin_template_version` bleibt 1; `list_prior_analyses`-Segmentierung nach Version bleibt korrekt (nur derzeit trivial). Als eigener späterer PR, wenn Template-Evolution über Versionen gewünscht ist. |

**PR-WEB-06a-Umfang:** A1–A8 (A9 aufgeschoben). Reine
`apps/api` + `packages`-Änderungen, ggf. eine additive Migration
(A1-Snapshot). OpenAPI/TS-Client regenerieren. Zwei-Konten-Integrationstests
für jede Position. Keine Frontend-Änderung.

---

## 4. Frontend-Umfang — **PR-WEB-06b**

Voraussetzung: 06a gemergt.

### Route & Navigation
- Neue Route `apps/web/src/app/workspaces/[id]/checkins/page.tsx` (Muster
  `dynamics/page.tsx`: `"use client"`, `useParams`, `AppShell`, `useAsync`
  auf `api.workspaces.get`, State-Isolation `workspace.id === id`,
  `isPhaseDisabledError` → `PhaseDisabledState`).
- 4. Tab „Check-ins" in `components/workspaces/workspace-nav-tabs.tsx`
  (Array manuell erweitern, Key `app.relationshipWorkspace.tabCheckins`).
- Hub-Stub-Card „Check-ins" (`page.tsx:57-61`) → echter Link (die übrigen
  Stubs bleiben).

### Dimensionen-/Template-Konfiguration
- `GET /checkin-template` laden (Default wird lazily angelegt) →
  aktive/retirte Dimensionen clientseitig trennen.
- Aktive Dimension: `label`/`description` editieren (PATCH), deaktivieren
  (PATCH `active:false`), Custom-Dimension anlegen (POST) mit
  clientseitiger `semantic_key`-Pattern-Validierung und Hinweis
  „Bedeutung ist nach der ersten Antwort unveränderlich — zum Ändern neue
  Dimension anlegen".
- Retirte Dimension: read-only anzeigen, reaktivierbar (PATCH `active:true`)
  sofern nicht `sexual_connection`-Klasse × restricted Type.
- `DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE` (422) → Inline-Fehler,
  kein `PhaseDisabledState`.
- **Config-Sperre solange eine Runde `AWAITING_SUBMISSIONS` ist**
  (nach 06a/A1): Konfiguration ist gesperrt/gewarnt, bis die offene Runde
  abgeschlossen ist — die Fragegrundlage einer laufenden Runde darf sich
  nicht ändern. Ohne A1: WEB-06b schaltet die Config-UI clientseitig
  read-only während `AWAITING`, mit sichtbarem Hinweis (Backend erlaubt es
  sonst).
- Bei `WORKSPACE_DISSOLVED`: gesamte Config-UI read-only, historische
  Analysen weiter lesbar (`dissolution-policy.md`).

### Eigene Erfassung & gemeinsame Runde
- „Runden"-Zustand aus `GET /checkins/current` (06a/A7) bzw. `list` +
  clientseitiger Auswahl der `AWAITING`-Runde:
  - **Keine Runde / keine Abgabe:** Formular über die aktiven
    (Snapshot-)Dimensionen, Slider/Zahleneingabe `scale_min..scale_max`,
    clientseitige Range-Validierung, „Abgeben" → `POST /checkins`
    (mit `expected_round_id` aus 06a/A3).
  - **Ich habe abgegeben, Partner nicht** (`my_responses.length>0`,
    `status===AWAITING`, `analysis===null`): Wartezustand „Auf {Name}
    warten", eigene abgegebene Werte read-only sichtbar, kein erneutes
    Abgeben (409-sicher, Button aus).
  - **Beide abgegeben** (`status===ANALYZED`, `analysis` gesetzt):
    Ergebnis-Ansicht.
- Kein „Antwort ändern" (append-only). Kein „neue Runde starten"-Button
  bevor D1 entschieden ist.

### Ergebnis-Ansicht (nur Anzeige, keine Browser-Berechnung)
- Je Dimension: `absolute_gap`, `direction`
  (`CONVERGING`/`DIVERGING`/`STABLE`/`NO_PRIOR_DATA` als lokalisierte
  Labels), `rolling_trend`, `sample_size`, `historical_delta`,
  `sufficient_evidence`. **Alle Werte verbatim aus dem Response** — die UI
  berechnet **kein** gap/trend/mean/score.
- Bei `sufficient_evidence:false`: gedämpfter „noch zu wenige Runden für
  einen Trend"-Hinweis statt eines scheinbar belastbaren Trends.
- Zurückhaltende Formulierung zum `absolute_gap` (siehe §2 Privacy):
  **nicht** „nur ihr beide seht das" o.ä.
- Kein Compatibility-Score, kein Prozent.

### Trend über Runden
- `GET /checkins` (Liste) → je `semantic_key` **und** `checkin_template_version`
  getrennte Serie (nie über Versionen mischen — Spec §41-44). Da 06a/A1 die
  Fragegrundlage je Runde stabilisiert und `checkin_template_version`
  vorerst 1 bleibt, ist die Segmentierung meist trivial, muss aber im Code
  vorhanden sein.
- Darstellung: einfache Verlaufsliste/Sparkline der `absolute_gap`-Werte je
  Dimension; keine Achsen-Beschriftung die einen Rohwert nahelegt.

### Zustände (vollständig)
Loading · Empty (keine Dimension aktiv / keine Runde) · „ich abgegeben,
warte auf Partner" · „Partner abgegeben, ich noch nicht" · Ergebnis ·
`sufficient_evidence:false` · `V2_PHASE_DISABLED` (Flag aus) ·
`WORKSPACE_DISSOLVED` (Config read-only, Historie lesbar) · Inline-Fehler
(409 already-submitted, 422 range, 422 type-restriction, 409 round-mismatch,
409 semantic-key-immutable).

### i18n
Neuer Block `app.checkin.*` (DE + EN paarweise), inkl. Dimensions-Default-Labels
(`closeness`, `communication`, `understanding`, `autonomy`, `conflict_load`) und
`direction`-Labels. `catalog-parity`-Test.

### Nicht in 06b
Kein manuelles Template-Versioning-UI. Kein Runden-Scheduler. Keine
Historie-über-Template-Versionen-Ansicht. Keine Backend-Änderung.

---

## 5. Prüfplan

### PR-WEB-06a (Backend)
- Zwei-Konten-Integrationstests je Position A1–A8. Insbesondere:
  - A1/A5: A gibt ab → Dimension deaktiviert/hinzugefügt → B gibt ab →
    beide beantworten denselben Snapshot; asymmetrische Abgabe = klarer
    Fehler, kein stilles Verwerfen.
  - A2: `create/update_dimension` in dissolved Workspace → 409; Lesen ok.
  - A3: Submit mit `expected_round_id` einer bereits `ANALYZED`-Runde →
    409, **keine** neue Runde.
  - A4: `value` < min / > max → 422.
  - A6: gleichzeitiger Zweit-Submit → genau eine `CheckinAnalysis`, kein 500.
- **Privacy-Regression (bestehende Section-49-Tests müssen grün bleiben):**
  kein Feld, keine Fehlermeldung leakt einen Roh-Partnerwert; `analysis`
  erst nach beidseitiger Abgabe.
- Alle 12 Required Checks; OpenAPI/TS-Client-no-drift **erwartet Änderung**
  (neuer Endpunkt / Felder) → Regenerat committen.

### PR-WEB-06b (Frontend)
- Vitest (`vi.mock("@/api/client")`): Config (Create/Edit/Deactivate/
  Reactivate/422-restricted/Immutability-Hinweis), Submit-Formular
  (Range-Validierung, alle Snapshot-Dimensionen), Wartezustände beide
  Richtungen, Ergebnis-Rendering (Werte verbatim, **kein** `role="progressbar"`
  für gap/trend, kein `%`, kein Score), `sufficient_evidence:false`-Hinweis,
  Trend-Segmentierung nach `(semantic_key, version)`, DISSOLVED-Read-only,
  `V2_PHASE_DISABLED`.
- `pr-web-06-visual-baseline.spec.ts` (gemockt, kuratierte Fixtures) —
  Desktop 1440×900 + Mobile 390×844: Config-Ansicht, Submit-Formular,
  „warte auf Partner", Ergebnis (mit/ohne sufficient_evidence), Trend,
  DISSOLVED.
- **RC2-Zweikonten-Journey erweitern** (`rc2-two-account-journey.spec.ts`,
  echter Stack, Desktop): nach dem bestehenden Consent-/Dynamics-Block →
  A navigiert zu `/checkins`, beide geben eine Runde ab (A per UI, B per UI),
  Ergebnis erreicht `ANALYZED`, Assertions: A sieht **nie** B's Rohwert
  (DOM-Scan), Ergebnisfelder vorhanden, kein Score. **API-Ebene zusätzlich:**
  direkter `GET`-Versuch von A auf B's Antworten → kein Rohwert im Response.
  Mobile: nur Struktur-Smoke (Formular + Wartezustand), analog WEB-05.
- Template-Wechsel während offener Runde: Playwright/Integration —
  Config-UI ist während `AWAITING` gesperrt (bzw. 06a-Fehler wird sauber
  angezeigt).
- Doppel-/Parallel-Submit: 409 wird als Inline-Fehler angezeigt, kein
  Datenverlust.
- Desktop + Mobile, alle Fehlerfälle, `catalog-parity`, Required Checks,
  Post-Merge-`main`-CI, Execution-State + Evidence-Datei.

---

## 6. Offene Entscheidungen (Freigabe nötig)

**D1 — Runden-Lebenszyklus.** Es gibt keinen „Runde starten/schließen".
Optionen:
- (a) **Minimal (empfohlen):** kein neues Lifecycle-Konzept; 06a/A3 fügt nur
  `expected_round_id` hinzu, damit die UI nicht versehentlich eine neue
  Runde eröffnet. „Neue Runde" entsteht implizit, wenn ein Nutzer nach
  `ANALYZED` bewusst erneut abgibt — die UI macht das über einen expliziten
  „Neue Check-in-Runde beginnen"-Button (mit Bestätigung) sichtbar.
- (b) Echter `POST /checkins/rounds` + `status: OPEN/CLOSED/ANALYZED` +
  optionale Kadenz — größerer Backend-PR, mehr als „Fix-Paket".
- (c) Nur eine Runde je Zeitfenster (z.B. 1×/Woche) serverseitig erzwingen.

**D2 — `sexual_connection`-Klasse.** Spec fordert „any dimension of that
class". Optionen:
- (a) **Minimal (empfohlen):** additive `dimension_class`-Spalte,
  Default-Dimension `sexual_connection` = Klasse `INTIMATE`, Restriktion
  prüft die Klasse; User können beim Custom-Create eine Klasse wählen
  (Default: keine). Deckt „bewusst als intim markierte" Custom-Dimensionen.
- (b) Status quo (nur Literal-Key `sexual_connection`) belassen und die
  Lücke dokumentieren — verletzt den Spec-Wortlaut.
- (c) Keyword-Heuristik serverseitig — abgelehnt (rät Bedeutung).

**D3 — Config-Sperre während offener Runde.** Backend (06a/A1) hart sperren
(`WORKSPACE_CHECKIN_ROUND_OPEN` 409 bei `create/update_dimension` solange
`AWAITING`) **oder** nur die UI read-only schalten? Empfehlung: **Backend
hart** (die Fragegrundlage-Konsistenz ist ein Contract-Thema, keine
UI-Höflichkeit).

**D4 — Reihenfolge.** Empfehlung: **06a zuerst als eigener Fix-PR mergen,
Post-Merge-CI grün, dann 06b planen/umsetzen.** 06b nicht auf den Lücken
aufbauen.

**D5 — RC2-Erweiterung jetzt oder in 06b.** Empfehlung: in 06b (die
Check-in-Journey braucht die UI).

---

## 7. Zusammenfassung

- **Kein Widerspruch** zwischen Analyse- und Privacy-Contract; keine
  Contract-Änderung. Einzige UX-Auflage: keine „vollständige
  Geheimhaltung"-Zusage.
- **4 bestätigte Backend-Lücken** (Snapshot fehlt, DISSOLVED-Config,
  Runden-Zuordnung, + `value`-Range) plus 4 kleinere (Summary-`analysis`,
  Analyse-Race, Dimension-Klasse, current-round-GET). → **PR-WEB-06a**.
- **PR-WEB-06b** danach: Route, Config-UI, Erfassung, Warte-/Ergebnis-/
  Trend-Ansicht, alle Zustände, keine Browser-Berechnung.
- **5 offene Entscheidungen** (D1–D5) vor Umsetzung.
- Kein echtes Template-Versioning in diesem Zug (A9 aufgeschoben).
