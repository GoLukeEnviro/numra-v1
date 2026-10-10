# D4 Geschlossene Beta: Berechtigungen und Übergangsplan

Stand: 2026-10-09. Produktentscheidung: zunächst geschlossenes Beta-Modell, keine
Zahlungsintegration. Dieses Dokument beschreibt Modell, Betrieb und die Reihenfolge,
in der ein Deploy keine bestehenden Nutzer aussperrt.

## 1. Modell: globales Flag UND individuelle Berechtigung

| Ebene | Wer steuert | Wo gespeichert | Wirkung |
|---|---|---|---|
| Globales Feature-Flag (`copilot`, `relationship_workspaces`, `evidence_layer`, `v2_master`) | Betreiber, `/v1/admin/flags` | `feature_flags` | Kill-Switch für alle |
| Individuelle Beta-Berechtigung | Admin je Konto | `entitlement_assignments` -> `entitlement_sets` | nur wer sie hat, darf kostenintensive Funktionen starten |

Kostenintensive Funktionen brauchen serverseitig BEIDES (nur wenn
`BETA_GATE_ENFORCED=true`):

| Funktionsgruppe | Berechtigungsspalte (`entitlement_sets`) | Einstiegspunkte |
|---|---|---|
| `report` | `premium_reports` | `POST /v1/reports`; Worker-Start (`worker.py`) |
| `analysis` | `advanced_relationship_analysis` | `POST /v1/workspaces/{id}/relationship-analysis`, `POST /v1/workspaces/{id}/shadow-dynamics`, `POST /v1/people/{id}/pattern-analyses`; Worker-Start (`analysis_worker.py`) |
| `copilot` | `relationship_copilot` | `POST /v1/workspaces/{id}/copilot/threads/{tid}/messages`, `POST /v1/me/copilot/threads/{tid}/messages` |

Lesezugriffe (bereits erzeugte Berichte/Analysen/Threads ansehen, Threads anlegen,
Exporte) bleiben offen: ein Entzug sperrt nur das Auslösen neuer Kosten.
`GET /v1/people/{id}/evidence-results` ist reine Berechnung ohne LLM und ohne
Persistenz und bleibt ungeschützt.

Bestand der Tabellen (Prod, 2026-10-09, nur gezählt): `entitlement_sets` = 1 Zeile
(`beta_default`, alle Funktionen true, keine Limits), `entitlement_assignments` = 0
Zeilen. Vor D4 diente das Modell nur der Anzeige (`GET /v1/me/entitlements`); nichts
erzwang es.

Umsetzung ohne Schemaänderung: Eine Freigabe ist eine explizite
`entitlement_assignment` auf das Set `beta_default`. Wer keine Zuweisung hat, hat keine
Freigabe, auch wenn die Anzeige-Rückfalllogik weiter `beta_default` auflöst. Neue
Konten erhalten also nichts automatisch. Entzug = Zeile löschen.

`GET /v1/me/entitlements` meldet zusätzlich `beta_access` (Freigabe vorhanden) und
`beta_gate_enforced`; die drei kostenintensiven Flags sind dort die WIRKSAMEN Werte
(bei erzwungenem Gate ohne Freigabe `false`).

Altersbestätigung (D2, `users.age_confirmed_at`) ist eine eigene Eigenschaft des Kontos
und wird vom Gate nicht gelesen; beide Prüfungen sind unabhängig testbar
(`test_age_confirmation_and_beta_grant_are_independent`).

## 2. Fehlercodes

| HTTP | Code | Bedeutung |
|---|---|---|
| 403 | `BETA_ACCESS_REQUIRED` | Gate erzwungen, Konto ohne Freigabe |
| 429 | `QUOTA_EXCEEDED` | Limit erreicht (siehe Limits-Dokument, PR 2) |

Reihenfolge der Prüfungen: Flag (Router) -> Authentifizierung -> CSRF -> Beta-Gate ->
Rate-Limit -> Fachlogik. Im Frontend ersetzt `api/client.ts` den englischen
Servertext von `BETA_ACCESS_REQUIRED` durch einen verständlichen deutschen Hinweis.

## 3. Admin-Betrieb

Alle Endpunkte hinter `require_admin`; Schreibzugriffe mit CSRF und Rate-Limit
(120/h je Admin), Origin-Prüfung durch die bestehende Middleware.

