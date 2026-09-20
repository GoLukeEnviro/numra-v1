# PWA-07 — Kontodatenexport (`GET /v1/account/export`)

Stand 2026-09-20. Dieses Dokument ist die **Formatspezifikation** des strukturierten
Kontodatenexports, der PWA-07 gefehlt hat (Issue #125). Es beschreibt, was exportiert
wird, was bewusst nicht exportiert wird und über welchen Pfad ein Konto daran kommt.

Vorher gab es nur den PDF-Render eines Reports; `ExportType.JSON` führte einen
JSON-Export im Enum, der nie erreichbar war. Diese Arbeit schließt die Funktionslücke.

## Der Produktpfad

| Ebene | Pfad |
|---|---|
| UI | `/settings/privacy` → Karte „Deine Daten exportieren" → Download-Link |
| Browser | `/api/v1/account/export` (Same-Origin-Proxy der Web-App) |
| API | `GET /v1/account/export` |

Der Link ist ein echtes `<a href download>` auf den Same-Origin-Proxy. Die API
antwortet mit `Content-Disposition: attachment` und
`Cache-Control: no-store`; der Dateiname lautet
`avenyth-account-export-<YYYYMMDDTHHMMSSZ>.json` (UTC, identisch mit `generated_at`).

Zugang: ausschließlich ein angemeldetes Konto für **sich selbst** — die Route liest die
Identität aus der Session und kennt keinen Zielparameter. Rate Limit: 10 Exporte pro
Konto und Stunde.

## Format

```jsonc
{
  "format": "avenyth.account-export",
  "format_version": "1.0",
  "generated_at": "2026-09-20T06:58:00+00:00",
  "counts": { "profiles": 1, "personal_workspace.private_notes": 3, "…": 0 },
  "account": { … },
  "profiles": [ … ],
  "personal_workspace": { … },
  "relationships": { … },
  "workspaces": [ … ],
  "reports": { … },
  "copilot": { … }
}
```

`format` bleibt über Versionen stabil, `format_version` steigt bei Strukturänderungen.
`counts` nennt je Liste die Anzahl Datensätze — die Vollständigkeitsprüfung eines
Konsumenten braucht damit keinen Volltextscan, und ein leeres Konto ist daran sofort
als „leer" erkennbar (jede Kategorie existiert immer, auch leer: keine fehlenden
Schlüssel, keine `null`-Kategorien).

### Kategorien

| Kategorie | Inhalt |
|---|---|
| `account` | `id`, `email`, `display_name`, `role`, `is_active`, `email_verified_at`, `created_at`, `deletion{status,deleted_at}`, `entitlements` (effektiver Satz + Schwellen) |
| `profiles` | je Profil: Geburts-/aktuelle Namensfelder, Geburtszeit/-ort, Modus (`SELF`/verwaltet), `name_identities`, `calculations` mit `input_snapshot` und `canonical_profile_json` |
| `personal_workspace` | `private_reflections`, `private_notes`, `personal_tasks`, `life_tracking_entries` (inkl. Custom-Werten), `custom_metrics`, `pattern_analyses` |
| `relationships` | `comparisons` (V1-Vergleiche), `invitations` (ausgehend), `connections` mit `status`/`dissolved_at` und dem Anzeigenamen der Gegenseite |
| `workspaces` | je Workspace: `members` (Rolle + Anzeigename + Status), `consent` (`grants` mit Richtung/Schirmherr, `events`), `tasks` + Ereignisse, `roadmaps` + Meilensteine, `checkins` (eigene Antworten + geteilte Analyse), `shared_reflections`, `analysis_jobs`, `analyses` (Relationship + Shadow Dynamics), `copilot_threads` |
| `reports` | `reports` (inkl. `content_json`, also der vollständige Bericht), `report_jobs` (Status/Fortschritt, keine Lease-/Backoff-Interna), `report_exports` (PDF-Metadaten) |
| `copilot` | `PERSONAL_PRIVATE`-Threads mit Nachrichten (`role`, `content`, `basis_type`, `author`) |

### Bewusst nicht enthalten

| Nicht enthalten | Begründung |
|---|---|
| `users.password_hash` | Geheimnis |
| `sessions`, `email_verification_tokens`, `password_reset_tokens` | Zugangs-Token; ein Export ist keine Wiederherstellung von Sitzungen |
| `connection_invitations.token_hash`, `checkin_idempotency.payload_hash` | Interne Schlüssel |
| `thread_context_snapshots` (Prompt-Kontextblöcke) | Interner Prompt-Baustein — genau das Material, das nie Produkttext werden darf |
| `llm_generations` (`prompt_hash`, Latenzen) | Interne Betriebsmetadaten ohne Nutzerinhalt |
| `admin_audit_events` | Interner Admin-Audit-Pfad, betrifft nicht nur dieses Konto |
| `report_sections` (Einzelzeilen) | Der zusammengesetzte Report steht vollständig in `reports[].content_json`; die Zeilen sind das Bau-Artefakt dazu |
| `exports.file_ref` | Opaker Speicherpfad |
| E-Mail-Adressen, Namen oder UUIDs anderer Konten | Ein Konto sieht im Export nur den Produkt-Anzeigenamen der Gegenseite (`display_name_override` bzw. Profilname), nie ihre Adresse, nie ihre Nutzer-ID |
| Rohe Check-in-Antworten der Gegenseite | `specs/v2/checkin-spec.md` (Section 19): SUBMITTER_ONLY. Nur die eigenen Antworten werden gelesen — und die geteilte, aggregierte Analyse, die beiden gehört |
| Private Copilot-Threads der Gegenseite | `RELATIONSHIP_PRIVATE` wird auf `owner_user_id` gefiltert |

