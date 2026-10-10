# D4 Limits, Zähler und Budgetvorschlag

Stand: 2026-10-10. Teil 2 von 2 der D4-Arbeit (Teil 1: `2026-10-09-d4-beta-transition.md`).
Alle Limits sind standardmäßig AUS. Konkrete Werte in Abschnitt 6 sind ein Vorschlag,
keine Produktionswerte; es wird nichts automatisch gesetzt.

## 1. Was begrenzt wird

Pro Konto und Funktionsgruppe zwei unabhängige, einzeln optionale Grenzen:

| Grenze | Bedeutung | Env |
|---|---|---|
| Einheiten je Zeitfenster | gleitendes Fenster (`created_at > jetzt - Fenster`) | `QUOTA_<F>_MAX`, `QUOTA_<F>_WINDOW_SECONDS` (Default 86400) |
| gleichzeitig laufend | Einheiten im Zustand `active` | `QUOTA_<F>_MAX_CONCURRENT` |

`<F>` = `REPORT`, `ANALYSIS`, `COPILOT`. Zusätzlich `QUOTA_ACTIVE_STALE_SECONDS`
(Default 3600): eine Einheit, die so lange `active` ist, gilt als verwaist (abgestürzter
Prozess) und blockiert das Parallelitätslimit nicht mehr; muss größer sein als die
längste Jobdauer (Prod-Maximum bisher 1688 s). Die Variablen liest nur der `api`-Dienst
(Worker settlen/geben nur zurück); leer oder ungesetzt = unbegrenzt.

Eine "Einheit" ist: ein Berichts-Job, ein Analyse-Job (Beziehung ODER Schatten, gemeinsames
Budget `analysis`), eine Copilot-Nachricht
(geteilt/privat/persönlich, gemeinsames Budget `copilot`).

## 2. Warum Postgres statt Redis-Lua

Die Reservierung muss mit der Job-/Nachrichtenzeile gemeinsam committen oder zurückrollen,
und ein gescheiterter Job muss seine Einheit genau einmal zurückgeben. Das ist mit der
Datenbank-Transaktion trivial; ein Redis-Zähler wäre davon entkoppelt (zurückgerollter Job =
aufgeblähter Zähler, Absturz zwischen INCR und Insert = Drift). Der vorhandene Redis-Rate-Limiter
(`rate_limit_by_user`, z. B. 30 Anfragen/h) bleibt als grobe Burst-Bremse unverändert bestehen;
er begrenzt Anfragen, nicht Kontingent-Einheiten.

Mechanik (`services/usage_quota.py`, `repositories/usage_quota.py`, Tabelle
`usage_reservations`):

1. `pg_advisory_xact_lock(hashtextextended('usage:<user>:<feature>'))` serialisiert alle
   Reservierer EINES Kontos und EINER Funktion bis zum Transaktionsende. Andere Konten und
   Funktionen warten nie aufeinander.
2. Existiert `(feature, ref_id)` schon, wird nichts verbraucht (Idempotenz, `UNIQUE`).
3. Zählen (Fenster, Parallelität), vergleichen, `INSERT ... ON CONFLICT DO NOTHING`.
4. Atomarität: Prüfen und Einfügen laufen unter dem Lock; 20 gleichzeitige Anfragen bei
   Limit 5 ergeben genau 5 Erfolge (Test `test_twenty_parallel_requests_at_limit_five_yield_exactly_five`,
   ebenso 10 parallele Copilot-Nachrichten bei Limit 3).

Der Ledger enthält nur IDs, Funktion, Zustand und Zeiten (keine Inhalte, keine PII) und wird
beim Löschen des Kontos per `ON DELETE CASCADE` entfernt. Er wächst mit der Nutzung; Zeilen
außerhalb des Fensters sind für die Zählung irrelevant und können später per Retention-Job
gelöscht werden (nicht Teil dieses PR).

## 3. Verhalten bei Fehlern und Wiederholungen

| Situation | Wirkung auf das Kontingent |
|---|---|
| Limit erreicht | `429 QUOTA_EXCEEDED`, nichts angelegt, nichts verbraucht |
| Gleicher `Idempotency-Key` erneut (Bericht/Analyse) | bestehender Job wird zurückgegeben, KEINE zweite Einheit |
| Job scheitert retrybar, wird neu eingereiht | dieselbe Reservierung bleibt `active`, keine zweite Einheit |
| Job erreicht `COMPLETE` | `settled`: zählt weiter für das Fenster, nicht mehr für Parallelität |
| Job scheitert endgültig (`FAILED`, auch `BETA_ACCESS_REQUIRED` beim Worker-Start) | `released`: Einheit zurückgegeben |
| Copilot-Antwort `FAILED` (Provider/Validierung) oder Ausnahme | `released` |
| Copilot-Antwort `COMPLETE` | `settled` |
| Neuer `POST` ohne Key (auch "Neu generieren") | neue Einheit |
| Abgestürzter Prozess, Reservierung bleibt `active` | nach `QUOTA_ACTIVE_STALE_SECONDS` kein Parallelitäts-Block mehr; im Fenster zählt sie weiter |
| Fehler beim Anlegen des Jobs (Rollback) | Reservierung wird mit zurückgerollt |

