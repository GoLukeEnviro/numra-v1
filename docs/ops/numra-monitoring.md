# NUMRA — Überwachung und Alarmierung auf Agent0

Stand: 2026-10-05. Rollen und Pfade: `docs/ops/numra-topology.md`.

## Was überwacht wird

`numra-healthcheck.timer` startet alle fünf Minuten `numra-healthcheck.service`, das
`/usr/local/bin/numra-healthcheck.sh` ausführt (Quelle im Repo:
`scripts/ops/numra-healthcheck.sh`). Der Lauf prüft:

| Prüfung | Kriterium | Wirkung |
|---|---|---|
| Readiness Produktion | `GET 127.0.0.1:17800/v1/health/ready`: Gesamtstatus und je Dienst (`database`, `numerology_engine`, `llm`, `pdf`) gegen `EXPECTED_DEPENDENCIES` | siehe „Alarmsemantik pro Dienst“ |
| Readiness Audit | `GET 127.0.0.1:17801/v1/health/ready`, gleiche Bewertung — nur solange konfiguriert | siehe oben |
| Job-Lesbarkeit | die Jobzählung des jeweiligen Stacks ist lesbar (Container + DB erreichbar) | **nicht lesbar → Alarm** |
| Neue Jobfehler | `report_jobs`/`analysis_jobs` mit `status=FAILED`: **Zuwachs seit dem letzten Lauf** | Zuwachs > 0 → Alarm |
| Hängende Jobs | `QUEUED` länger als `STALE_QUEUED_MINUTES` (15) in `report_jobs`/`analysis_jobs` | > 0 → Alarm |
| Frische der Sicherung | jüngster `numra-*.dump` jünger als 26 h | Fehlschlag → Alarm |

Die Readiness-Antwort deckt Datenbank, Numerologie-Engine, LLM-Provider und PDF-Dienst
ab.

**Statuscode des Endpunkts:** `GET /v1/health/ready` antwortet nur dann mit **HTTP 503**,
wenn die Datenbank `unhealthy` ist (Gesamtstatus `unhealthy`). Sonst ist es **HTTP 200**:
`unhealthy` bei `llm`, `pdf` oder `numerology_engine` sowie `degraded`/`disabled` ändern den
Statuscode nicht. Der Body enthält in beiden Fällen alle Dienstdetails, auch auf dem
TTL-Cache-Pfad.

Der Monitor liest den JSON-Body bei **HTTP 200 und 503** (kein `curl -f`): ein 503
trägt genau die Dienstdetails, die für die Bewertung nötig sind. Andere HTTP-Codes
(404, 500, …) zählen als Fehlschlag des Endpunkts.

## Alarmsemantik pro Dienst

Soll-Zustand je Dienst in `healthcheck.env`. **Nur ein Beispiel** — der Ist-Stand von
Produktion und Audit (`curl -s http://127.0.0.1:17800/v1/health/ready`, `…:17801…`) muss
vor dem Rollout geprüft werden. Meldet ein Dienst z. B. `llm=healthy`, alarmiert
`llm=optional-disabled` sofort als Konfigurationsabweichung:

```bash
# BEISPIEL, nicht blind übernehmen:
EXPECTED_DEPENDENCIES="database=required numerology_engine=required llm=optional-disabled pdf=required"
FAIL_THRESHOLD=3
```

`EXPECTED_DEPENDENCIES` gilt **global für Produktion und Audit** gleichermaßen. Dienstnamen
bestehen aus `[a-z0-9_]`; ein Tippfehler (`pdf=reqired`), ein unbekannter Wert oder ein
doppelter Eintrag wird als `config:invalid_expectation_<eintrag>` gemeldet (Alarm, Exit 1)
und nicht stillschweigend ignoriert.

`required` = der Dienst muss laufen, `optional-disabled` = der Dienst ist bewusst
abgeschaltet und muss `disabled` melden. Dienste, die nicht aufgeführt sind, werden nicht
einzeln bewertet; ist `EXPECTED_DEPENDENCIES` leer oder fehlt es, zählt nur der
Gesamtstatus.

