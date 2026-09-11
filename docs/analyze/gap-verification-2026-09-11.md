# Verifizierte GAP-Befundmatrix — 2026-09-11

Referenz ist `origin/main` bei `6344539f8807e3f9c557ec8beb434935ae04e5e0`; Änderungen aus `codex/web08-release-basis` sind als **in Arbeit** gekennzeichnet. Der ursprüngliche Gesamtscore wird nicht fortgeschrieben. Risiko bezeichnet den geschlossenen Testkreis.

| ID | Prüfergebnis und Quelle | Status | Risiko / Entscheidung | Paket und Abnahme |
|---|---|---|---|---|
| ARCH-001 | ADR-006 und `engine-astrology` bestätigen die bewusste Deaktivierung. | BEWUSST_ZURÜCKGESTELLT | Kein Risiko für den vereinbarten Umfang; keine Astrologie implementieren. | E: Scope eingehalten |
| ARCH-002 | Admin-Routen, Rollenchecks und Admin-Tests existieren; die historische Versionsaussage ist keine aktuelle Funktionslücke. | TEILWEISE_BESTÄTIGT | Doku-Pflege, kein WEB-08-Blocker. | E: Folge-Backlog |
| ARCH-003 | Architektur ist in README und ADRs verteilt; `docs/architecture.md` fehlt. | BESTÄTIGT | Mittel für Wartung, nicht für Testkreis-Journey. | E: Folge-Backlog |
| ARCH-004 | Backend samt Migration existiert; WEB-08-Oberfläche fehlte auf Referenz-Commit. | BESTÄTIGT | Hoch für WEB-08; in diesem Branch umgesetzt. | C: Zwei-Konten-Journey |
| ARCH-005 | Importzyklus wurde nicht mit einem freigegebenen Diagnosewerkzeug gemessen. | UNVERIFIZIERT | Kein belegter Release-Blocker. | A: keine pauschale Bereinigung |
| CQ-001 | Einzelne lange Funktionen bestehen; Zeilenlänge beweist keinen Defekt. | TEILWEISE_BESTÄTIGT | Nur konkrete WEB-08-Risiken werden geändert. | D: Folge-Backlog |
| CQ-002 | Personenformulare enthalten ähnliche Logik. | BESTÄTIGT | Außerhalb WEB-08; keine risikoreiche Abstraktion im Release-Branch. | E: Folge-Backlog |
| CQ-003 | `print` kommt überwiegend in expliziten CLI-/Diagnoseskripten vor. | TEILWEISE_BESTÄTIGT | Niedrig; kein Laufzeitfehler belegt. | E: Folge-Backlog |
| CQ-004 | Genannte Signaturen besitzen viele fachliche Parameter. | BESTÄTIGT | Niedrig; Umbau ohne Defekt verschoben. | E: Folge-Backlog |
| CQ-005 | Große Dateien bestehen, unter anderem der typisierte API-Client. | BESTÄTIGT | Größe allein ist kein Abnahmekriterium. | E: Folge-Backlog |
| CQ-006 | Keine belastbare Duplikat-/Verschachtelungsmessung. | UNVERIFIZIERT | Kein belegter Blocker. | A |
| TEST-001 | Der aktuelle Web-Baum enthält wesentlich mehr Tests als der Altbericht; einzelne Seiten haben keine direkte Seitendatei-Suite. | TEILWEISE_BESTÄTIGT | WEB-08 erhält gezielte Unit-/Systemabdeckung. | C/D: Tests grün |
| TEST-002 | Interpretation besitzt Unit-, Golden- und Systemabdeckung, aber keine pauschale Property-Suite für jeden Composer. | TEILWEISE_BESTÄTIGT | Nicht durch WEB-08 verändert. | E: Folge-Backlog |
| TEST-003 | PDF besitzt eine kleine, reale Renderer-Suite. | BESTÄTIGT | Nicht durch WEB-08 verändert. | E: Folge-Backlog |
| TEST-004 | CI hat kein API-/Web-Coverage-Gate. | BESTÄTIGT | Messung vor Festlegung eines ehrlichen Gates erforderlich. | D |
| TEST-005 | API-/Web-Coverage war im Bericht ungemessen. | BESTÄTIGT | Messlauf als Release-Nachweis; Gate nicht senken. | D |
| DOC-001 | `CHANGELOG.md` fehlt. | BESTÄTIGT | Kein Testkreis-Blocker. | E: Folge-Backlog |
| DOC-002 | Entspricht ARCH-003. | BESTÄTIGT | Wartungsrisiko. | E: Folge-Backlog |
| DOC-003 | `CONTRIBUTING.md` fehlt. | BESTÄTIGT | Kein Nutzerstreckenrisiko. | E: Folge-Backlog |
| DOC-004 | OpenAPI ist vorhanden; ein separates vollständiges API-Handbuch fehlt. | BESTÄTIGT | Kein WEB-08-Blocker. | E: Folge-Backlog |
| DOC-005 | Produktions-Compose ist nicht im Repo; Zielkonfiguration konnte als `deploy` nicht gelesen werden. | BESTÄTIGT | Hoch; externe Betriebsverifikation blockiert. | B: Betreiber-Nachweis nötig |
| DOC-006 | Kommentarquote wurde nicht gemessen. | UNVERIFIZIERT | Kein Qualitätskriterium für diesen Release. | A |
| DEP-001 | Kein Dependabot/Renovate-Workflow vorhanden. | BESTÄTIGT | Mittel; Update-Automatik ohne Auto-Merge folgt separat. | D |
| DEP-002 | Playwright-Versionen sind gepinnt; alter Drift ist behoben. | BEREITS_BEHOBEN | Kein offenes Risiko. | A |
| DEP-003 | Veraltungsgrad ist ohne kontrollierte Upgrade-Prüfung nicht bewertet. | UNVERIFIZIERT | Keine pauschalen Major-Upgrades. | D |
| DEP-004 | GitHub meldete `js-yaml` High und `qs` Moderate auf dem Referenzstand. Gezielte transitive Overrides auf 4.3.2/6.16.0 beheben sie; `pnpm audit` meldet danach keine bekannte Schwachstelle. `pip-audit` ist für externe Python-Pakete ebenfalls sauber. | BEREITS_BEHOBEN | Interne Pakete sind nicht auf PyPI prüfbar. | D |
| SEC-001 | Mock-LLM ist isoliert gesund; ein echter Provider-Smoke fehlt. Timeout-Konfiguration wird separat geprüft. | TEILWEISE_BESTÄTIGT | Verifikationslücke; echte LLM-Funktionen bleiben ohne Provider-Nachweis deaktiviert. | D: externer Provider-Nachweis |
| SEC-002 | Referenz-CSP erlaubte Inline-Skripte. Branch liefert Request-Nonce und `strict-dynamic`; Produktionsbuild und HTML-Header wurden geprüft. | BEREITS_BEHOBEN | Regression wird per Browser geprüft. | D: CSP-Smoke |
| SEC-003 | CI hat Dependency-Audit, aber keinen eigenständigen SAST-Lauf. | BESTÄTIGT | Mittel; getrennte Härtung, damit Required Checks stabil bleiben. | D |
| SEC-004 | Gefundene Werte sind benannte, isolierte Testwerte und keine produktiven Geheimnisse. | WIDERLEGT | Kein Leak belegt. | A |
| SEC-005 | Incident-Ablauf fehlte; `docs/runbooks/test-circle-operations.md` ergänzt ihn. | BEREITS_BEHOBEN | Verfahren muss organisatorisch angenommen werden. | B |
| SEC-006 | Bestätigte Node-Advisories wurden per Patch-Override behoben; Node- und externer Python-Audit sind danach sauber. | BEREITS_BEHOBEN | Interne Pakete brauchen weiterhin Quellcodeprüfungen. | D |
| OPS-001 | Externe Ziel-Compose ist nicht versioniert und für `deploy` nicht lesbar. | BESTÄTIGT | Hoch; reproduzierbare Zielzuordnung extern blockiert. | B |
| OPS-002 | Healthchecks existieren; Metrikexport, Aggregation und realer Alarmempfänger fehlen. Lokaler Readiness-/Backup-Alter-Check ergänzt. | TEILWEISE_BESTÄTIGT | Betriebsalarmierung extern offen. | B |
| OPS-003 | `numra-backup.timer` existiert, letzter gelesener Lauf war fehlgeschlagen; Backup-Pfad war nicht lesbar. Isolierter synthetischer Dump/Restore ist erfolgreich. | BESTÄTIGT | Kritischer externer Blocker für echte Daten. | B: echter Restore-Nachweis |
| OPS-004 | Ein aktiver `numra-update.timer` führt ein externes Deploy-Skript aus; dessen genaue Merge-Wirkung war nicht lesbar. | TEILWEISE_BESTÄTIGT | Merge-Hold bis ausdrückliche Freigabe und geklärter Wirkung. | B/E |
| OPS-005 | Keine frühere reproduzierbare Performance-Baseline gefunden. | BESTÄTIGT | Messung offen, keine Skalierungszusage. | D |
| OPS-006 | Next-Build weist Route- und Shared-Bundle-Größen aus; ein festes Budget fehlt. | BESTÄTIGT | Mittel; aktuelle WEB-08-Routen bauen erfolgreich. | D |
| OPS-007 | Timeout-Felder existieren; Durchsetzung im echten Providerpfad bleibt zu belegen. | TEILWEISE_BESTÄTIGT | Providerfunktionen ohne Live-Smoke deaktiviert halten. | D |
| OPS-008 | Kein bereinigter Musterscan ausgeführt. | UNVERIFIZIERT | Kein spekulativer Befund. | A |
| OPS-009 | Worktrees und Status wurden direkt geprüft; fremde und untracked Dateien blieben unangetastet. | BEREITS_BEHOBEN | Arbeitsbasis ist isoliert. | A |

