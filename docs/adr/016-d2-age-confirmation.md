# ADR 016 — Alterserklärung (18+) für eigene Nutzerkonten (D2)

## Status

Accepted — setzt die Produktentscheidung D2 um und konkretisiert ADR 012
("AVENYTH accounts are 18+ only").

## Entscheidung

Eigene Nutzerkonten gibt es ab 18 Jahren. Das Konto trägt dafür eine **Erklärung**,
keinen Nachweis.

- **Registrierung.** Die Web-UI zeigt eine ausdrückliche, **nicht vorangekreuzte**
  Checkbox „Ich bin mindestens 18 Jahre alt.“. Maßgeblich ist der Server:
  `POST /v1/auth/register` verlangt `age_confirmed: true` (nur ein echtes JSON-`true`; jeder andere Wert, auch `null`, `"true"` oder `1`, wird zu `false`).
  Fehlt das Feld oder ist es `false`, antwortet die API mit `422` und dem Code
  `AGE_CONFIRMATION_REQUIRED`, es entsteht weder Konto noch Sitzung. Ein Direktaufruf
  ohne UI scheitert damit.
- **Konto-Export.** `age_confirmed_at` und `age_declaration_version` stehen im Abschnitt `account` des Datenexports.
- **Speicherung.** `users.age_confirmed_at` (UTC, `timestamptz`) und
  `users.age_declaration_version` (aktuell `age-declaration-v1`, Konstante
  `AGE_DECLARATION_VERSION` in `services/age_declaration.py`). Bei jeder inhaltlichen
  Änderung des Erklärungstexts wird die Version erhöht; gespeicherte Bestätigungen
  behalten die Version, unter der sie abgegeben wurden.
- **Bestandskonten.** Beide Spalten bleiben `NULL` = **nicht bestätigt**. Es gibt
  keinen Backfill und keine rückwirkende Markierung. Die Migration `d2a8c4f6b1e3`
  (auf `c5a9d3e72b16`) fügt nur zwei nullable Spalten ohne Default hinzu; der
  Vorgängercode ignoriert sie (rückwärtskompatibel).
- **Nachträgliche Bestätigung.** `POST /v1/auth/confirm-age` mit `{"age_confirmed": true}`:
  authentifiziert, CSRF-geschützt (`require_csrf`), pro Nutzer ratenbegrenzt, idempotent.
  Der Erstanspruch ist ein atomares `UPDATE … WHERE age_confirmed_at IS NULL`; eine
  Wiederholung ändert Zeitpunkt und Version nie und schreibt keinen zweiten
  Audit-Eintrag. Unbekannte Felder (z. B. ein Geburtsdatum) werden mit `422` abgelehnt.
- **Web-UI für Bestandskonten.** `AgeConfirmationBanner` im App-Shell zeigt für
  unbestätigte Konten einen nicht ausblendbaren Hinweis mit Checkbox und Button. Es gibt
  **kein hartes Aussperren**; die App bleibt nutzbar.
- **Auditlog.** Jede erstmalige Bestätigung erzeugt ein `AdminAuditEvent` mit
  `action=AGE_CONFIRMED` (Akteur = Ziel = Konto), `safe_metadata` =
  `{declaration_version, source: "registration" | "existing_account"}`.
- **Datensparsamkeit.** Keine Ausweiskopie, kein Geburtsdatum, kein Alter. Gespeichert
  wird ausschließlich die Erklärung mit Zeitpunkt und Version.

## Schnittstelle für D4 (kostenintensive Aktionen)

D2 sperrt **nichts**. Ein späteres Gate (D4) liest `age_confirmed_at` aus
`GET /v1/auth/me` (`UserOut.age_confirmed_at`, `UserOut.age_declaration_version`) bzw.
`users.age_confirmed_at` serverseitig: `NULL` heißt „nicht bestätigt“. Maßgeblich bleibt
die serverseitige Prüfung; die UI darf nur spiegeln.

## Offene Frage: verwaltete Profile

Ob und wie verwaltete Profile (`MANAGED_MINOR` laut ADR 012, auch Profile Dritter)
zusätzliche Regeln, Einwilligungen oder Hinweise brauchen, wird durch die Kontoregel
**nicht** automatisch beantwortet. Sie ist hier bewusst nicht implementiert und braucht
eine eigene Produktentscheidung.

## Bekannte Grenzen

- Eine Erklärung ist kein Altersnachweis; sie ist selbst abgegeben und nicht verifizierbar.
- Konten, die nicht über die Registrierung entstehen (z. B. per CLI angelegt), bekommen keine
  Erklärung automatisch; sie bleiben `NULL` bis zur Bestätigung.
- Mobile-App und Bearer-Pfad (`/v1/auth/mobile/*`) nutzen das neue Feld in `UserOut`
  noch nicht; die mobile Registrierung existiert nicht im Repo.