| Lage | Bewertung | Wirkung |
|---|---|---|
| `optional-disabled` meldet `disabled` | erwartet | kein Alarm |
| `required` meldet `disabled`, oder `optional-disabled` meldet etwas anderes | **Konfigurationsabweichung** | sofort Alarm (`config_deviation`), nie unterdrückt |
| `degraded`, oder Fehlschläge unter dem Schwellwert N | vorübergehend beeinträchtigt | Warnung im Statusfile (`warnings`), Exit 0 |
| `unhealthy` (oder unbekannter Wert) in ≥ N aufeinanderfolgenden Läufen | ausgefallen | Alarm |
| Endpunkt fehlerhaft: nicht erreichbar, kein/ungültiges JSON, Feld `status` fehlt, HTTP-Code ≠ 200/503 | Fehlschlag des Endpunkts | zählt in den Zähler `readiness` ein, Alarm ab N |
| Gesamtstatus `unhealthy`, ohne dass ein Dienst es erklärt | Fehlschlag des Endpunkts | wie oben |

**Zähler.** Je Stack und Dienst steht ein Zähler im Statusfile
(`prod_fail_count_pdf`, `prod_fail_count_readiness`, …). Er bleibt zwischen den
Timerläufen erhalten, steigt bei jedem Fehlschlag und fällt bei der ersten erfolgreichen
Prüfung auf 0 zurück. Diese Rückkehr wird einmalig als Entwarnung gemeldet
(`recoveries` im Statusfile, `RECOVERED` auf stdout/Journal). Fällt der Endpunkt aus,
bleiben die Dienstzähler unverändert erhalten. „In Folge“ heißt: `degraded` setzt einen
Zähler weder zurück noch hoch, die Folge unhealthy, unhealthy, degraded, unhealthy
alarmiert also erst im 4. Lauf. Nur ein gesunder Lauf setzt auf 0.

**Bewusste Verhaltensänderung:** Ein Datenbankausfall (`database=unhealthy` im Body,
Gesamtstatus `unhealthy`) wird erst im dritten Lauf alarmiert, also nach etwa 10–15
Minuten statt wie früher sofort. Fällt dagegen der Postgres-Container weg, schlägt die
Jobabfrage fehl und `jobs_unreadable` alarmiert weiterhin sofort im ersten Lauf.

**Statusfile.** Es wird atomar geschrieben (Temp-Datei im selben Verzeichnis, dann
Umbenennen). Ist es nicht schreibbar, wird das als eigener Alarm `status:file_unwritable`
gemeldet (Exit 1): ohne Statusfile gingen die Zähler verloren und der Schwellwert-Alarm
könnte nie auslösen. Der Modus ist unabhängig von der umask 0644. In Meldungen und im Statusfile erscheinen nur
druckbare ASCII-Zeichen; Steuerzeichen und ungültige UTF-8-Bytes aus der Konfiguration
werden verworfen, damit der Statusfile immer gültiges JSON bleibt. Die Konfigurationsdatei
wird als Shell-Code eingelesen und darf keinen `EXIT`-Trap setzen (das Skript setzt
seinen eigenen für das Aufräumen der Temp-Datei). Ein fehlendes, leeres oder korruptes
vorheriges Statusfile zählt als
„keine Vorwerte“ (Zähler bei 0) und wird neu geschrieben.

**Schwellwert N = 3.** Bei fünf Minuten Timer-Intervall (OnUnitActiveSec=5min) fällt der Alarm im dritten fehlgeschlagenen Lauf, also etwa 10 Minuten nach dem ersten Fehlschlag. Mit Timer-Jitter (AccuracySec=30s) und Laufzeit bleibt die maximale Erkennungszeit **≤ 15 Minuten**. Ein einzelner Aussetzer (Neustart eines Containers, kurzer Timeout) erzeugt nur eine Warnung. FAIL_THRESHOLD ist anpassbar; ein ungültiger Wert fällt auf 3 zurück.

## Weitere Alarmregeln

**Neue Jobfehler, nicht der Bestand.** Gemeldet wird die *Differenz* zum vorherigen Lauf
(`prod_new_failed_jobs`), nicht die absolute Zahl. Grund: in Produktion stehen zehn
historische Fehlschläge aus der Entwicklung (2026-08-20 bis 2026-09-16, überwiegend
Provider-Timeouts und Validierungsfehler, alle älter als 24 h). Eine absolute Schwelle
würde alle fünf Minuten alarmieren, bis jemand die Altlast löscht — und damit genau das
Signal erzeugen, das man ignoriert. Der Zuwachs dagegen ist ein echtes Ereignis.