## Widersprüche

| ID | Entscheidung |
|---|---|
| FLAG-001 | Alte Zahl von neun Unit-Dateien ist durch den aktuellen Testbaum überholt; gezielte Lücken bleiben möglich. |
| FLAG-002 | Maßgeblich ist die Workflow-Datei am jeweiligen Commit; am Referenzstand wurden zwölf Required Jobs berichtet. |
| FLAG-003 | Testzahlen werden nur mit Commit, Suite und Laufdatum verglichen; Wachstum zwischen August und September erklärt die Differenz. |

## Bereits gemessene Release-Evidenz

- Web: Typecheck, ESLint und Next-Produktionsbuild erfolgreich; Roadmap- und Reflexionsrouten werden dynamisch gebaut.
- CSP: Antwort enthält einen individuellen Nonce, `strict-dynamic`, `Cache-Control: no-store`; alle ausgelieferten Script-Tags trugen denselben Nonce.
- API/Python: finaler vollständiger Lauf 753/753 einschließlich der Review-Regressionen.
- Reale Zwei-Konten-Journey einschließlich WEB-08: Desktop 1440×900 und Mobile 390×844 bestanden. Sie umfasst Roadmap, Reviewpunkt, Task-Link, explizite Shared Copy, Fremdlöschschutz, Service Worker und DISSOLVED-Historie.
- Restore: synthetischer Custom-Dump mit SHA-256 `971A0FD0DA9A6F0A554E313C0FD3AC19A6AC5DF4F809B89BD806A3B06F192823` wurde in eine leere Datenbank restauriert; Alembic-Revision `e6a1b2c3d4e5`, 4 Nutzer und 2 Workspaces wurden gelesen, eine separate API meldete gegen die Restore-Datenbank vollständige Readiness.
- Betrieb: Zielhost-Repository meldete `f03af3a8c4695d08ccda0be1eb37a2143384d077`; aktive Update- und Backup-Timer wurden gelesen. Die letzten Service-Ergebnisse waren fehlgeschlagen und die Skripte beziehungsweise deployed-SHA waren für `deploy` nicht lesbar. Es wurden keine Rechte oder produktiven Daten geändert.