Hinweis: Rückgabe bei Fehlschlag heißt, dass ein Provider-Aufruf, der Tokens verbraucht
hat und danach scheitert, das Kontingent nicht belastet. Das schützt Nutzer vor Ausfällen,
nicht das Budget; dagegen wirkt das Parallelitätslimit und `numra_llm_max_retries`.
Prod-Stand: 12 von 18 Berichts-Jobs sind FAILED (Rückgabe ist also relevant).

Der Copilot reserviert und committet VOR dem LLM-Aufruf (Lock nicht während der Generierung
gehalten, parallele Nachrichten sehen die Einheit als laufend). Zu diesem Zeitpunkt hat die
Request-Transaktion nur gelesen.

## 4. Einstiegspunkte (vollständig, per Code-Suche inventarisiert)

Gate (Teil 1) und Quote greifen an denselben Stellen; Reihenfolge: Flag -> Auth -> CSRF ->
Beta-Gate (403) -> Rate-Limit -> Fachprüfungen (404/409/422) -> Quote (429).

| Funktion | Einstieg | Quote reserviert in | Freigabe/Settle |
|---|---|---|---|
| Bericht (inkl. Neuerzeugung) | `POST /v1/reports` | `report_service.create_report_job` (nach Idempotenz-Early-Return, `ref=job.id`) | `repositories/reports.py::mark_job_status`, `fail_job_terminally` |
| Beziehungsanalyse | `POST /v1/workspaces/{id}/relationship-analysis` | `relationship_analysis_service.create_relationship_analysis_job` | `repositories/analysis.py::mark_job_status`, `fail_job_terminally` |
| Schattendynamik | `POST /v1/workspaces/{id}/shadow-dynamics` | `create_shadow_dynamics_job` | wie oben |
| Copilot geteilt/privat | `POST /v1/workspaces/{id}/copilot/threads/{tid}/messages` | `copilot_service._persist_message_pair` | dort |
| Copilot persönlich | `POST /v1/me/copilot/threads/{tid}/messages` | `copilot_service._persist_message_pair` | dort |
| Worker-Jobstart Bericht | `worker.run_one_cycle` | (Reservierung besteht seit dem Enqueue) | Gate-Recheck, bei Fehlschlag `released` |
| Worker-Jobstart Analyse | `analysis_worker.run_one_cycle` | (dito) | dito |

Es gibt keinen separaten Regenerations-Endpunkt: "Neu erzeugen" ist ein neuer `POST`
(Quote) bzw. derselbe `POST` mit gleichem `Idempotency-Key` (keine Quote). Bewusst NICHT
begrenzt und ohne Gate: Lesen, Thread-Anlage, Exporte (PDF, kein LLM), `GET .../evidence-results`
und `POST .../pattern-analyses` (rein rechnerisch, kein LLM, keine Kosten), Check-in-Auswertung
(deterministisch, kein LLM).

Jobs, die VOR dem Einschalten der Limits eingereiht wurden, haben keine Reservierung;
Settle/Release sind dort wirkungslose No-ops. Das Einschalten zählt ab Null (Altnutzung
im Fenster wird nicht rückwirkend angerechnet).

## 5. Fehlerformat

```
HTTP 429  Retry-After: <s>
{"code":"QUOTA_EXCEEDED","message":"quota exceeded for report (window limit 3)",
 "feature":"report","limit_kind":"window"|"concurrent","limit":3,"retry_after_seconds":<s>}
```

`retry_after_seconds` beim Fenster: Zeit bis die älteste zählende Einheit herausfällt;
bei Parallelität pauschal 30 s. Das Web zeigt daraus "Du hast dein Nutzungslimit für diese
Funktion erreicht. Bitte versuche es in etwa N Minuten erneut." (`api/client.ts`).

## 6. Nutzungsdaten und Budgetvorschlag (VORSCHLAG, nicht aktiv)

Quelle: schreibfreie Aggregation der Prod-DB am 2026-10-10 (`scripts/ops/llm_usage_report.sql`,
READ ONLY, nur Zähler und Summen). NULL-Tokens werden nie als 0 gewertet.

### 6.1 Gemessener Bestand

