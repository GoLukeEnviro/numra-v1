# Abnahme-Werkzeuge: Smoke, Acceptance, PDF-Inhaltsprüfung

Ergänzt [release-tooling.md](release-tooling.md): Die Abnahmeläufe liefern den Bericht, den die
Marker-Phase von `numra-release.sh` verlangt.

| Datei | Zweck | Ziele |
|---|---|---|
| `scripts/acceptance/numra_smoke.py` | minimaler Smoke-Test mit genau einem synthetischen Konto (Auth, CSRF, Origin, Proxy, Report + PDF, Queue, Cleanup) | `audit`, `prod` |
| `scripts/acceptance/numra_acceptance.py` | vollständige Abnahme (Zwei-Konten-Journey, Einladungen, Consent/IDOR, Admin-Flags, LLM-Analysen, Web-Proxy, Worker-Logs, Cleanup) | nur `audit` |
| `scripts/acceptance/content_checks.py` | Platzhalter-, Sprach- und PDF-Prüfung (pypdf) | – |
| `scripts/acceptance/requirements.txt` | `pypdf` für die PDF-Prüfung (im Repo zusätzlich Dev-Abhängigkeit) | – |

`numra_acceptance.py` verändert die Audit-Datenbank (E-Mail-Verifizierung per UPDATE,
`promote-admin`, Flag-Umschaltung mit Wiederherstellung) und verweigert deshalb `--target prod`
(Exit 2). Für Produktion gibt es nur den Smoke-Test, der ausschließlich `SELECT` ausführt.

## Aufruf

```bash
pip install -r scripts/acceptance/requirements.txt

# Audit, vollständig
python3 scripts/acceptance/numra_acceptance.py --target audit --target-sha <SHA> \
  --api-base http://127.0.0.1:<API-PORT> --web-base http://127.0.0.1:<WEB-PORT> \
  --container-prefix <PROJEKT>- --report-dir <DIR> [--repo-dir <CHECKOUT>] \
  [--skip-llm] [--reset-ratelimit] [--llm-timeout 600] [--dry-run]

# Smoke (audit oder prod)
python3 scripts/acceptance/numra_smoke.py --target prod --target-sha <SHA> \
  --api-base http://127.0.0.1:<API-PORT> --web-base http://127.0.0.1:<WEB-PORT> \
  --container-prefix <PROJEKT>- --origin <ERLAUBTE-ORIGIN> --expect-checkins 401|503 \
  --report-dir <DIR> [--public-base https://<HOST>] \
  --i-am-sure-prod --confirm-sha <SHA8>
```

- `--target` hat keinen Default. Prod braucht zusätzlich `--i-am-sure-prod` und
  `--confirm-sha` (erste 8 Zeichen von `--target-sha`).
- `--target-sha` ist die vollständige SHA des geprüften Stands und landet im Bericht. Mit
  `--repo-dir` wird der Checkout-HEAD dagegen geprüft.
- Container heißen `<container-prefix><dienst>-1`; Basis-URLs müssen http-Loopback sein.
  Docker wird nur gegen diese Container aufgerufen (Guard), Datenbankzugriff ist auf die
  Container-`psql`-Abfragen beschränkt (Smoke: nur `SELECT`).
- `--dry-run`: Konsistenzprüfung und Plan, kein HTTP-Request, kein Prozessaufruf, kein Bericht.
- Exit-Codes: `0` kein FAIL, `1` mindestens ein FAIL, `2` Aufruf/Preflight verweigert.

## Synthetische Daten

Alle Konten tragen Präfix und Domain aus Konstanten (`SYNTH_PREFIX`, `SYNTH_DOMAIN` in den
Skripten; Acceptance `numra-acc-`, Smoke `numra-smoke-`, Domain `example.com`). Am Ende
löscht Schritt 12 jedes angelegte Konto per `POST /v1/account/delete-all` (auch nach Fehlern)
und prüft per Zähler, dass keine aktiven synthetischen Konten und keine Nutzdaten
(`people`, `report_jobs`) übrig sind. Schlägt das Löschen fehl, steht ein FAIL im Bericht und
eine Meldung zur manuellen Bereinigung auf der Konsole. Passwörter und Cookies leben nur im
Prozess und fließen nie in Ausgabe oder Bericht (zentrale Redaktion).

## PDF-Inhaltsprüfung

Statt des früheren SKIP ("weder pdftotext noch Bibliothek") liest `content_checks.py` den
Export mit pypdf und prüft reproduzierbar:

| ID | Prüfung |
|---|---|
| `7.9` | Seitenzahl im Bereich (Standard 1 bis 200) |
| `7.10a` | Text extrahierbar (mindestens 60 Wörter) |
| `7.10b` | Text deutsch (Anteil deutscher Funktionswörter ≥ 0,08 und mehr als doppelt so hoch wie englischer) |
| `7.10c` | null Platzhalter-/Token-Treffer (`[a:`, `{{`, `}}`, `{name}`, `<a_b>`, `%(`, `profile_fact`, `metric:`) |

Ein nicht lesbares PDF ist ein FAIL (`pypdf` fehlt: Exit 2 mit Installationshinweis), nie ein
SKIP. Der Smoke-Test führt dieselben Prüfungen nach seinem PDF-Export aus (`10.8-9 bis 10.8-10c`).
Tests (`scripts/acceptance/tests/test_content_checks.py`) erzeugen deterministische PDFs
und enthalten die Negativ-Gegenproben (Platzhalter, englischer Text, zu wenig Text, kaputte
Datei).

## Berichte

Markdown und JSON nach `--report-dir` (0600) mit Zeitstempel, Ziel, Ziel-SHA, Skriptversion,
Prüfumfang, PASS/FAIL/SKIP/INFO je Schritt, Einschränkungen und Gesamtergebnis. Die
Marker-Phase akzeptiert nur einen echten (kein Dry-Run) PASS-Bericht für genau Ziel und
SHA, jünger als `MAX_SMOKE_AGE_S`. Berichte enthalten weder Secrets noch Mailadressen.

## Grenzen

- Die Sprachprüfung ist eine Häufigkeitsheuristik, die LLM-Qualität wird nur formal geprüft
  (Platzhalter, Länge, Sprache), nicht inhaltlich.
- Der Smoke-Test löst pro Lauf einen echten LLM-Aufruf aus (QUICK-Report).
- Die Unit-Tests laufen ohne Netz und Docker (Fakes); sie belegen Guards, Dry-Run,
  Cleanup-Logik, Berichtsinhalt und PDF-Prüfung, nicht das Verhalten eines echten Stacks.

## Tests

```bash
uv run --no-project --with pytest --with "pypdf>=6.19.0" \
  pytest scripts/ops_report scripts/acceptance -q
```
