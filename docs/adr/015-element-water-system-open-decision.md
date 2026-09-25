# ADR 015 — Element-/Wassersystem: offene Produktentscheidung, kein Canon bisher

## Status

**Proposed — wartet auf Produktentscheidung.** Anders als die übrigen ADRs in diesem
Verzeichnis dokumentiert dieses keine bereits getroffene Entscheidung, sondern legt
die Frage bewusst einem Menschen vor, bevor irgendein Code oder Knowledge-Inhalt
entsteht (Phase 4 des Migrationsplans "NUMRA v1 — Vertragslücken schließen +
Deutungstiefe aus dem Vorgänger-Repo migrieren").

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

_Offen — wartet auf Rückmeldung des Produktverantwortlichen (A, B oder C)._

## Consequences

- Bis zur Entscheidung entsteht **kein** Code, kein Knowledge-Content und keine
  weitere Canon-Spec-Änderung zu diesem Thema (entspricht der expliziten
  Migrationsplan-Vorgabe, Phase 4 nicht opportunistisch während Wave 3 mitzuziehen).
- Wird Option A gewählt, folgt ein kleiner Canon-Spec-PR (ein neuer `FEATURE_DISABLED_
  NO_CANON`-Abschnitt, analog zu §32), keine weiteren Schritte.
- Wird Option B gewählt, ist der nächste Schritt eine eigene Recherche-Phase
  (Quellenlage, Provenienz, Zuordnungslogik) vor jeglicher Implementierung.
- Wird Option C gewählt, folgt ein kleiner Interface-PR analog zu
  `AstrologyEngineInterface`.
