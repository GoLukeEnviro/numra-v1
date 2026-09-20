# NUMRA — Überwachung und Alarmierung auf Agent0

Stand: 2026-09-20. Rollen und Pfade: `docs/ops/numra-topology.md`.

## Was überwacht wird

`numra-healthcheck.timer` startet alle fünf Minuten `numra-healthcheck.service`, das
`/usr/local/bin/numra-healthcheck.sh` ausführt (Quelle im Repo:
`scripts/ops/numra-healthcheck.sh`). Der Lauf prüft:

| Prüfung | Kriterium | Wirkung |
|---|---|---|
| Readiness Produktion | `GET 127.0.0.1:17800/v1/health/ready` liefert `status=healthy` | Fehlschlag → Alarm |
| Readiness Audit | `GET 127.0.0.1:17801/v1/health/ready` liefert `status=healthy` — nur solange konfiguriert | Fehlschlag → Alarm |
| Job-Lesbarkeit | die Jobzählung des jeweiligen Stacks ist lesbar (Container + DB erreichbar) | **nicht lesbar → Alarm** |
| Neue Jobfehler | `report_jobs`/`analysis_jobs` mit `status=FAILED`: **Zuwachs seit dem letzten Lauf** | Zuwachs > 0 → Alarm |
| Frische der Sicherung | jüngster `numra-*.dump` jünger als 26 h | Fehlschlag → Alarm |

Die Readiness-Antwort deckt Datenbank, Numerologie-Engine, LLM-Provider und PDF-Dienst
bereits mit ab; Einzelprüfungen dafür sind deshalb nicht nötig.

## Alarmregeln im Detail

**Neue Jobfehler, nicht der Bestand.** Gemeldet wird die *Differenz* zum vorherigen Lauf
(`prod_new_failed_jobs`), nicht die absolute Zahl. Grund: in Produktion stehen zehn
historische Fehlschläge aus der Entwicklung (2026-08-20 bis 2026-09-16, überwiegend
Provider-Timeouts und Validierungsfehler, alle älter als 24 h). Eine absolute Schwelle
würde alle fünf Minuten alarmieren, bis jemand die Altlast löscht — und damit genau das
Signal erzeugen, das man ignoriert. Der Zuwachs dagegen ist ein echtes Ereignis.

Fehlt eine vorherige Messung (erster Lauf, Statusfile zurückgesetzt, vorheriger Lauf
konnte die DB nicht lesen), greift als Rückfall die **24-Stunden-Zählung**
(`*_failed_jobs_24h`): dann alarmiert jeder Fehlschlag der letzten 24 h. Zeitfenster und
Schwelle sind damit beide dokumentiert und beide im Statusfile sichtbar.

**Nicht lesbare Jobzählung ist ein Fehler, keine Lücke.** Ist der Postgres-Container
nicht erreichbar, kann die Pipeline nicht bewertet werden — ein solcher Zustand darf
nicht als „keine Fehler" durchgehen. Er wird als `job(s)_unreadable` alarmiert.

**Readiness `unhealthy` oder nicht erreichbar** → Alarm (`readiness_unreachable` bzw.
`readiness_<status>`).

**Sicherung älter als 26 h** → Alarm. Das fängt beides: einen kaputten `pg_dump` und
einen nicht gelaufenen Timer. Ein einzelner verpasster Tag ist damit noch kein Alarm,
ein zweiter ist einer.

## Konfiguration und Teardown

`/etc/numra/healthcheck.env` (keine Secrets, 0644) steuert die Prüfziele:

```bash
PROD_READY_URL=http://127.0.0.1:17800/v1/health/ready
PROD_DB_CONTAINER=numra-prod-postgres-1
AUDIT_READY_URL=http://127.0.0.1:17801/v1/health/ready
AUDIT_DB_CONTAINER=numra-audit-postgres-1
```

Fehlt die Datei oder eine Zeile, gelten genau diese Vorgaben (der Produktions-Stack wird
also immer geprüft).

**PWA-10-Teardown:** `AUDIT_READY_URL=` auf einen leeren Wert setzen. Der Lauf prüft den
Audit-Stack dann nicht mehr (`audit_readiness: "not_configured"`, keine Jobabfrage) —
sonst bliebe nach dem Entfernen des Stacks dauerhaft eine fehlgeschlagene Unit zurück.

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

## Bewusste Grenzen

- Kein Alarmkanal nach außen (E-Mail/Push). Ein solcher Kanal gehört an einen
  Messaging-Anbieter und damit an eine Zugangsdaten-Entscheidung des Betreibers; das
  Skript bleibt deshalb zugangsfrei. Sobald SMTP existiert (PWA-05), ist ein
  `OnFailure=`-Versand die naheliegende Ergänzung.
- Keine Historie/kein Trend: der Statusfile ist ein Zustandsschnappschuss, die Historie
  liegt im Journal. Der Zuwachsvergleich nutzt genau eine vorherige Messung.
- Keine automatische Reparatur. Der Lauf beobachtet nur — ein Neustart von Containern
  oder ein Zurückspielen von Sicherungen bleibt ein bewusster Eingriff.
- `worker` und `analysis-worker` haben im Compose **keinen** Healthcheck (nur
  `restart: unless-stopped`). Der Probe merkt einen stehenden Worker nur indirekt: über
  liegen bleibende QUEUED-Jobs ist er nicht sichtbar, über neue FAILED-Jobs erst, wenn
  der Job das Retry-Budget verbraucht hat. Ein `restart: unless-stopped`-Container ohne
  Healthcheck wird von Docker auch dann nicht neu gestartet, wenn der Prozess zwar lebt,
  aber nichts mehr abarbeitet.
