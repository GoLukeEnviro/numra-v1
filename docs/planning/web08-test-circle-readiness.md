# WEB-08 Abschlussmatrix

Stand: Branch `codex/web08-release-basis`, Basis `6344539f8807e3f9c557ec8beb434935ae04e5e0`.

| Bereich | Implementiert | Lokal getestet | Deployed | Im Zielbetrieb verifiziert |
|---|---:|---:|---:|---:|
| Roadmaps 14/30 Tage/Quartal | ja | ja | nein | nein |
| Meilensteine, Reviewpunkte und Task-Link | ja | ja | nein | nein |
| Annahme/Archivierung und serverseitige Guards | ja | ja | nein | nein |
| Shared Reflection als explizite Kopie | ja | ja | nein | nein |
| Zwei Konten, Außenstehender und Cross-Workspace | ja | ja | nein | nein |
| DISSOLVED-Historie und Mutationssperre | ja | ja | nein | nein |
| Desktop 1440×900 / Mobile 390×844 | ja | ja | nein | nein |
| Nonce-CSP und Service Worker | ja | ja | nein | nein |
| Synthetischer Backup/Restore | ja | ja | nicht anwendbar | nein |
| Readiness- und Backup-Alter-Check | ja | ja | nein | nein |
| Dependabot ohne Auto-Merge | ja | Konfiguration geprüft | nein | nein |
| Echter LLM-Provider | nein | Timeout/Fehler technisch getestet | nein | nein |

## Nachweise

- Web: 263/263 Vitest-Tests, TypeScript, ESLint und Next-Produktionsbuild erfolgreich. Coverage-Basis: 74,39 % Statements und 76,83 % Lines.
- API/Python: finaler vollständiger Lauf 753/753; die gezielten Roadmap-, Task-, Monitoring- und LLM-Regressionen sind enthalten.
- System: reale Zwei-Konten-Journey erfolgreich auf Desktop und Mobile; keine gemockten Produktrequests.
- Backup: isolierter Dump/Restore samt Hash, Alembic-Revision, Datensatzzählung und separater API-Readiness erfolgreich.
- Sicherheit: bestätigte `js-yaml`-/`qs`-Advisories per Patch-Override behoben; Node und externe Python-Pakete danach ohne bekannte Schwachstellen. CSP enthält Request-Nonce, `strict-dynamic` und `worker-src 'self'`.
- Review: vier konkrete unabhängige Befunde wurden behoben: Readiness-Payload, archivierte Task-Links, Service-Worker-CSP und Mobile-Langtext.

## Externe Blocker

1. Der aktive `numra-backup.timer` meldete zuletzt einen Fehler. Alter, Aufbewahrung und Restore eines echten Zielbackups sind nicht verifiziert.
2. Der aktive `numra-update.timer` kann einen Merge zum Deployment machen. Das Skript und die deployed-SHA waren für die vorgeschriebene `deploy`-Identität nicht lesbar; deshalb gilt ein Merge-Hold.
3. Ziel-Compose, Image-Digests, Env-Zuordnung, Alert-Empfänger und tatsächlich laufende Migration sind nicht vollständig lesbar beziehungsweise nachgewiesen.
4. Ein echter LLM-Provider-Smoke fehlt. Davon abhängige Funktionen müssen deaktiviert bleiben.
5. Die lokale Readiness-Lastprobe ist keine WEB-08-Endpunkt- oder Produktionsbaseline.

## Urteil

**NOCH NICHT TESTKREIS-BEREIT.** Der Repository-Stand ist nach Abschluss der finalen CI voraussichtlich testkreisbereit. Der tatsächliche Betriebsstand ist wegen fehlendem echten Backup/Restore-Nachweis, ungeklärtem Auto-Deployment und fehlender Zielkonfigurations-/Monitoring-Evidenz nicht freigabefähig. Ein grüner PR darf diese Betriebsnachweise nicht ersetzen.
