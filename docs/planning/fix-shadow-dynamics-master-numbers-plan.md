# Fix — Shadow Dynamics bricht bei Meisterzahl-Lebenszahlen

Separater Fix-PR (nicht WEB-06). Basis `main` @ `1bb3da1`.

## Fehler

`packages/engine-relationship-interpretation/.../context.py::primary_shadow_theme`
gibt für Life Path 11/22/33 `shadows[0]` aus
`knowledge/master-numbers/{11,22,33}.yaml` zurück — **„Überreizung" / „enormer
innerer Druck" / „Märtyrerrolle"**. `knowledge/shadow-interaction/rules.yaml`
enthält keine Zeile mit diesen Strings → `assemble_shadow_context`
(`context.py:198-205`) wirft `ValueError` → in `run_shadow_dynamics_job`
(`relationship_analysis_service.py:449-457`) als `UNEXPECTED_ERROR`,
`retryable=False`, terminaler Job-Fail.

`_life_path_value` liest `effective_value` — bei einer Meisterzahl ist das die
Meisterzahl selbst (Canon „Master Rule"), es wird **nichts** auf 2/4/6 reduziert.

### Zweiter, breiterer Bug (im selben Fehlermodus)

`rules.yaml` nutzt ASCII-Transkription (`Rigiditaet`, `Ueberverantwortung`,
`Rueckzug`), `knowledge/numbers/{4,6,7}.yaml` echte Umlaute (`Rigidität`,
`Überverantwortung`, `Rückzug`). Der Lookup vergleicht Strings exakt
(`{a,b} == {theme_a,theme_b}`). → Shadow Dynamics scheitert **identisch für
jedes Profil mit Life Path 4, 6 oder 7**. Von keinem Test erfasst (Tests nutzen
nur LP 1 & 9). Fällt unter „Regelabdeckung für alle unterstützten Lebenszahlen:
1–9 sowie 11, 22, 33".

## Fix

### 1. Knowledge — `rules.yaml`

- **Umlaut-Angleich:** `shadow_theme_a`/`shadow_theme_b` (und der Themenname im
  Prosatext) für die betroffenen Zeilen von `Rigiditaet`→`Rigidität`,
  `Ueberverantwortung`→`Überverantwortung`, `Rueckzug`→`Rückzug`. Die
  Theme-Keys müssen den `shadows[0]`-Strings der Quelldateien **exakt**
  entsprechen — die Zahl-Dateien sind die maßgebliche Quelle.
- **Master-Zahl-Abdeckung:** neue Zeilen für die 3 Master-Themen, gepaart mit
  allen 9 Basis-Themen (27), untereinander (Diagonale 3, Kreuz 3) → **+33
  Zeilen, gesamt 78**. Der Lookup ist mengenbasiert-symmetrisch, also je Paar
  genau eine Zeile.
- **Template-Text:** exakt der bereits im File etablierten, getemplateten Form
  folgen — nicht-diagonal: „Wenn die Neigung zu {A} bei der einen Seite auf die
  Neigung zu {B} bei der anderen Seite trifft, kann ein Muster entstehen, in dem
  beide Reaktionen sich wechselseitig verstärken, solange keine Seite die eigene
  Neigung bewusst reflektiert." + Deeskalation analog. Diagonal (gleiches Thema):
  „Wenn beide Seiten zu {A} neigen, kann sich dieses Muster gegenseitig
  verstärken: …". **Das ist Anwendung des vorhandenen Musters auf die bereits
  kuratierten Master-Themen, keine Bedeutungs-Neudefinition.** Master-Themen
  werden **nicht** auf 2/4/6 reduziert und bekommen **keine** generische
  Sammelregel.
- **`interaction_pattern_template_id`:** Schema fortführen —
  `pattern_11_<n>` / `pattern_22_<n>` / `pattern_33_<n>` (n = 1..9),
  `pattern_11_11` / `pattern_22_22` / `pattern_33_33`,
  `pattern_11_22` / `pattern_11_33` / `pattern_22_33`. Nur Label/Provenance-Ref,
  kein Template-Store.
- **Inhaltsreview** der 33 neuen Zeilen durch einen separaten Agenten
  (nicht-diagnostische Sprache, konsistent mit `shadow-dynamics-spec.md`,
  Provenance-Ableitung aus `master-numbers/*.yaml` nachvollziehbar).

### 2. Knowledge-Version

`knowledge/shadow-interaction/manifest.yaml` `version: 0.1.0` → `0.2.0`
(eigenständige Sub-System-Version, bestehende Konvention). Kein Checksum-
Mechanismus im Repo; kein Golden-Fixture für Shadow-Output (existiert nicht).

### 3. Engine — Validierung & saubere Fehler

- **Completeness-Test (der zentrale Regressionstest, zuerst RED):**
  `test_shadow_interaction_rules_cover_all_supported_life_path_pairs` —
  berechnet `shadows[0]` je Life Path {1..9, 11, 22, 33} aus den echten
  `knowledge/numbers` + `knowledge/master-numbers` Dateien und assertiert, dass
  **jedes** ungeordnete Paar (inkl. gleiche Zahl) **genau eine** Regel hat.
  Fängt sowohl den Umlaut-Bug als auch die Master-Lücke, und hält die Abdeckung
  künftig grün.
- **Runtime-Guard:** `assemble_shadow_context` wirft bei fehlender Regel statt
  `builtins.ValueError` einen `AnalysisGenerationError`
  (`errors.py`) → `run_shadow_dynamics_job` klassifiziert es als
  `ANALYSIS_GENERATION_ERROR` statt `UNEXPECTED_ERROR`. `retryable` bleibt
  `False` (permanente Wissenslücke). Kleiner, risikoarmer Wechsel; die FAILED-
  View im Frontend bleibt korrekt.
- `primary_shadow_theme` bleibt unverändert (liefert bereits den korrekten
  Master-Theme-String; `knowledge.number(22)` existiert dank
  `master-numbers/*.yaml`-Load).

### 4. A/B-Richtung absichern

- `list_workspace_members` (`repositories/workspaces.py:78-83`) bekommt ein
  deterministisches `ORDER BY joined_at, id` — beseitigt die nicht-deterministische
  Member-Reihenfolge, an der `user_a`/`user_b` hängt. Innerhalb einer
  Analyse-Zeile ist A/B ohnehin über eingefrorene `calculation_a/b_id` stabil;
  dieser Fix macht auch die *Zuweisung* stabil.
- **Test:** Pipeline mit `(profile_a, profile_b)` und `(profile_b, profile_a)` →
  `user_a_shadow_themes` / `user_b_shadow_themes` und die `canonical_refs`
  (`metric:a:…` / `metric:b:…`) vertauschen konsistent mit; keine
  Fehl-Attribution.

### 5. Tests

| Test | Ort | Zweck |
|---|---|---|
| Completeness (RED→GREEN) | `tests/unit/test_relationship_knowledge_loader.py` | alle 78 Paare gedeckt; `len(rules) == 78` |
| `primary_shadow_theme` LP 11/22/33 | `tests/unit/test_relationship_context.py` | liefert Master-Theme, nicht reduziert |
| `assemble_shadow_context` Master-Paar + LP-4/6/7-Paar | `tests/unit/test_relationship_context.py` | Regel wird aufgelöst |
| Missing rule → `AnalysisGenerationError` | dito | nicht mehr nacktes `ValueError` |
| A/B-Swap | `tests/unit/test_relationship_pipeline.py` | Themen/Refs korrekt vertauscht |
| Shadow-E2E Master-22 → COMPLETE | `apps/api/tests/integration/test_relationship_analysis.py` | Workaround-Override entfernen bzw. neuer Test; `_set_up_partner_workspace` ohne Master-Vermeidung |
| Shadow-Pipeline LP 11 & LP 33 → Erfolg | `packages/engine-relationship-interpretation/tests/…` bzw. integration | „zusätzlich Pipeline-/Integrationserfolg nachweisen" |
| FAILED-View separat | bereits vorhanden (`shadow-dynamics-view.test.tsx`) + neuer Backend-Test mit gezielt fehlender Regel via Monkeypatch | FAILED-Pfad bleibt geprüft |

Geburtsdaten: **LP 11 = 1960-01-03**, **LP 22 = 1986-07-18** (Lukas Springer),
**LP 33 = 1960-04-22** (per Engine verifiziert).

### 6. RC2

- `apps/web/e2e-system/rc2-two-account-journey.spec.ts` — der Shadow-Smoke wird
  **verschärft**: für die RC2-Fixture-Profile (Lukas 1986-07-18 = LP 22, Anna
  1990-03-14 = LP 9) muss Shadow jetzt **COMPLETE** erreichen. „COMPLETE oder
  FAILED" als Erfolgskriterium entfällt. Master-22 bleibt (nicht durch eine
  einfache Zahl ersetzen). Assertions: Person-A/B-Blöcke, Provenance, Footer,
  A/B-Zuordnung. Desktop **und** Mobile (Timeout entsprechend anheben bzw.
  Relationship-Analyse-Render auf Mobile schlanker halten).
- FAILED-View separat: eigener Playwright-Visual-Baseline-Fall bleibt (gemockt,
  gezielt ausgelöst) — nicht über echten Worker.

## Nicht in diesem PR

Kein Mock-Provider-Change (nur zur Verschönerung verboten). Kein Checksum-/
Knowledge-Drift-Mechanismus (Infrastruktur, eigenes Thema). Kein Relationship-
Type-Fallback (`generic_relationship_shadow.yaml` — PR-V2-05b).

## Mock- vs. echte-LLM-Qualität

Bleibt getrennt: RC2-Smoke + kuratierte Visual-Baselines = struktureller /
Layout-Nachweis; der Mock-Provider echot Grounding-Rohtext und ist **kein**
Prosa-Qualitätsnachweis. Diese Unterscheidung wird in den Nachweisen ausdrücklich
benannt.
