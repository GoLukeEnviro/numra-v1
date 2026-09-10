# WEB-06b — finaler Frontend-Umfang auf dem WEB-06a-Backend

Stand: WEB-06a gemergt und Post-Merge-CI erfolgreich; keine 06b-Implementierung.
Umsetzungsbasis: PR #53, geprüfter Merge-Commit `16d7e1a9cc33764af7180365fc80d86a4377f32b`.

## Oberfläche und Navigation

Check-in-Tab im Relationship-Workspace und dedizierte Check-in-Ansicht. Vorhandene
Workspace-/Feature-Flag-Gates verwenden. Deutsch und Mobile/Desktop gleichwertig.
Alle Zustände: Laden, leer, Fehler, Feature deaktiviert, ACTIVE, DISSOLVED/read-only.

## Vollständige Journey

1. Ohne Runde (`GET /checkins/current` → null): Fragenkonfiguration anzeigen und
   ausdrücklichen Start mit Bestätigung anbieten. `startRound(workspaceId, key)`
   verwenden; Key bis zur geklärten Antwort stabil behalten, auch nach Timeout/Retry.
2. Offene Runde: ausschließlich deren `dimensions`-Snapshot als Fragenbasis nehmen,
   niemals das inzwischen abrufbare aktive Template. Alle Skalen/Pflichtfelder aus
   Backend-Daten. Genau eine Integer-Antwort pro Dimension, keine Teilabgabe.
3. Submit mit `round_id` und stabilem Idempotency-Key. Bei unklarem Netzwerkergebnis
   denselben Versuch wiederholen bzw. Current neu laden. Bei fachlich neuem Versuch
   neuer Key. Keine implizite neue Runde und keine Browser-Analyseberechnung.
4. Wartezustände anhand eigener Antworten und `partner_submitted`: niemand hat
   abgegeben, ich warte auf Partner, Partner wartet auf mich. Abgegebene Antworten
   append-only/read-only; bei 409 kein Überschreiben oder Verlust der eigenen Abgabe.
   Current beim Wiederöffnen/Fokus und über eine Aktualisierungsmöglichkeit neu laden,
   damit eine inzwischen erfolgte Partner-Abgabe zu ANALYZED führt; kein Backend-Push.
5. ANALYZED: alle sechs abgeleiteten Felder anzeigen; direction zeitlich lokalisieren
   (Annäherung/Divergenz/stabil/keine Vordaten), niemals als „wer höher bewertet“.
   `sufficient_evidence=false` und sample_size sichtbar erklären; kein Score,
   Prozentwert, Kompatibilitätsurteil oder diagnostisches Label.
   `historical_delta=null` als „noch nicht verfügbar“ anzeigen, niemals als `0`.
6. Neue Runde nach Abschluss nur durch erneuten ausdrücklichen Start. Ein Replay
   des vorherigen Start-Keys zeigt dessen alte Runde, startet also nichts Neues.

## Konfiguration

Custom-Dimension erstellen, Label/Beschreibung bearbeiten, deaktivieren/reaktivieren.
Semantic-Key-Identität erklären: Bedeutungsänderung erfordert neuen Key. INTIMATE-
Klasse beim Erstellen bewusst auswählbar; bekannte sexual_connection-Klassifikation
wird vom Server erzwungen. Server erkennt freie unklassifizierte Texte nicht.

Während offener Runde keine Config-Aktionen oder tatsächlichen Relationship-Type-
Wechsel anbieten; `CHECKIN_ROUND_OPEN` trotzdem als serverseitigen Konflikt behandeln.
Dissolve bleibt verfügbar. DISSOLVED ausschließlich lesen; kein Start, Submit,
Config oder POST-Retry. DISSOLVED ohne bisheriges Template: Template-GET 404 zusammen
mit Current null als leere historische Ansicht behandeln; nicht pauschal als fehlende
Workspace-Berechtigung ausgeben. Keine zusätzliche Versionierungsoberfläche: Versionswechsel
werden automatisch vom Backend erzeugt. Nach Mutationen aktuelle Template-Daten/IDs
neu laden, auch wenn ein PATCH auf eine ältere ID akzeptiert wurde.