| Methode | Pfad | Wirkung |
|---|---|---|
| GET | `/v1/admin/users/{id}/beta-access` | `{user_id, granted, changed:false}` |
| PUT | `/v1/admin/users/{id}/beta-access` | erteilen, idempotent |
| DELETE | `/v1/admin/users/{id}/beta-access` | entziehen, idempotent |

Jede ECHTE Änderung schreibt genau ein `admin_audit_events`-Ereignis
(`BETA_ACCESS_GRANTED` / `BETA_ACCESS_REVOKED`: Akteur, Ziel-Konto-ID, Zeit,
`safe_metadata = {entitlement_set, source}`; keine E-Mail, kein Freitext). Ein
wiederholter Aufruf ändert nichts und loggt nichts (`changed:false`). Gleichzeitige
Erteilungen sind durch `ON CONFLICT DO NOTHING` auf dem Unique-Index sicher
(Test: 8 parallele PUT = 1 Zuweisung = 1 Auditereignis).

Web: Auf `/admin/users/{id}` zeigt die Kontodaten-Karte den Beta-Zugang, die
Aktionsleiste hat "Beta-Zugang erteilen/entziehen" (mit Bestätigungsdialog).

## 4. Übergangsplan für Bestandskonten

Ziel: Der Deploy sperrt niemanden aus. Reihenfolge verbindlich:

1. **Deploy mit Gate AUS.** `BETA_GATE_ENFORCED` ungesetzt oder `false` (Default).
   Verhalten unverändert; Migration nicht nötig (PR 1 ändert das Schema nicht).
2. **Inventur** (schreibfrei), mindestens eine der beiden Varianten:
   - vor/ohne Deploy: `psql -v salt="$(openssl rand -hex 8)" -f scripts/ops/beta_inventory.sql`
     (read-only-Transaktion, Konten als Kurz-Hash, nur Zähler);
   - nach Deploy: `python -m numra_api.cli beta inventory [--since-days N]`
     (HMAC-Pseudonyme, gleiche Zählweise).
   Gezählt werden je Konto Berichte, Analyse-Jobs (Beziehung/Schatten),
   gespeicherte Musteranalysen, Copilot-Nachrichten des Nutzers.
3. **Backfill, ausdrücklich ausgelöst.** Weder Migration noch Start-Hook schalten
   frei. `python -m numra_api.cli beta backfill [--since-days N]` ist Dry-run und
   listet nur Pseudonyme; erst `--apply` schreibt. Kandidaten: aktive Konten mit
   mindestens einer Nutzung (im Zeitfenster) ohne Freigabe. Jede Freigabe wird auditiert
   (`actor_user_id` NULL, `source=cli_backfill`, `run=<Zeitstempel>`). Wiederholung ist
   wirkungslos. Einzelne Konten lassen sich zusätzlich über die Admin-API/-UI nachziehen
   oder verweigern (zuvor aus der Kandidatenliste prüfen).
4. **Enforce.** `BETA_GATE_ENFORCED=true` für api, worker UND analysis-worker setzen
   (die Worker prüfen beim Jobstart erneut) und die Dienste neu starten. Danach
   Stichprobe: freigeschaltetes Konto kann erzeugen, Neukonto bekommt 403
   `BETA_ACCESS_REQUIRED`.
5. **Rollback** ohne Datenverlust: `BETA_GATE_ENFORCED=false` und Neustart. Freigaben
   bleiben bestehen.

Stand der Prod-Inventur am 2026-10-09 (nur aggregierte Zähler, schreibfrei): 7
Konten, davon 5 aktiv; 4 Konten haben mindestens einmal Berichte, Analysen oder Chat
genutzt (insgesamt 18 Berichte, 1 Analyse-Job, 1 Copilot-Nachricht); 0 Freigaben.
Ein Backfill würde nach heutigem Stand also 4 aktive Konten freischalten.

Hinweis Worker: Wird das Gate erzwungen, scheitern bereits eingereihte Jobs eines
Kontos ohne Freigabe beim Start terminal mit `error_code=BETA_ACCESS_REQUIRED`
(kein LLM-Aufruf). Deshalb Backfill VOR Enforce.
