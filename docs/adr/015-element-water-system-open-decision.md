# ADR 015 — Element-/Wassersystem: offene Produktentscheidung, kein Canon bisher

## Status

**Accepted — 2026-09-25.** Entschieden durch den Produktverantwortlichen
(GoLukeEnviro), festgehalten als Operator-Entscheidung im Zuge der Wave-3-Abschluss-
Session. Ersetzt den vorherigen "Proposed"-Status; die Empfehlung aus diesem
Dokument (Option A) ist die getroffene Entscheidung.

## Context

Ein Element-/Wassersystem (z. B. eine Zuordnung von Zahlen oder Buchstaben zu den vier
klassischen Elementen Feuer/Wasser/Erde/Luft, oder ein eigenständiges "Wassersystem"
wie es in Teilen der numerologischen Breitenliteratur kursiert) wird von keiner
bestehenden NUMRA-Quelle referenziert:

- `specs/canon-spec.md` kennt kein Element-/Wassersystem, weder als `RESERVED_UNFROZEN`
  noch als `FEATURE_DISABLED_NO_CANON` (§33 listet nur Astrologie, Essence-Zahl,
  Planes of Expression, Transits und die Kompatibilitäts-Prozentzahl als unfrozen).
- Keine der bisherigen ADRs (001–014) erwähnt es.
- Das Vorgänger-Repo `numerology-analyst-agent` (`de-v2.json`/`de-v3.json`), die
  Quelle für die gesamte Wave-3-Content-Migration dieses Plans, enthält **keinerlei**
  Element- oder Wasser-Zuordnung — die Migration liefert hierfür kein Rohmaterial.
- `packages/engine-numerology` implementiert kein Element-System; es gibt keine
  bestehende Berechnungslogik, an die ein solches System andocken könnte.

Das bindende Grundprinzip aus `PROJECT_CHARTER.md` ("Determinismus vor LLM", keine
erfundenen Daten) und ADR 006 ("NUMRA DOES NOT GUESS") gelten hier genauso: Ein
Element-System bräuchte eine explizite, nachvollziehbare Zuordnungsregel mit
Provenienz (welche Tradition, welche Quelle) — es kann nicht plausibel aus dem
bestehenden Zahlenschema abgeleitet werden, ohne eine Methode zu erfinden.

## Die offene Frage

**Wird ein Element-/Wassersystem für NUMRA überhaupt gewollt, und wenn ja, mit
welchem Produktzweck?** Das ist keine technische Entscheidung — es gibt keinen
bestehenden Code oder Content, der sie präjudiziert. Drei Optionen:

### Option A — Nicht bauen, explizit als `FEATURE_DISABLED_NO_CANON` markieren

Ein neuer `specs/canon-spec.md`-Abschnitt (analog zu §32 Astrologie) hält fest: kein
Element-/Wassersystem in NUMRA v1, keine Platzhalter-UI, kein reserviertes Interface.
Aufwand: minimal (ein Canon-Spec-Absatz). Vorteil: verhindert, dass ein späterer
Beitragender oder ein LLM-Agent "einfach mal schnell" eine plausibel klingende
Zuordnung nachträgt, ohne dass je eine Quelle geprüft wurde — genau das Risiko, das
ADR 006 für Astrologie/Kompatibilitäts-Prozent bereits benennt.

### Option B — Recherche + eigene, versionierte Canon-Spec, dann Implementierung

Wie im ursprünglichen Plan skizziert: zunächst eine dedizierte Recherche, welche
Tradition(en) ein Element-/Wassersystem tragen, mit welcher Provenienz und welcher
Zuordnungslogik (Zuordnungsregeln, Umgang mit Mehrfachzuordnungen, Claim-
Klassifizierung nach dem Sechs-Klassen-Schema aus `numerology-analyst-agent`).
Danach eine eigene Canon-Spec mit derselben Sorgfalt wie `specs/canon-spec.md`, erst
danach Implementierung. Aufwand: groß (mehrere Tage Recherche + Spec-Arbeit,
danach Knowledge-Content + Engine-Erweiterung + Tests). Setzt voraus, dass ein
konkreter Produktzweck existiert (welches Nutzerbedürfnis löst das System, das die
bestehenden Metriken nicht schon abdecken).

### Option C — `RESERVED_UNFROZEN`-Interface, ohne Werte

Ein typisiertes Interface (analog zu `AstrologyEngineInterface.compute()` aus ADR 006),
das `NotImplementedError` wirft, plus eine `RESERVED_UNFROZEN`-Markierung im Canon-Spec.
Signalisiert Bereitschaft für später, ohne heute eine Methode zu erfinden oder zu
implementieren. Aufwand: klein (ein Interface, ein Canon-Spec-Absatz).

## Empfehlung

**Option A**, mit der Möglichkeit, später zu C zu wechseln, falls ein konkreter
Produktzweck entsteht. Begründung: Es gibt aktuell keinen belegten Nutzerbedarf, keine
Quelle und keinen Produktzweck für dieses Feature — nur die allgemeine Beobachtung,
dass Element-/Wassersysteme in Teilen der numerologischen Breitenliteratur existieren.
Ohne einen konkreten Zweck würde selbst ein `RESERVED_UNFROZEN`-Interface (Option C)
eine Erwartung wecken, die niemand eingelöst hat. Option A hält die Tür offen (der
Canon-Spec-Absatz lässt sich jederzeit von `FEATURE_DISABLED_NO_CANON` auf
`RESERVED_UNFROZEN` oder eine echte Spec hochstufen), ohne heute Aufwand in eine
Richtung zu stecken, die noch niemand angefordert hat.

## Decision

**Option A.** Ein Element-/Wassersystem wird nicht gebaut. Es ist
`FEATURE_DISABLED_NO_CANON` (siehe `specs/canon-spec.md` §33) — kein Interface, keine
eigene Canon-Spec, keine Knowledge-Dateien, keine Engine-Arbeit, keine Platzhalter-UI.

Diese Entscheidung gilt, bis der Produktverantwortliche sie schriftlich revidiert.
Eine Revision braucht eine **neue** ADR mit einer verifizierten Quelle und einem
belegten Produktzweck — nicht das Wiederbeleben dieses Dokuments als Bauplan. Eine
vage Beobachtung aus der numerologischen Breitenliteratur ist keine Revision.

Die Optionen B und C bleiben oben als dokumentierte Alternativen stehen, falls eine
spätere Revision sie erneut abwägen will — sie sind nicht gewählt.

## Consequences

- Es entsteht **kein** Code, kein Knowledge-Content und keine weitere Canon-Spec-
  Änderung zu diesem Thema über den einen Satz in §33 hinaus (entspricht der
  expliziten Migrationsplan-Vorgabe, Phase 4 nicht opportunistisch mitzuziehen).
- `specs/canon-spec.md` §33 erhält einen datierten Satz, der Element-/Wassersystem
  explizit als `FEATURE_DISABLED_NO_CANON` listet (nicht `RESERVED_UNFROZEN`, kein
  Interface) — siehe den begleitenden Canon-Spec-PR.
- Eine spätere Umkehr zu Option B oder C erfordert eine neue ADR mit Quelle und
  Produktzweck, kein Wiedereröffnen dieses Dokuments.