## Historie und ehrliche Herkunft

Listen-/Detail-API verwenden, paginieren und Detailanalyse bei Bedarf nachladen.
Trends streng nach `(semantic_key, checkin_template_version)` segmentieren; historische
Templates bei Bedarf über `?version=N`. Keine Mittelung über Versionen und keine
Neuberechnung von gap/trend/delta im Browser.

- `ROUND_START`: gespeicherte Originalfragen dieser Runde anzeigen.
- `MIGRATION_CURRENT`: Fragen wurden erst bei Migration festgehalten; sichtbarer
  Herkunftshinweis, keine Behauptung über früher tatsächlich gesehene Texte.
- `LEGACY_MISSING`: keine erfundenen Labels/Beschreibungen; vorhandene Analyse über
  semantic_key und Hinweis auf fehlende historische Dimensionsdetails anzeigen.

Privacy-Text verspricht keine vollständige Geheimhaltung der Partnerwerte:
Rohantworten sind nicht direkt verfügbar, aus eigenem Wert und absolute_gap können
aber Kandidatenwerte abgeleitet werden (akzeptierter bestehender Trade-off).

## Fehlerverhalten

422: fehlende/doppelte/fremde Antworten, Skala, leere Dimensionen, INTIMATE-Restriktion
oder ungültiger Request. 409: offene/falsche Runde, schon abgegeben, Key mit anderem
Payload, unveränderliche Identität oder DISSOLVED. 404: fehlende Ressource/Berechtigung.
Servercodes gezielt lokalisieren, Antwortwerte nicht in Diagnose-/Telemetry-Ausgaben.
Bei `CHECKIN_IDEMPOTENCY_CONFLICT` keine automatische Wiederholung mit neuem Key.

## Verbindliche Prüfungen

- Vitest: Config, alle Runden-/Warte-/Ergebniszustände, stabile Retry-Keys, vollständige
  Antworten, Range, Konflikte, DISSOLVED, Flag deaktiviert, Herkunft und Trend-Versionen.
- Kuratierte visuelle Baselines für 1440×900 und 390×844 einschließlich leerer Ansicht,
  Config-Lock, Formular, beiden Wartezuständen, Ergebnis mit/ohne ausreichende Evidenz,
  Historie und DISSOLVED. Catalog-Parity und Accessibility der Formulare prüfen.
- Vollständige reale RC2-Journey auf **beiden** Viewports mit zwei separaten Konten:
  A startet und gibt über UI ab → Wartezustand → B gibt über UI ab → ANALYZED →
  Ergebnis/Historie korrekt. Check-in-Berechnung ist deterministisch; Mock-LLM sagt
  hier nichts über Textqualität aus und ist für die Berechnung nicht zuständig.
- Privacy feld-/herkunftsbasiert auf API-Ebene: my_responses ausschließlich vom
  Aufrufer, genau sechs erlaubte Analysefelder, partner_submitted nur Bool, kein
  Partner-Rohwertfeld. Keine pauschale DOM-Suche nach einzelnen Zahlen.
- Doppel-/Parallel-Submit, Retry nach unklarer Response, Config-/Typkonflikt und
  Dissolve während der Journey; keine verlorenen lokalen Eingaben bei Fehlern.
- Alle zwölf Required Checks, unabhängiges Review, PR-CI und getrennte Post-Merge-CI,
  aktualisierter Execution-State und WEB-06b-Evidence.

Nicht enthalten: Scheduler/Kadenz, neue Scopes/Entitlements, neue Scores, semantische
Textklassifikation, Versionsmanagement-UI, Legacy-Archiv-Migration, Deployment oder
Aktivierung neuer Produktionsflags. Backend-Lücken nur bei konkret bewiesenem Befund
separat behandeln; abgeschlossene RC2-/Shadow-Arbeiten nicht erneut aufrollen.
