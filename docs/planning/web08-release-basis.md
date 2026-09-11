# WEB-08 und Testkreis-Basis — Arbeitsnachweis

Referenz: `6344539f8807e3f9c557ec8beb434935ae04e5e0`. Kein Produktionsauftrag.

## Contract vor Implementierung

| Nutzeraktion | Existierender Vertrag | Testbasis |
|---|---|---|
| Roadmap anlegen/lesen/bearbeiten/annehmen/archivieren | POST/GET/PATCH `/v1/workspaces/{id}/roadmaps` bzw. `/{roadmap_id}` | test_relationship_roadmaps.py |
| Meilenstein oder Reviewpunkt anlegen/bearbeiten/entfernen | POST/GET/PATCH/DELETE `.../roadmaps/{id}/milestones` | test_relationship_roadmaps.py |
| Aufgabe zuordnen/Zuordnung entfernen | PATCH `.../tasks/{id}` mit `roadmap_milestone_id` | test_relationship_roadmaps.py, test_workspace_tasks.py |
| Private Reflexion bewusst teilen | POST `/v1/private-reflections/{id}/share` mit workspace_id | test_shared_reflections.py |
| Geteilte Kopien lesen/als Autor entfernen | GET/DELETE `/v1/workspaces/{id}/shared-reflections` bzw. `/{id}` | test_shared_reflections.py |

Keine neue Generierungsroute: vorhandene AVENYTH-Vorschläge werden dargestellt;
Generierung gehört nicht zum öffentlich vorhandenen Roadmap-Vertrag.
Shared Reflection ist eine unveränderliche Kopie. Änderungen/Löschen der privaten
Quelle ändern die freigegebene Kopie nicht. Autor-Löschung gemäß bestehender
Privacy-Policy separat prüfen; keine neuen Freigaberegeln erfinden.

## Betriebsprüfung 2026-09-11

SSH-Transport über hermestrader-root, Leseoperationen als deploy UID/GID 1000.
Host-Checkout: f03af3a8c4695d08ccda0be1eb37a2143384d077 (kein Deploymentbeweis).
numra-update.timer und numra-backup.timer aktiv/enabled. Beide zugehörigen
Services meldeten zuletzt exit status 1. Update-ExecStart ist deploy-if-green.sh,
Backup-ExecStart backup.sh. Skripte und deployed_sha sind für deploy nicht lesbar.
Keine Rechteänderung, kein Redeploy, keine Migration oder produktive Datenänderung.

MERGE-HALT: Aktiver Update-Timer kann Merges zu Deployments machen; Wirkung wegen
fehlender Leserechte noch ungeklärt. PRs vorbereiten, keine Merges ohne Klärung.
BACKUP-VERIFIKATION BLOCKIERT: letzter Lauf fehlgeschlagen; reales Backup-Alter,
Inhalt und Wiederherstellbarkeit sind nicht verifiziert. Lokale synthetische
Restore-Prüfung ersetzt diesen Nachweis nicht.

## Lokale Nachweise

- Synthetischer Postgres-Custom-Dump wurde in eine neue Datenbank restauriert. Hash: `971A0FD0DA9A6F0A554E313C0FD3AC19A6AC5DF4F809B89BD806A3B06F192823`; Revision `e6a1b2c3d4e5`; 4 Nutzer und 2 Workspaces lesbar; separate API-Readiness gegen die Restore-Datenbank erfolgreich.
- Produktionsbuild-CSP: individueller Nonce, `strict-dynamic`, `worker-src 'self'`, `private, no-store`; alle ausgelieferten Script-Tags trugen den Nonce.
- WEB-08 Zwei-Konten-Journey: Desktop 1440×900 und Mobile 390×844, reale Next/FastAPI/Postgres-Strecke, Roadmap/Reviewpunkt/Task-Link/Shared Copy und DISSOLVED-Historie erfolgreich.
- Web-Coverage-Basis: 261 Tests, 74,39 % Statements, 65,58 % Branches, 65,58 % Functions, 76,83 % Lines. Diese Messung ist die Ausgangsbasis und noch kein Gate.
- Dependency-Audit: bestätigte `js-yaml`-/`qs`-Advisories per Patch-Override behoben; Node und externe Python-Pakete danach ohne bekannte Schwachstelle.
- Lokaler Readiness-Smoke auf Docker Desktop/Windows: 100 Requests, Parallelität 10, 0 Fehler, p50 39,76 ms, p95 417,67 ms, Maximum 440,28 ms. Das misst ausschließlich den Readiness-Endpunkt in einer lokalen Einzelinstanz und ist keine Skalierungszusage oder WEB-08-Endpunktbaseline.
