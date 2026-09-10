# PR-WEB-05 — Relationship / Shadow Analysis UI

**Segment C, erster Web-PR.** Basis `main` @ `da79405` (RC2 freigegeben).
Entspricht `PR-V2-05` aus `specs/v2/api-contract.md` §53
(„Relationship/Shadow Analysis"). Nachfolger von PR-WEB-04.

## Ziel

Die zwei bereits fertigen Backend-Analysen — **Relationship Analysis**
(Frame-Dimensionen je Beziehungstyp) und **Shadow Dynamics**
(Schattenthemen, Interaktionsmuster) — in einer neuen Workspace-Unterseite
`/workspaces/[id]/dynamics` sichtbar machen: Start, Job-Polling,
Ergebnis-Rendering mit vollständiger Provenance, Versions-Footer, und alle
phasengesteuerten Sperrzustände. Reines Frontend.

## Enthalten

- Route `app/workspaces/[id]/dynamics/page.tsx` mit zwei **unabhängigen**
  gestapelten Abschnitten (Relationship zuerst, dann Shadow) — je eigener
  Job-State, Launch, Retry, `Idempotency-Key`.
- „Gibt es schon eine Analyse?"-Initialladen je Abschnitt
  (`GET .../relationship-analysis` bzw. `.../shadow-dynamics` ohne id →
  200 rendert / 404 = „noch keine Analyse" + Start-Button).
- Launch = `POST` mit per-Versuch-`Idempotency-Key` (via `useRef`), danach
  Polling `GET /v1/analysis-jobs/{job_id}` alle 2500 ms (Muster
  `use-report-progress.ts`), bei Job `COMPLETE` → `GET .../{analysis_id}`
  (voller Body) → strukturelles Narrowing → Render.
- Relationship-Render: pro Frame-Dimension genau 1 Statement mit sichtbarer
  Provenance (`canonical_refs`, `knowledge_refs`, `workspace_evidence_refs`
  — **leere Arrays werden angezeigt**, nicht weggelassen).
- Shadow-Render: alle 7 Result-Felder (`user_a_shadow_themes`,
  `user_b_shadow_themes`, `interaction_pattern`, `escalation_loop`,
  `deescalation_opportunities`, `pattern_intensity` als **Label-Text**,
  `recommended_micro_tasks` als Liste), Themen mit Provenance.
- Job-Progress-State (`progress` 10/80/100 verbatim, `attempt_count`),
  FAILED-State mit `error_code` **verbatim** + Retry (= neuer POST mit
  frischem Key).
- Versions-Footer (calculation/knowledge/prompt_version,
  model_provider/model_name) analog Report-Reader-Footer.
- Phase-Disabled-Zustände als ruhiger `PhaseDisabledState` (nicht roter
  `ErrorState`): `WORKSPACE_DISSOLVED`, `KNOWLEDGE_FRAME_NOT_AVAILABLE`,
  `CONSENT_NOT_GRANTED`, **neu** `RELATIONSHIP_TYPE_NOT_SET`,
  `SELF_PROFILE_REQUIRED`.
- „Dynamics"-Tab in `WorkspaceNavTabs`; die „Dynamics"-`FeatureStubCard` im
  Hub wird durch einen echten Link ersetzt (die anderen 5 Stubs bleiben).
- i18n-Block `app.dynamics.*` (DE + EN) inkl. Dimensions-Label-Map.

## Ausgeschlossen

- Check-ins (V2-06), Tasks (V2-07), Roadmaps + Shared Reflection (V2-08),
  Copilot (V2-09) — bleiben `ComingSoonState`-Stubs.
- Kein Backend-, OpenAPI-, TS-Client-Generat-, Alembic-Change.
- Keine produktive Feature-Flag-Aktivierung (Flags bleiben default-off; nur
  Test-/RC2-Env aktiviert sie).
- Kein Export/PDF der Analysen, kein History-/Verlaufs-Listing über die
  „latest COMPLETE"-Semantik hinaus, kein Evidence-Layer-UI (V2-11).
- Keinerlei Compatibility-Score / Prozent- oder Balken-Darstellung.

## Betroffene API-Contracts

**Keine Änderung.** Konsumiert (alle bereits vorhanden, Typen in
`@numra/schema`):

| Methode | Pfad | Zweck |
|---|---|---|
| POST | `/v1/workspaces/{id}/relationship-analysis` | Start (201, CSRF, opt. `Idempotency-Key`, Rate-Limit 30/h) → `RelationshipAnalysisOut{status:"PENDING", job_id, result:null}` |
| GET | `/v1/workspaces/{id}/relationship-analysis` | latest, nur wenn `status=="COMPLETE"`, sonst 404 |
| GET | `/v1/workspaces/{id}/relationship-analysis/{analysis_id}` | voller Body, jeder Status |
| POST/GET/GET | `/v1/workspaces/{id}/shadow-dynamics[...]` | analog |
| GET | `/v1/analysis-jobs/{job_id}` | `AnalysisJobOut{status: QUEUED\|GENERATING\|VALIDATING\|COMPLETE\|FAILED, progress, error_code, attempt_count}` |

Fehler beim POST: `WORKSPACE_DISSOLVED` 409, `RELATIONSHIP_TYPE_NOT_SET`
409, `SELF_PROFILE_REQUIRED` 409, `KNOWLEDGE_FRAME_NOT_AVAILABLE` 409 (nur
relationship-analysis), `CONSENT_NOT_GRANTED` 403 (braucht **beidseitig**
`RELATIONSHIP_INSIGHTS`), `NOT_FOUND` 404 (IDOR / keine latest).

`result` ist im OpenAPI-Typ nur `{[k]:unknown}|null` → Frontend narrowt
strukturell (`api/analysis-content.ts`, Muster `report-content.ts`).
Result-Shapes gespiegelt aus
`packages/engine-relationship-interpretation/.../schemas.py`.

## Abnahmekriterien

- Alle 12 bestehenden Required Checks grün, insb. „OpenAPI/TS-Client no
  drift" (kein Contract-Change → dürfen sich nicht bewegen) und
  `catalog-parity`.
- Neue Vitest-Suites (Hook mit Fake-Timers, Views, Narrowing-Guards,
  nav-tabs, states-Erweiterung) grün.
- `pr-web-05-visual-baseline.spec.ts` erzeugt Screenshots aller Szenarien
  in Desktop 1440×900 + Mobile 390×844.
- Kein Element ohne zugehörige Provenance sichtbar (Ausnahme:
  `recommended_micro_tasks` — deterministisch abgeleitete Liste, mit
  Hinweistext, kein Free-Text-Claim). `pattern_intensity` nur als Text,
  nie als Zahl/`role="progressbar"`/`%`. Keine Diagnose-/Schicksalssprache
  in Copy.
- Consent-Richtung, serverseitige Autorisierung, Workspace-Isolation,
  Re-Grant, DISSOLVED-Sperre, Commit-vor-Response unangetastet.
- RC2-Zweikonten-Journey lokal grün + RC2-Workflow manuell grün
  (Consent-/Workspace-Berührung).

## Geklärte Design-Entscheidungen

1. **Eine Route, zwei gestapelte Abschnitte** (nicht zwei Routen / keine
   Sub-Tabs) — konsistent mit einem Hub-Stub, einem Nav-Tab, der
   V2-06+-Tab-Struktur.
2. **Handkuratierte Mock-Fixtures** unter `apps/web/src/fixtures/analysis/`
   (von Vitest-Views UND `pr-web-05-visual-baseline.spec.ts` via
   `page.route` genutzt). Der Mock-LLM-Provider echot Grounding-Rohtext →
   für einen menschlichen Reality-Check ungeeignet; RC2/system-e2e gelten
   nur als **Struktur-Smoke** (Provenance sichtbar, 7 Felder da, kein
   Score), nicht als Prosa-Nachweis.
3. **Shadow: neutrale Labels „Person A" / „Person B".** `user_a`/`user_b`
   im gespeicherten Snapshot tragen keine Member-Identität; die
   Member-Reihenfolge (`list_workspace_members` ohne `ORDER BY`) ist nicht
   garantiert deckungsgleich mit `dual_profile`. Eine Namenszuordnung
   würde raten und könnte jemandem falsche Schattenthemen zuschreiben —
   verboten. Bekannte Einschränkung; Namenszuordnung braucht einen
   separaten Backend-Change (Member-IDs im Result).
4. **Dimensions-Labels:** i18n-Map `app.dynamics.dimension.<id>` für die
   21 bekannten IDs (`communication`, `closeness`, `autonomy`, `needs`,
   `strengths`, `conflict_dynamics`, `boundaries`, `support`, `pace`,
   `collaboration`, `structure`, `responsibility`, `power_dynamics`,
   `family_roles`, `long_term_patterns`, `expectations`, `loyalty`,
   `shared_history`, `rivalry_and_cooperation`, `attraction_dynamics`,
   `guidance_and_independence`) + Humanize-Fallback (`snake_case` →
   „Title Case") für unbekannte/künftige IDs.
5. **`recommended_micro_tasks`** ohne Provenance-Chips, mit Hinweistext
   „deterministisch aus dem Muster abgeleitet" — reine Strings, kein
   Free-Text-Claim, von der Spec als Pflicht-Liste geführt.
6. **`status`-Feld** (`PENDING|COMPLETE|FAILED`, eigener String neben dem
   Job-Enum): Job-Status ist Autorität für Progress/Terminalität,
   `result != null` treibt den Content-Render (defensive Kombination, da
   `result` in jedem Status geliefert wird).
7. **Client-Namespace:** `api.workspaces.relationshipAnalysis.*`,
   `api.workspaces.shadowDynamics.*`, `api.analysisJobs.get(jobId)`.

## Dateien (neu / geändert)

Siehe Umsetzungsschritte. Neu u. a.:
`app/workspaces/[id]/dynamics/page.tsx`,
`components/workspaces/dynamics/{dynamics-content,analysis-section,analysis-launcher,analysis-progress-view,relationship-analysis-view,shadow-dynamics-view,provenance-sources,analysis-meta-footer}.tsx`,
`lib/{use-analysis-progress,analysis-status}.ts`,
`api/analysis-content.ts`, `fixtures/analysis/*`,
`e2e-system/pr-web-05-visual-baseline.spec.ts`, plus Tests.
Geändert: `api/client.ts` (Namespaces + Typ-Re-Exports),
`components/ui/states.tsx` (2 neue `PhaseErrorCode`),
`components/workspaces/workspace-nav-tabs.tsx` (Dynamics-Tab),
`app/workspaces/[id]/page.tsx` (Stub → Link),
`i18n/messages/{de,en}/app.ts`.

## Zustandsmodell

**Seite:** `useAsync(api.workspaces.get(id))` → `loading`/`error`
(PhaseDisabled vs. ErrorState)/`success`. `DISSOLVED` → ganzseitiger
`PhaseDisabledState code="WORKSPACE_DISSOLVED"`. Sonst zwei
`<AnalysisSection>`.

**Abschnitt** (`useAnalysisProgress(workspaceId, type)` → diskriminierte
Union): `loading` → `LoadingState`; `empty` (404) → Erklärtext +
`<AnalysisLauncher>`; `phaseDisabled` (GET latest oder create wirft einen
der 5 Codes) → `PhaseDisabledState` mit abschnittsspezifischer Copy + ggf.
Link zu Hub/Consent; `error` (sonstiger Fehler / ≥4 konsekutive
Poll-Fehler / by-id-GET-Fehler) → `ErrorState` + `reload()`; `pending`
(nach create oder initialem latest mit `status ∉ {COMPLETE,FAILED}`) →
`<AnalysisProgressView>`; `failed` → `<AnalysisFailedView error_code
retry>`; `complete` → `result` narrowen → View, oder bei Guard-`null`
`ErrorState` „complete aber unlesbar" + `reload()`.

## Umsetzungsreihenfolge (blattnah zuerst)

1. `api/client.ts` — Namespaces + Typ-Re-Exports (`tsc` grün).
2. `lib/analysis-status.ts` + Test (hardcoded EN wie `report-status.ts`).
3. `api/analysis-content.ts` + Test (Guards, leere Provenance).
4. `components/ui/states.tsx` — 2 neue Codes + Test.
5. `provenance-sources.tsx` + `analysis-meta-footer.tsx` + Tests.
6. `relationship-analysis-view.tsx` + `shadow-dynamics-view.tsx` + Tests
   (nutzen Fixtures aus `src/fixtures/analysis/`).
7. `lib/use-analysis-progress.ts` + Hook-Test (`vi.useFakeTimers()`).
8. `analysis-launcher.tsx`, `analysis-progress-view.tsx`,
   `analysis-section.tsx`, `dynamics-content.tsx`.
9. `app/workspaces/[id]/dynamics/page.tsx` + Page-Test.
10. `workspace-nav-tabs.tsx` (Dynamics-Tab) + `workspaces/[id]/page.tsx`
    (Stub → Link) + Test-Updates.
11. i18n DE + EN parallel; `catalog-parity.test.ts` lokal.
12. `pr-web-05-visual-baseline.spec.ts` (alle Szenarien, beide Viewports).
13. Gesamtlauf: lint + tsc + build + vitest; Playwright-Visual-Baseline;
    RC2 lokal.

## Verifikation

- **Vitest:** Hook (404→empty; create→pending→QUEUED→GENERATING(80)→
  COMPLETE→by-id→complete; FAILED→failed+error_code; 4 Poll-Fehler→error;
  create wirft `CONSENT_NOT_GRANTED`/`RELATIONSHIP_TYPE_NOT_SET`→
  phaseDisabled; Idempotency-Key stabil pro Versuch, neu bei Retry).
  Narrowing-Guards. `analysis-status`. View-Tests (Provenance sichtbar
  inkl. leerer Arrays; `pattern_intensity` als Text, kein `progressbar`,
  kein `%`; Micro-Tasks als `listitem`; beide `user_a`/`user_b`-Blöcke).
  `provenance-sources` Toggle + leeres Array sichtbar. `workspace-nav-tabs`
  (3 Tabs, `aria-current`). `states` (`isPhaseDisabledError` für die 2
  neuen Codes). Page-Test (beide Abschnitte, DISSOLVED ganzseitig,
  Launch löst `create`). `catalog-parity` automatisch.
- **Playwright Visual-Baseline** (Desktop + Mobile), Szenarien: noch keine
  Analyse · Job läuft · Relationship complete · Shadow complete · FAILED ·
  CONSENT_NOT_GRANTED · RELATIONSHIP_TYPE_NOT_SET · Workspace DISSOLVED.
- **Required Checks:** alle 12; `web-lint-typecheck-build-test`,
  `playwright` (golden journey unberührt), `system-e2e`/`docker-compose-e2e`,
  OpenAPI/TS-Client-no-drift (kein Change), `catalog-parity`.
- **RC2** (Consent/Workspace/Auth berührt): `scripts/rc2-e2e.sh`
  {up,test,down} lokal grün; RC2-Workflow manuell grün. Optional die
  RC2-Journey um einen `/dynamics`-Struktur-Smoke erweitern (beide
  Analysen starten, `complete` abwarten, Provenance-Chips + Meta-Footer
  strukturell asserten — keine Prosa).
- **Desktop + Mobile Funktionsnachweis:** Visual-Baseline-Artefakte beide
  Viewports + manueller Durchlauf gegen den RC2-Stack (1440×900 und
  390×844) mit Screenshots von empty/pending/relationship-complete/
  shadow-complete.
