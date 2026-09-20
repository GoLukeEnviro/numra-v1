# NUMRA — Überwachung und Alarmierung auf Agent0

Stand: 2026-09-20. Rollen und Pfade: `docs/ops/numra-topology.md`.

## Was überwacht wird

`numra-healthcheck.timer` startet alle fünf Minuten `numra-healthcheck.service`, das
`/usr/local/bin/numra-healthcheck.sh` ausführt (Quelle im Repo:
`scripts/ops/numra-healthcheck.sh`). Der Lauf prüft:

| Prüfung | Kriterium | Wirkung |
|---|---|---|
| Readiness Produktion | `GET 127.0.0.1:17800/v1/health/ready` liefert `status=healthy` | Fehlschlag → Alarm |
| Readiness Audit | `GET 127.0.0.1:17801/v1/health/ready` liefert `status=healthy` | Fehlschlag → Alarm |
| Frische der Sicherung | jüngster `numra-*.dump` jünger als 26 h | Fehlschlag → Alarm |
| Fehlgeschlagene Jobs | Anzahl `report_jobs`/`analysis_jobs` mit `status=FAILED`, je Stack | nur Zahl im Statusfile, kein Alarm |

Der Lauf schreibt `/var/lib/numra/health-status.json`, z. B.:

```json
{"checked_at":"2026-09-20T07:30:10Z",
 "prod_readiness":"healthy","prod_payload":{...},
 "audit_readiness":"healthy","audit_payload":{...},
 "backup_age_seconds":22411,"backup_file":"numra-20260920T011605Z.dump",
 "prod_failed_jobs":"10/0","audit_failed_jobs":"0/0",
 "failures":[]}
```

## Wie der Alarm sichtbar wird

Es gibt **keinen externen Pager** und bewusst keinen Zugangsdaten-Zugriff aus dem
Probe-Skript. Der Alarm ist damit:

```bash
systemctl --failed                     # zeigt numra-healthcheck.service
journalctl -u numra-healthcheck.service -n 20
cat /var/lib/numra/health-status.json  # "failures":[...]
```

Der Dienst läuft als Benutzer `hermes`. Dafür darf die Gruppe `hermes` das
Sicherungsverzeichnis **auflisten** (`0750 root:hermes`), die Dump-Inhalte bleiben
root-only — die Frischeprüfung braucht nur den Dateinamen, keinen Inhalt.

## Interpretation

- `*_readiness` prüft die komplette Abhängigkeitskette, weil `/v1/health/ready` selbst
  Datenbank, Numerologie-Engine, LLM-Provider und PDF-Dienst meldet. Ein `unhealthy`
  dort heißt: der Stack kann Nutzeranfragen nicht vollständig bedienen.
- `backup_age_seconds > 93600` (26 h) fängt beides: einen kaputten `pg_dump` und einen
  nicht gelaufenen Timer. Ein einzelner verpasster Tag ist damit noch kein Alarm, ein
  zweiter ist einer.
- `*_failed_jobs` ist eine **Zahl, kein Alarm**: zum Abnahmetag stehen in Produktion
  10 historische Fehlschläge aus der Entwicklung (2026-08-20 bis 2026-09-16, überwiegend
  Provider-Timeouts und Validierungsfehler). Relevant ist die Entwicklung dieser Zahl,
  nicht ihr Absolutwert — sie wird deshalb nur fortgeschrieben.
- Die Audit-Instanz läuft absichtlich im selben Timer: ihr Ausfall ist für den Betrieb
  kein Notfall, soll aber sichtbar sein, solange sie die Abnahmeumgebung ist.

## Bewusste Grenzen

- Kein Alarmkanal nach außen (E-Mail/Push). Ein solcher Kanal gehört an einen
  Messaging-Anbieter und damit an eine Zugangsdaten-Entscheidung des Betreibers; das
  Skript bleibt deshalb zugangsfrei.
- Keine Historie/kein Trend: der Statusfile ist ein Zustandsschnappschuss, die Historie
  liegt im Journal.
- Keine automatische Reparatur. Der Lauf beobachtet nur — ein Neustart von Containern
  oder ein Zurückspielen von Sicherungen bleibt ein bewusster Eingriff.
