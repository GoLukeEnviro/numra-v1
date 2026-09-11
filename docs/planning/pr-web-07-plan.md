# PR-WEB-07 — Shared Tasks UI

Basis: `main` @ `4a72bc207dc170c377e59220bb031556530dac63`.

## Umfang

- Relationship-Workspace-Route `/workspaces/{id}/tasks`, eigener Tab und Hub-Link.
- Vollständig paginierte Aufgabenliste über den vorhandenen PR-V2-07-Contract.
- `JOINT_SHARED` wird bewusst als sofort aktive gemeinsame Aufgabe angelegt.
- `FOR_PARTNER_PROPOSED` wird als ausstehender Vorschlag angelegt; nur der
  serverseitig bestimmte Empfänger erhält Annehmen/Ablehnen-Aktionen.
- `AVENYTH_SUGGESTED` wird mit Herkunftstyp angezeigt und bleibt bis zu einer
  ausdrücklichen Annahme vorgeschlagen.
- Aktive Aufgaben können über den serverseitigen Zustandsübergang abgeschlossen
  oder archiviert werden; erledigte Aufgaben erhalten einen eigenen Abschnitt.
- Aufgelöste Workspaces zeigen erhaltene Aufgaben ausschließlich lesend.
- Deutsche und englische Texte, Phase-disabled-/Fehler-/Leerzustände.

## Grenzen

`PERSONAL_PRIVATE` bleibt in der persönlichen Workspace-Oberfläche und wird nie
in Relationship-Workspace-Listen gemischt. Roadmap-Verknüpfungen und eine
Roadmap-Auswahl gehören zu WEB-08. Es werden keine neuen Backend-Routen, Scores,
LLM-Aufrufe oder Produktionsflags eingeführt.

## Nachweise

- Komponentenregressionen für Erstellen, Rollenaufteilung, Abschluss und
  DISSOLVED.
- visuelle Zustände auf 1440×900 und 390×844.
- echte Zwei-Konten-RC2-Journey: Vorschlag A → B, Annahme durch B, ACTIVE für
  beide und read-only nach Auflösung.
- vollständige Web-Suite, Lint, Typecheck, Produktionsbuild sowie Required CI.