Fehlt eine vorherige Messung (erster Lauf, Statusfile zurückgesetzt, vorheriger Lauf
konnte die DB nicht lesen), greift als Rückfall die **24-Stunden-Zählung**
(`*_failed_jobs_24h`): dann alarmiert jeder Fehlschlag der letzten 24 h. Die Zählung
umfasst **Report- und Analysefehler** (`report_jobs` + `analysis_jobs`). Zeitfenster und
Schwelle sind damit beide dokumentiert und beide im Statusfile sichtbar; die Felder
`*_stale_queued` stehen ebenfalls im Statusfile.

**Nicht lesbare Jobzählung ist ein Fehler, keine Lücke.** Ist der Postgres-Container
nicht erreichbar, kann die Pipeline nicht bewertet werden — ein solcher Zustand darf
nicht als „keine Fehler" durchgehen. Er wird als `jobs_unreadable` alarmiert.

**Sicherung älter als 26 h** → Alarm. Das fängt beides: einen kaputten `pg_dump` und
einen nicht gelaufenen Timer. Ein einzelner verpasster Tag ist damit noch kein Alarm,
ein zweiter ist einer.

## Konfiguration und Teardown

`/etc/numra/healthcheck.env` (keine Secrets, 0644) steuert die Prüfziele und den
Soll-Zustand:

```bash
PROD_READY_URL=http://127.0.0.1:17800/v1/health/ready
PROD_DB_CONTAINER=numra-prod-postgres-1
AUDIT_READY_URL=http://127.0.0.1:17801/v1/health/ready
AUDIT_DB_CONTAINER=numra-audit-postgres-1
# Beispielwerte: Soll-Zustand vor dem Rollout gegen den Ist-Stand prüfen (gilt für Prod und Audit)
EXPECTED_DEPENDENCIES="database=required numerology_engine=required llm=optional-disabled pdf=required"
FAIL_THRESHOLD=3
```

Fehlt die Datei oder eine Zeile, gelten die Vorgaben (der Produktions-Stack wird also
immer geprüft; ohne `EXPECTED_DEPENDENCIES` zählt nur der Gesamtstatus, `FAIL_THRESHOLD`
ist 3). Der Soll-Zustand muss zum tatsächlichen Betrieb passen: wird ein Dienst bewusst
aktiviert oder abgeschaltet, ist `EXPECTED_DEPENDENCIES` mitzuändern — bis dahin meldet
der Monitor die Abweichung, statt sie zu unterdrücken.

Für Tests und Dry-Runs lassen sich `CONFIG_FILE`, `STATUS_FILE`, `BACKUP_DIR` und
`BACKUP_MAX_AGE_SECONDS` über die Umgebung setzen; die Konfigdatei darf sie wieder
überschreiben.

**PWA-10-Teardown:** `AUDIT_READY_URL=` auf einen leeren Wert setzen. Der Lauf prüft den
Audit-Stack dann nicht mehr (`audit_readiness: "not_configured"`, keine Jobabfrage) —
sonst bliebe nach dem Entfernen des Stacks dauerhaft eine fehlgeschlagene Unit zurück.

## Wie der Alarm sichtbar wird

Es gibt **keinen externen Pager** und bewusst keinen Zugangsdaten-Zugriff aus dem
Probe-Skript. Der Alarm ist damit:

```bash
systemctl --failed                     # zeigt numra-healthcheck.service
journalctl -u numra-healthcheck.service -n 20
cat /var/lib/numra/health-status.json  # "failures":[...], "warnings":[...], "recoveries":[...]
```

Nur `failures` (inkl. Konfigurationsabweichungen) setzen den Exit-Code 1 und damit die
Unit auf `failed`. `warnings` und `recoveries` erscheinen im Statusfile und im Journal
(`NUMRA healthcheck WARN: …` / `RECOVERED: …`), lösen aber keinen Alarm aus.

Der Dienst läuft als Benutzer `hermes`. Dafür darf die Gruppe `hermes` das
Sicherungsverzeichnis **auflisten** (`0750 root:hermes`), die Dump-Inhalte bleiben
root-only — die Frischeprüfung braucht nur den Dateinamen, keinen Inhalt.

## Tests