### Soft-Delete und Tombstone

Die Löschung ist ein Soft-Delete mit PII-Tilgung; die `users`-Zeile überlebt als
Tombstone (`repositories/account.py`). Für den Export heißt das:

* Ein **gelöschtes** Konto kann nicht exportieren — `is_active=False` greift im
  Login-Gate, die Route antwortet `401`, nicht mit Daten.
* Ein Konto, dessen **Gegenseite** gelöscht wurde, exportiert weiterhin die geteilte
  Historie (Aufgaben, Roadmaps, geteilte Reflexionen, Analysen) und benennt die
  Gegenseite mit dem Produkt-Tombstone-Namen `Ehemaliges Mitglied`.
* Der Zustand steht als `account.deletion.status` im Dokument, damit ein Empfänger ihn
  nicht aus `deleted_at` ableiten muss.

## Umsetzung

* `repositories/account_export.py` — Lese-Projektionen. Jede Abfrage nennt die
  exportierten Spalten einzeln; Geheimnisse werden nicht nachträglich gefiltert,
  sondern **nie gelesen**.
* `services/account_export_service.py` — Dokumentaufbau und Kategorien-Reihenfolge.
* `routes/account.py` — die Route selbst.

Zwei Eigenschaften sind bewusst:

1. **Streaming.** Das Dokument wird Kategorie für Kategorie erzeugt und als
   `StreamingResponse` ausgeliefert; der Speicherbedarf hängt an der größten
   Einzelkategorie, nicht an der Kontogröße.
2. **Session-Eigentum.** Der Generator öffnet und schließt seine eigene
   `AsyncSession` aus dem `sessionmaker`. Er darf **nicht** die request-gebundene
   Session benutzen: FastAPI schließt `Depends(..., scope="function")`-Dependencies,
   bevor `await response(...)` den Body streamt (`fastapi/routing.py:140-147`) — die
   Generator-Abfragen liefen dann auf einer bereits geschlossenen Session, die sich
   still eine neue Verbindung nimmt, deren Transaktion nie committet wird. Genau das
   ist beim ersten Lauf dieser Route passiert und hat eine „idle in transaction"-
   Verbindung hinterlassen, die Tabellen-Locks hielt (der nächste Testlauf blockierte
   im `DROP TABLE`). Der Grund steht als Kommentar im Modul-Docstring, damit er nicht
   wegoptimiert wird.

## Tests

`apps/api/tests/integration/test_account_export.py` (14 Fälle):

| Test | Sichert |
|---|---|
| `test_export_requires_authentication` | kein Export ohne Session |
| `test_empty_account_returns_every_documented_category` | alle Kategorien vorhanden, alle `counts` 0 |
| `test_export_headers_and_cache_behaviour_are_stable` | Content-Type, `no-store`, Dateinamensmuster |
| `test_populated_account_exports_its_records_and_counts_agree` | Datensätze + `counts`-Konsistenz |
| `test_shared_workspace_is_exported_with_its_retained_artifacts` | Mitglieder, Consents, Aufgaben, geteilte Reflexion, Verbindung; keine fremde E-Mail, kein `*_user_id` |
| `test_own_checkin_responses_are_exported_but_not_the_others` | eigene Antworten ja, die der Gegenseite nicht (beide Zeilensätze existieren) |
| `test_export_repeats_are_stable_but_not_byte_identical` | gleiche Struktur/Werte, neuer Zeitstempel |
| `test_export_never_contains_another_accounts_private_material` | Sentinel-Probe: fremde Notiz, fremder Copilot-Thread und fremde UUID fehlen |
| `test_export_never_contains_credentials_or_internals` | Sentinel-Proben in Sitzungs-/Token-/Prompt-Hash, `file_ref`, Kontextblock; rekursive Schlüsselprüfung gegen `password*`, `token_hash`, `file_ref`, … |
| `test_deleted_account_cannot_export_its_data` | gelöschtes Konto → `401` |
| `test_export_after_partner_deletion_keeps_history_and_pseudonymizes` | Historie bleibt, Gegenseite wird `Ehemaliges Mitglied` |
| `test_export_after_own_deletion_leaves_nothing_readable` | nach der Löschung ist das private Material weg |
| `test_export_and_deletion_form_a_working_pair` | Exit-Gate aus #125: erst exportieren, dann löschen |
| `test_export_is_rate_limited_per_account` | 10 Exporte, danach `429` |

Web: `apps/web/src/components/settings/__tests__/export-account-panel.test.tsx`
prüft den Same-Origin-Link, das `download`-Attribut und die Offenlegung, dass keine
Zugangsdaten und keine Prompt-Bausteine im Export landen.

## Offen (nicht Teil dieses Schritts)

* **`ExportType.JSON`.** Der Enum-Wert bleibt unerreichbar: Exporte im Sinne der
  `exports`-Tabelle sind Report-Renderings, der Kontodatenexport ist eine eigene
  Auskunft. Der Wert ist damit weiterhin eine irreführende Oberfläche — siehe
  Folge-Issue.
* **Formatversionierung in der Praxis.** `format_version` ist gesetzt und
  dokumentiert; ein zweiter Bruch (1.1) existiert noch nicht, die Regel steht aber im
  Dokument.
