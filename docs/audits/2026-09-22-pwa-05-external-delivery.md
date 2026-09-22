# PWA-05 — Externer Nachweis der E-Mail-Zustellung über Resend

- **Datum:** 2026-09-22 (Audit-Stack auf agent0)
- **Umgebung:** `numra-audit` (`ENVIRONMENT=test`), `EMAIL_BACKEND=smtp` gegen
  `smtp.resend.com:587` mit STARTTLS; Provider: Resend (Transport über Amazon SES,
  eu-west-1) → Cloudflare Email Routing → kontrolliertes Postfach
- **Produktion:** unverändert (`EMAIL_BACKEND` dort weiterhin `disabled`, kein Deploy)
- **Issue:** #121 (PWA-05)

## 1. Was diese Abnahme belegt

Der frühere Nachweis endete am Loopback-Sink: Code- und Transportpfad vollständig
bewiesen, **externe** Zustellung nicht. Dieser Lauf schließt genau diese Lücke — die
Nachricht verlässt den Host, passiert den echten Provider und kommt im kontrollierten
Postfach an, nachweisbar an den Authentifizierungsergebnissen des Empfängers.

## 2. Auflösung einer Vorgaben-Kollision (Empfängeradresse)

Resend weist Empfänger unter `example.com` grundsätzlich ab:

```text
550 Invalid `to` field. Please use our testing email address instead of domains
    like `example.com`.
```

Die Domain ist per RFC 2606 reserviert und damit kein zustellbares Ziel. Die Vorgabe
„neue synthetische `@example.com`-Konten **und** echte Zustellung über Resend" ist
zusammen nicht erfüllbar. Aufgelöst wurde es so, dass beide Absichten erhalten bleiben:

- **Konto bleibt synthetisch** (`@example.com`) — es wird keine reale Person berührt;
- **Zustellung geht an das kontrollierte Postfach** `pwa-test@avenyth.de`, pro Lauf mit
  eindeutigem Plus-Tag, damit Nachrichten einem Lauf zuzuordnen sind.

## 3. Abnahmelauf `20260922T205442Z` (Plus-Tag `pwa0589832e8f`)

```text
register (synthetisches Konto) .................. 201
register (Plus-Tag-Konto) ....................... 201
request-email-verification → echter Provider .... 204
forgot-password → echter Provider ............... 202
anti-enumeration bekannt/unbekannt .............. 202/202, Body identisch
verify ungültiger Token ......................... 400
verify leerer Token ............................. 422
reset ungültiger Token .......................... 400
reset zu kurzes Passwort ........................ 422
login mit gesetztem Passwort .................... 200
delete-all (beide Konten, Produktpfad) .......... 204 / 204
findings ........................................ []
```

## 4. Zustellung und Authentifizierung (Empfänger-Header)

Belege am zugestellten Objekt, nicht an der Absenderantwort:

| Prüfung | Ergebnis |
|---|---|
| Ankunft im Postfach | ja (Header der zugestellten Nachricht) |
| Transportweg | Resend → SES `eu-west-1` → Cloudflare Email Routing → Postfach |
| SPF | `spf=pass` (Cloudflare **und** Google) |
| DKIM | `dkim=pass header.i=@mail.avenyth.de header.s=resend` |
| DMARC | `dmarc=pass` (Policy `p=NONE`) |
| ARC | `arc=pass` |
| TLS | `ESMTPS TLS1_3` auf beiden Hops |
| `From` | `AVENYTH <no-reply@mail.avenyth.de>` |
| `Return-Path` | `cfbounces+ndrdrop@avenyth.de` (Cloudflare-Routing) |

Nachrichteninhalte, Links und Token werden hier nicht wiedergegeben.

## 5. Token- und Log-Sicherheit (selbst gemessen, nicht übernommen)

| Prüfung | Ergebnis |
|---|---|
| Speicherung | nur `token_hash`-Spalten; **0** Klartext-Spalten in `email_verification_tokens` / `password_reset_tokens` |
| Rate-Limit | `forgot-password`: Sequenz endete in **429** (5/Stunde/IP) |
| Secrets in Logs | **0** Treffer für Token-Muster und **0** für die Resend-Key-Form, geprüft in API und beiden Workern |
| Kaskade nach Löschung | **0** Restkonten, **0** verwaiste Token |

## 6. Änderungen am Audit-Stack (Produktion unberührt)

| Datei | Änderung |
|---|---|
| `/etc/numra/audit.env` | `EMAIL_BACKEND=smtp` plus die nicht-geheimen SMTP-Werte; `SMTP_PASSWORD` in dieser Datei, Rechte `600`, Verzeichnis `700`. Backups: `audit.env.bak-smtp-<stamp>`, `audit.env.bak-pre-smtpcfg-<stamp>` |
| `/opt/numra/audit-compose.yml` | Kopfkommentar korrigiert (die Aussage „no real mail ever leaves the host" gilt nicht mehr) |
| Dienst | nur `api` neu erstellt; Worker unverändert (sie senden keine Mail — im Code geprüft: `email_sender` nur in `routes/auth.py`) |

`WEB_APP_BASE_URL` war bereits korrekt auf die Audit-Origin gesetzt, Verifikations- und
Reset-Links führen daher nicht auf Produktion.

## 7. Abweichung vom Vorgaben-Port

Der vorgesehene Port **465 war nicht erreichbar** (vier Versuche, beide A-Records,
zusätzlich aus dem API-Container heraus). Erreichbar und TLS-verifiziert waren `587`
(STARTTLS, TLS 1.3) und `2465` (implizites TLS, TLS 1.3). Verwendet wird **587 mit
STARTTLS** — der Standard-Submission-Port.

## 8. Was diese Abnahme nicht behauptet

- **Keine Produktionsfreigabe.** Produktion bleibt auf ihrem Stand, `EMAIL_BACKEND`
  dort `disabled`, kein Deploy. Für Produktion ist ein eigener Key und ein eigenes
  Deploy-Go nötig.
- **Kein Teardown.** Audit-Stack, Volumes und das Postfach bleiben bestehen.
- **Die Verträge sind nicht neu erfunden**, sondern erneut ausgeführt: Einmalnutzung,
  Replay, Manipulation und Ablauf waren bereits gegen einen Loopback-Sink bewiesen und
  sind zusätzlich im Repo-Testbestand verankert.