`scripts/ops/tests/test-numra-healthcheck.sh` ist ein reiner Mock-Harness: `docker` und
`curl` sind Attrappen, Konfig, Statusfile und Backup-Verzeichnis liegen in einem
Temp-Verzeichnis. Er liest und schreibt weder `/etc/numra` noch `/usr/local/bin`; ein
`strace`-Lauf am Ende des Harness belegt das (ohne `strace` wird der Beleg übersprungen
und gemeldet). Er deckt ab: Soll-Konfiguration je Dienst, Konfigurationsabweichung,
Warnung vs. Alarm am Schwellwert, Erholung, ungültiges/fehlendes JSON, HTTP 503 mit Body,
hängende QUEUED-Jobs und die 24h-Zählung inkl. Analysefehlern.

```bash
bash scripts/ops/tests/test-numra-healthcheck.sh
```

## Externer Uptime-Probe

Der Host-Healthcheck (oben) meldet einen **Hostausfall nicht**: fällt Agent0 aus, läuft
auch der Timer nicht mehr. Ergänzend prüft deshalb der GitHub-Actions-Workflow
`.github/workflows/uptime-probe.yml` die öffentliche Readiness **von außerhalb des
Hosts**. Er braucht keine Secrets und keinen Zugang zum Host; es entsteht keine neue
öffentliche Erreichbarkeit (nur ausgehende GETs gegen eine bereits öffentliche URL).

**Was geprüft wird.** `GET https://avenyth.de/api/v1/health/ready` (`curl -sS -m 15`,
bis zu 3 Versuche mit 20 s Pause). Ergebnis OK nur bei HTTP 200 **und** JSON-Feld
`status` = `healthy` **und** `database` = `healthy`. Das entspricht der API-Semantik:
der Gesamtstatus ist nur von der Datenbank abhängig. `llm`, `pdf` und
`numerology_engine` erzeugen bei Abweichung (außer `disabled`) nur eine Warnung im
Lauf-Log, keinen Alarm — wie bei den optionalen Diensten im Host-Healthcheck
(„Alarmsemantik pro Dienst“). Das Log enthält weder Header noch Cookies noch den
Response-Body, nur Statuscode und die bereinigten Feldwerte.

**Intervall und Verzögerung.** Zeitplan `*/15 * * * *`. GitHub startet geplante Läufe
häufig verspätet (teils mehrere Minuten, besonders zu Stundenbeginn), einzelne Läufe
können ausfallen. Die Erkennungszeit liegt daher grob bei 15 bis 30 Minuten und ist
nicht garantiert. Bei Repositories ohne Aktivität deaktiviert GitHub geplante
Workflows nach 60 Tagen; dann ist der Workflow im Actions-Tab wieder zu aktivieren.
Folge: Ein stillschweigend deaktivierter Probe alarmiert nicht (kein Lauf, kein Issue).
Der Actions-Tab ist deshalb im Betriebsablauf regelmäßig zu prüfen, ob der Workflow
aktiv ist und zuletzt gelaufen ist.

**Alarmweg.** Bei Fehlschlag legt der Lauf ein Issue mit Label `uptime-alert` und dem
festen Titel `ALARM: avenyth.de Readiness nicht erreichbar/unhealthy` an (das Label
wird bei Bedarf erzeugt) und endet rot. Ist bereits ein offenes Issue mit diesem Titel
vorhanden, wird nur ein Kommentar mit Zeitstempel und Statuscode ergänzt. Bei Erholung
kommentiert der nächste OK-Lauf „Wiederhergestellt“ mit Zeitstempel und schließt das
Issue. Die Alarm-Schritte nutzen `gh` mit dem eingebauten `GITHUB_TOKEN`
(`contents: read`, `issues: write`); der Probe-Schritt selbst nutzt `curl` und `jq`. Es
werden keine Fremd-Actions verwendet.

**Benachrichtigung.** Belegt ist nur, dass das Issue erstellt, kommentiert und
geschlossen wird. Ob und wie GitHub dies als E-Mail oder Push an eine Person zustellt,
hängt von deren GitHub-Benachrichtigungseinstellungen ab (Watch-Status des Repos,
Kanäle unter Settings → Notifications) und ist hier **nicht belegt**. Wer den Alarm
erhalten soll, muss das Repo beobachten bzw. dem Issue zugewiesen sein; eine
Empfängerliste ist im Workflow bewusst nicht hinterlegt.

**Grenzen.**