| Größe | Wert |
|---|---|
| `llm_generations` Zeilen gesamt | 1 (Copilot, 2026-10-09; Tabelle ist neu) |
| Davon Tokens vorhanden | prompt 1105, completion 603 (n = 1); NULL-Anteil 0 von 1 |
| Copilot-Dauer (n = 1) | 3,9 s, 1 Provider-Aufruf je Nachricht |
| Berichts-/Analyse-Aufrufe in `llm_generations` | 0 (liefen vor Einführung des Logs), Tokens daher UNBEKANNT |
| Berichts-Jobs | 18 gesamt: 6 `COMPLETE` (Ø 2 s, max 5 s), 12 `FAILED` (Ø 551 s, max 1688 s, Ø 2,3 Versuche) |
| Analyse-Jobs | 1, `COMPLETE`, 138 s, 2 Versuche |
| Copilot-Nutzernachrichten | 1 (0 fehlgeschlagen) |
| Aktive Konten / Konten mit Nutzung | 5 / 4 |
| Spitze je Konto (7 Wochen) | 10 Berichts-Jobs; 5 Berichts-Jobs an einem Tag (2026-08-22, alle Konten zusammen) |

Die Ø 2 s der 6 `COMPLETE`-Berichte deuten auf Mock-/Testläufe hin (nicht belegt); die
`FAILED`-Jobs tragen überwiegend Provider-Fehler (Timeout, leere/ungültige Antwort) und
Validierungsfehler im Fehlercode. Belastbare Kosten je Bericht oder Analyse lassen
sich aus diesen Daten NICHT ableiten; ein Preis je Token ist weder im Repo noch in der DB
hinterlegt und wird hier nicht angenommen.

### 6.2 Annahmen

1. Geschlossene Beta, höchstens 25 freigeschaltete Konten.
2. Die Obergrenze je Konto soll das beobachtete Nutzungsmaximum nicht behindern, aber
   einen Ausreißer (Schleife, Skript, geteilter Zugang) auf einen kleinen Faktor begrenzen.
3. Copilot: Tokens je Nachricht ~ 1,7 k (1105 + 603) ist EIN Messwert; Prompts wachsen mit
   der Threadlänge, daher Faktor 3 Sicherheitsaufschlag für die Obergrenze (~ 5 k).
4. Berichte und Analysen: Tokenzahl unbekannt, deshalb Limits in Einheiten, nicht in Kosten.

### 6.3 Vorschlag je Konto (Beta)

| Funktion | Einheiten je 24 h | gleichzeitig | Begründung |
|---|---:|---:|---|
| Bericht | 3 | 1 | beobachtete Spitze 5/Tag (alle Konten zusammen), 10 in 7 Wochen je Konto; ein langer Job (bis 28 min) soll keinen zweiten parallel starten |
| Analyse (Beziehung, Schatten) | 2 | 1 | bisher 1 Job insgesamt; Jobdauer 138 s bei 2 Versuchen |
| Copilot-Nachricht | 30 | 1 | deutlich strenger als die bestehende HTTP-Drossel (30 Anfragen/h, rechnerisch bis zu 720/Tag), die nur eine Burst-Bremse ist und kein Tagesbudget; 1 Aufruf je Nachricht, ~ 4 s |

Daraus ergibt sich die Obergrenze an Provider-Aufrufen und Tokens pro Tag und Konto:

| Größe | Rechnung | Ergebnis |
|---|---|---|
| Copilot-Tokens je Konto und Tag (Obergrenze) | 30 x ~ 5 k (Annahme 3) | ~ 150 k Tokens |
| Copilot-Tokens bei 25 Konten | 25 x 150 k | ~ 3,75 M Tokens/Tag (Obergrenze, real weit darunter) |
| Berichte bei 25 Konten | 25 x 3 | <= 75 Berichts-Jobs/Tag |
| Analysen bei 25 Konten | 25 x 2 | <= 50 Analyse-Jobs/Tag |
| Kosten | Tokens x Preis | nicht berechenbar, Preis je Token und Berichts-/Analyse-Tokens fehlen |

### 6.4 Empfohlenes Vorgehen

1. Deploy mit Limits AUS (Default), `llm_generations` füllt jetzt auch für Berichte und
   Analysen Tokenzahlen (soweit der Provider sie liefert).
2. Nach 1 bis 2 Wochen `scripts/ops/llm_usage_report.sql` erneut laufen lassen; die
   Summen über nicht-NULL-Werte und den NULL-Anteil je Funktion ersetzen die Annahmen 3 und 4.
3. Preis je Token des Providers eintragen, daraus ein Tagesbudget ableiten, dann
   Limits per Env setzen, z. B. `QUOTA_REPORT_MAX=3`, `QUOTA_REPORT_MAX_CONCURRENT=1`,
   `QUOTA_ANALYSIS_MAX=2`, `QUOTA_ANALYSIS_MAX_CONCURRENT=1`, `QUOTA_COPILOT_MAX=30`,
   `QUOTA_COPILOT_MAX_CONCURRENT=1`; api neu starten.
4. Rollback: Variablen leeren und api neu starten; der Ledger bleibt ungenutzt liegen.
