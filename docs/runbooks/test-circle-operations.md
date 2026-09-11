# Geschlossener Testkreis: Betrieb und Wiederanlauf

## Grenzen und Zielwerte

Dieses Runbook aktiviert keine Umgebung. Vorgeschlagene Ziele sind RPO höchstens 24 Stunden, RTO höchstens vier Stunden, eine tägliche Sicherung und sieben tägliche Wiederherstellungspunkte. Sie gelten erst als erfüllt, wenn Zeitplan, Aufbewahrung und ein Restore aus einem echten Sicherungsartefakt in der Zielumgebung nachgewiesen wurden.

## Reproduzierbare Zuordnung

Vor jedem Release werden Git-Commit, Container-Image-Digests, Compose-Dateien, Env-Dateiname und Alembic-Revision gemeinsam protokolliert. Geheimniswerte gehören nicht in das Protokoll. Ein Merge gilt nicht als Deployment-Nachweis.

## Backup und isolierter Restore

1. Mit `pg_dump --format=custom --no-owner --no-acl` ein eindeutig datiertes Artefakt erzeugen und dessen SHA-256 protokollieren.
2. Eine neue, leere Testdatenbank in einem isolierten Compose-Projekt erstellen.
3. Das Artefakt mit `pg_restore --clean --if-exists --no-owner --no-acl` einspielen.
4. Alembic-Revision, Tabellen- und Referenzintegrität sowie erwartete synthetische Marker prüfen.
5. API und Web gegen die wiederhergestellte Datenbank starten; Liveness, Readiness, Anmeldung und eine lesende WEB-08-Strecke prüfen.
6. Start, Ende, RTO, Artefakt-Hash und Resultat dokumentieren; den isolierten Stack anschließend entfernen.

Ein Restore synthetischer Daten belegt nur das Verfahren. Die Wiederherstellbarkeit realer Daten erfordert einen separaten, autorisierten Test eines echten Backups.

## Überwachung

`python scripts/check_testcircle_readiness.py --base-url http://127.0.0.1:58080 --backup <artefakt>` prüft Erreichbarkeit, Readiness und ein Backup-Alter von höchstens 24 Stunden. Ein Exitcode ungleich null wird vom später gewählten Scheduler/Alert-Kanal übernommen. Reale Empfänger werden erst nach ausdrücklicher Autorisierung konfiguriert.

## Rollback und Datenbank

Vor dem Wechsel wird geprüft, ob der vorherige Anwendungsstand mit der bereits migrierten Datenbank kompatibel ist. Bei kompatiblen, additiven Migrationen werden die zuvor protokollierten Image-Digests wieder aktiviert und anschließend Health- und Anwendungssmokes ausgeführt. Bei inkompatiblen Migrationen wird kein automatischer Downgrade ausgeführt; stattdessen wird eine neue Datenbank aus dem unmittelbar vor dem Release erstellten Backup isoliert wiederhergestellt und der kontrollierte Umschaltplan freigegeben.

## Incident-Ablauf

Änderungen stoppen, Zeitpunkt und betroffene Nutzerstrecke erfassen, Logs und Release-Zuordnung sichern, Datenintegrität prüfen und erst danach über Rollback oder Vorwärtskorrektur entscheiden. Datenschutzvorfälle werden getrennt erfasst; Zugangsdaten werden rotiert, sobald eine Offenlegung bestätigt ist. Abschluss sind Ursachenbefund, Nutzerwirkung, Korrektur und ein reproduzierbarer Regressionstest.