- Geprüft wird nur die Erreichbarkeit über Cloudflare/Tunnel und die in der öffentlichen
  Readiness enthaltenen Dienststatus; nicht jeder Dienst, nicht die Job-Pipeline, keine
  Sicherungen.
- Die öffentliche Readiness kann kurzzeitig zwischengespeichert sein (serverseitiger
  Cache); sehr kurze Ausfälle bleiben unsichtbar.
- Ein einzelner fehlgeschlagener Lauf (nach 3 Versuchen) alarmiert sofort; es gibt hier
  keinen Schwellwert über mehrere Läufe wie beim Host-Healthcheck.
- Ein manueller Lauf mit abweichender `target_url` nutzt dasselbe Alarm-Issue: ein
  erfolgreicher Testlauf schließt ein offenes, echtes Alarm-Issue.
- Einen manuellen Dispatch darf nur auslösen, wer Schreibrechte im Repository hat. Ein
  Dispatch mit Fehl-URL kann ein echtes offenes Alarm-Issue kommentieren oder ein neues
  anlegen; ein Erholungslauf kann ein echtes Alarm-Issue schließen.
- Der Probe ersetzt keinen Pager: Zustellung und Reaktion hängen an GitHub und an der
  Person, die das Repo beobachtet.

**Testverfahren.** `target_url` ist auf `https://avenyth.de/...` beschränkt
(Allowlist, Eingabe nur über `env`, nie direkt in `run:`), sodass der Dispatch nicht
als Proxy für andere Ziele dient.

```bash
# Fehlerfall: 404 -> Alarm-Issue wird erstellt, Lauf ist rot
gh workflow run uptime-probe.yml -f target_url=https://avenyth.de/api/v1/health/does-not-exist
# Erholung/Normalfall: Standard-URL -> Kommentar "Wiederhergestellt", Issue geschlossen
gh workflow run uptime-probe.yml
gh run list --workflow uptime-probe.yml --limit 5
```

Das Test-Issue danach mit Hinweis „Kontrollierter Test“ schließen (nicht löschen).

**Rückbau.** `.github/workflows/uptime-probe.yml` löschen (und optional das Label
`uptime-alert`). Es bleiben keine Ressourcen außerhalb von GitHub zurück.


## Bewusste Grenzen

- Kein Alarmkanal nach außen (E-Mail/Push) aus dem Host-Skript; der Hostausfall wird nur vom
  „Externen Uptime-Probe“ (GitHub Actions, Issue-Alarm) von außen erfasst. Ein solcher Kanal gehört an einen
  Messaging-Anbieter und damit an eine Zugangsdaten-Entscheidung des Betreibers; das
  Skript bleibt deshalb zugangsfrei. Sobald SMTP existiert (PWA-05), ist ein
  `OnFailure=`-Versand die naheliegende Ergänzung.
- Keine Historie/kein Trend: der Statusfile ist ein Zustandsschnappschuss, die Historie
  liegt im Journal. Der Zuwachsvergleich nutzt genau eine vorherige Messung; die
  Fehlerzähler leben nur im Statusfile (Reset des Files = Zähler bei 0).
- Keine automatische Reparatur. Der Lauf beobachtet nur — ein Neustart von Containern
  oder ein Zurückspielen von Sicherungen bleibt ein bewusster Eingriff.
- `EXPECTED_DEPENDENCIES` und `FAIL_THRESHOLD` gelten global für Produktion und Audit;
  eine getrennte Soll-Konfiguration je Stack gibt es nicht. Ebenso gibt es keinen eigenen
  Schwellwert pro Dienst (z. B. für `database`).
- Die Statuscode-Semantik von `/v1/health/ready` (503 nur bei unhealthy Datenbank, sonst 200)
  legt die API fest, nicht der Monitor; er wertet beide Varianten mit Body korrekt aus.
- `worker` und `analysis-worker` haben im Compose **keinen** Healthcheck (nur
  `restart: unless-stopped`). Der Probe merkt einen stehenden Worker nur indirekt: über
  liegen bleibende QUEUED-Jobs (`STALE_QUEUED_MINUTES`) oder neue FAILED-Jobs, sobald der
  Job das Retry-Budget verbraucht hat. Ein `restart: unless-stopped`-Container ohne
  Healthcheck wird von Docker auch dann nicht neu gestartet, wenn der Prozess zwar lebt,
  aber nichts mehr abarbeitet.
