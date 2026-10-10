# ADR — Proxy-Vertrauensgrenze und Rate-Limit-Schlüssel

Stand: 2026-10-10 · Status: Accepted · Umsetzung in zwei gestapelten PRs
(PR 1: Inventur + Shared Secret/Header-Vertrauen · PR 2: Rate-Limit-Schlüssel und -Limits)

## Kontext und Problem

Die API kennt als Client-Adresse nur den TCP-Peer (`request.client.host`). Browser-Verkehr
läuft ausschließlich über den Next.js-Route-Handler `apps/web/src/app/api/[...path]/route.ts`
(BFF). Für die API ist damit jeder Browser-Nutzer **dieselbe Peer-Adresse (der Web-Container)**:

- Alle IP-basierten Limits (`rate_limit_by_ip`: login, register, forgot/reset-password,
  verify-email) teilen sich **einen** Zähler für alle Web-Nutzer. Ein Angreifer sperrt damit
  Login/Registrierung für alle (Denial of Service); umgekehrt gibt es keinen echten
  IP-Schutz pro Angreifer.
- Der BFF reicht **alle** Client-Header ungefiltert weiter (nur `host`, `connection`,
  `content-length` fallen weg), einschließlich eines vom Client gesetzten `X-Forwarded-For`.
  Die API wertet keine Forwarded-Header aus (uvicorn-Default `--proxy-headers` mit
  `forwarded-allow-ips=127.0.0.1` würde sie nur für Loopback-Peers anwenden); es gibt aber
  keine Authentisierung des Proxys selbst.

## Inventur (Ist-Stand, Code-Suche am Stand `31dde5e`)

| Zugriffspfad | Weg zur API | Client-IP heute | Credential | Vertrauensgrenze |
|---|---|---|---|---|
| Browser (Web-UI) | Internet → Cloudflare-Tunnel/Tailscale `:8443` → Web `127.0.0.1:17300` → BFF `/api/*` → `http://api:8000` | Peer = Web-Container (für alle gleich) | Session-Cookie + CSRF | Web→API: internes Docker-Netz, **kein** Proxy-Auth |
| Mobile-App (Expo) | `EXPO_PUBLIC_API_URL` (nur Origin) `/v1/auth/mobile/*`, `/v1/people*` – ohne Web-Proxy | Peer des Ingress | Bearer-Token | direkt; API-Port ist in Prod nur auf `127.0.0.1:17800` gebunden → Erreichbarkeit über Ingress/Tunnel, nicht im Repo definiert |
| Host-Healthcheck (`numra-healthcheck.timer`) | `curl 127.0.0.1:17800/17801/v1/health/ready` | Docker-Gateway | keines | Host-lokal, read-only |
| Externer Uptime-Probe (GitHub Actions) | `https://avenyth.de/api/v1/health/ready` → Cloudflare-Tunnel → Web → **BFF** → API | Peer = Web-Container | keines | läuft durch den BFF (bekommt das Secret automatisch) |
| Admin-UI / `/v1/admin/*` | wie Browser (Cookie, `require_admin`, CSRF) | wie Browser | Session + Rolle | BFF |
| Admin-CLI (`python -m numra_api.cli`) | direkt auf DB, keine HTTP-Grenze | – | DB-Zugang | Container/Host |
| PDF-Dienst (`apps/pdf`) | API → `http://pdf:4300` (Bearer `PDF_INTERNAL_TOKEN`); PDF ruft die API **nicht** zurück | – | eigenes Token | ausgehend aus der API |
| Worker / Analysis-Worker | direkt DB + Redis, kein HTTP-Eingang | – | – | intern |

Rate-Limit-Schlüssel heute (`deps.py`): `rate_limit_by_ip` = `scope + HMAC(peer-IP)`;
`rate_limit_by_user` = `scope + HMAC(user.id)` mit `user` aus der serverseitigen Session
(nie aus Headern). Backend: `InMemoryRateLimiter` (Dev/Test) oder `RedisRateLimiter`
(Prod, in Produktion erzwungen). Fixed-Window; Redis-Ausfall → Exception → 500 (kein
definiertes Fallback).

## Entscheidung

1. **Shared Secret** `INTERNAL_PROXY_SHARED_SECRET` (+ `_PREVIOUS`) zwischen BFF und API,
   Header `X-Numra-Proxy-Auth`. Direkter Konstantzeit-Vergleich (`hmac.compare_digest`) gegen
   beide konfigurierte Werte ohne Short-Circuit. **Kein HMAC über Methode/Pfad/Zeitstempel**:
   Der Hop ist internes Docker-Netz ohne TLS; ein signierter Zeitstempel verhindert Replay
   nur, wenn er den Body bindet, und bringt gegen einen Angreifer mit Mitlesezugriff im
   Bridge-Netz nichts, der ohnehin Cookies mitliest. Einfachheit gewinnt (Core Principle 1).
2. **Forwarded-Client-IP** wird nur übernommen, wenn (a) das Secret gültig ist **und**
   (b) der TCP-Peer in `TRUSTED_PROXY_CIDRS` liegt. Sonst gilt die Peer-Adresse. Leere
   Liste = nie. uvicorn läuft mit `--no-proxy-headers`, damit allein die Middleware entscheidet.
3. **Identität nie aus Headern.** Es gibt keinen Code-Pfad, der eine User-ID aus einem
   Header liest; authentifizierte Limits nutzen ausschließlich `user.id` aus der Session
   (Test belegt: gefälschtes `X-User-Id` ändert den Schlüssel nicht).
4. **Web-Rand** (BFF) entfernt vom Client kommende `X-Numra-*`, `X-Forwarded-*`,
   `Forwarded`, `X-Real-IP`, `X-Client-IP`, `True-Client-IP`, `CF-Connecting-IP`, `X-User-Id`,
   `X-User` und setzt selbst: `X-Numra-Proxy-Auth` und – bei `TRUSTED_PROXY_HOPS ≥ 1` –
   `X-Forwarded-For` mit genau einem Wert: dem von der N-ten vertrauenswürdigen Instanz
   **von rechts** angehängten Eintrag (linke Einträge sind client-kontrolliert). Standard
   `TRUSTED_PROXY_HOPS=0` = keine Client-IP (heutiges Verhalten).
5. **`PROXY_SECRET_ENFORCED`**: `false` (Übergang): ungültiges/fehlendes Secret → Peer-IP,
   Warn-Log ohne Secret, nichts wird abgelehnt. `true`: erzwungen wird **nur** für
   (a) Requests mit Session-Cookie und (b) Requests, die `X-Numra-Proxy-Auth` mitsenden; ohne
   gültiges Secret → `403 PROXY_AUTH_FAILED` (generischer Text). Der Cookie-Name wird exakt wie
   von Starlette geparst (`cookie_parser`; Varianten mit Leerzeichen/Tab/mehreren Cookies sind
   getestet). `X-Forwarded-For`/`X-Real-IP`/`Forwarded` **ohne** gültiges Secret werden ignoriert
   (Peer-IP zählt), nie abgelehnt – Mobile (Bearer) und Health-Probe hinter
   Cloudflare/`tailscale serve` tragen diese Header. Begründung für das Cookie:
   Cookie-Sessions sind nur über den BFF vorgesehen (Origin-/CSRF-Modell). **Nicht betroffen**
   (bewusst): Mobile (Bearer), `/v1/health/*`, `/v1/public/*`, Login/Registrierung ohne Cookie.
6. **Rotation/Rückroll** über zwei gleichzeitig gültige API-Secrets (Runbook
   `docs/ops/2026-10-10-proxy-secret-rollout.md`). Das Web sendet immer nur das aktuelle.
7. **Nicht geändert:** Netzwerkisolation, Sessionprüfung, Origin-Validierung, CSRF.
8. **Rate-Limits (PR 2):** vor Anmeldung IP (aus vertrauenswürdiger Quelle), danach `user_id`;
   zusätzliche strengere Grenzen für Login, Registrierung, Passwort-Reset und
   Verifikations-Mail pro IP **und** pro Ziel-Adresse/Konto (Schlüssel = HMAC der normalisierten
   Adresse, unabhängig davon, ob das Konto existiert; identische Antworten → keine Enumeration).

## Folgen und Grenzen

- **Der IP-Schutz greift erst nach Messung und `TRUSTED_PROXY_HOPS=1`.** Mit dem Default `0` (und
  ohne gesetztes Secret/CIDRs) bleibt alles wie heute: alle Web-Nutzer teilen einen IP-Bucket.
  Dieser PR liefert die Vertrauensgrenze, nicht allein die Verbesserung.
- Zwei Annahmen sind **auf dem Host zu messen**, bevor `TRUSTED_PROXY_HOPS=1` gesetzt wird:
  dass sowohl der Cloudflare-Pfad als auch `tailscale serve` genau einen Eintrag rechts an
  `X-Forwarded-For` anhängen. Ist es falsch, entstehen schlimmstenfalls wieder gemeinsame
  Zähler (fällt auf Ist-Verhalten zurück) – ein linker, client-kontrollierter Eintrag wird
  nie benutzt.
- Mobile-Clients ohne BFF sind in der Praxis hinter demselben Ingress; ohne Secret bleibt ihr
  Schlüssel der Peer des Ingress. Das ist **unverändert** und wird nicht durch das Secret gelöst.
- Das Secret im Header ist im Klartext im internen Netz (kein TLS auf dem Hop). Schutz:
  Netzwerkisolation, Secret nur in Server-Env.
- Unter `PROXY_SECRET_ENFORCED=true` müssen Operator-`curl`s mit Cookie gegen die API selbst
  den Header mitsenden (`curl -H @-` aus stdin/Datei, **nicht** als Argument).
- Per-Account-Limits (PR 2) erlauben theoretisch gezieltes Sperren eines Kontos durch
  Fremde; gemildert durch hohe Schwellen und das IP-Limit davor.

## Rate-Limit-Schlüssel und Limits (PR 2)

| Phase | Schlüssel | Quelle |
|---|---|---|
| vor Anmeldung | HMAC(Client-IP) | `client_ip_of`: weitergeleitete IP nur bei gültigem Secret + vertrauenswürdigem Peer, sonst Peer |
| nach Anmeldung | HMAC(`user.id`) | serverseitig aus der Session (`get_current_user`), nie aus Headern |
| Ziel-Adresse | HMAC(`normalize_email(email)`) | Request-Body, **vor** dem Konto-Lookup, für bekannte und unbekannte Adressen gleich |

Alle Schlüssel sind mit `SESSION_SECRET` pseudonymisiert (keine Klartext-IP/-Adresse in Redis).

| Policy (Default Anzahl/Sekunden) | Schlüsselart | Zählt | Endpunkte |
|---|---|---|---|
| `auth:login` 10/60 · `auth:mobile-login` 10/60 | IP | jeden Versuch | `/login`, `/mobile/login` |
| `auth:login:target` 20/900 | Ziel-Adresse | Versuch wird **atomar vor der Passwortprüfung** reserviert (INCR); Erfolg setzt zurück → es sammeln sich nur Fehlversuche | `/login` und `/mobile/login` teilen den Zähler |
| `auth:register` 5/3600 · `auth:register:target` 3/3600 | IP · Ziel-Adresse | jeden Versuch | `/register` |
| `auth:forgot_password` 5/3600 · `…:target` 3/3600 | IP · Ziel-Adresse | jeden Versuch | `/forgot-password` |
| `auth:reset_password` 10/3600 · `auth:verify_email` 10/3600 | IP | jeden Versuch | `/reset-password`, `/verify-email` (Token statt Adresse im Body) |
| `auth:request_email_verification` 5/3600 · `…:target` 5/3600 | Nutzer-ID · eigene Adresse | jeden Versuch | `/request-email-verification` |

Bewusst **kein** IP-Limit auf der authentisierten Verifikations-Route: nach der Anmeldung zählt die
`user.id`; bei `TRUSTED_PROXY_HOPS=0` würde ein IP-Bucket von allen Web-Nutzern geteilt.

Überschreibbar per `RATE_LIMIT_OVERRIDES` (JSON, beim Start validiert: bekannte Policy, Anzahl
1..10000, Fenster 1..604800 s; sonst Startfehler). Bestehende Nutzer-Limits anderer Router bleiben
unverändert (bereits Nutzer-ID-basiert).

**Keine Enumeration:** Die Ziel-Adress-Zähler greifen vor jeder Kontoprüfung; ein Fehlversuch
(falsches Passwort, unbekannte Adresse, deaktiviertes Konto) zählt gleich. Beim Login läuft Argon2
immer: für eine unbekannte Adresse gegen einen Dummy-Hash mit denselben Parametern
(`dummy_password_hash`), damit Antwortzeit (~5 ms vs. ~118 ms) die Existenz nicht verrät (Test prüft
den Dummy-Pfad per Aufrufspur, kein Timing-Test; Restunschärfe: DB-Lookup und Jitter). 429-Antwort, Body und
Verlauf sind für registrierte und unbekannte Adressen identisch (Test vergleicht beide). Das
bestehende `409 EMAIL_ALREADY_REGISTERED` bei `/register` ist eine **vorhandene** Enumerationsfläche
und nicht Teil dieses ADR (bewusst unverändert).

### Risikobewertung: Sperren fremder Konten (Login)

Ein Ziel-Limit kann von Dritten missbraucht werden, um Logins für ein Konto (auch Admins) zu
verhindern. Maßnahmen und Restrisiko:
- Der Versuch wird atomar **vor** der Passwortprüfung reserviert (kein getrenntes Prüfen/Zählen: 40 parallele Fehlversuche bei Limit 5 lassen genau 5 durch, für Web und Mobile, Memory und Redis getestet); ein erfolgreicher Login setzt den Zähler zurück, es sammeln sich also nur Fehlversuche. Legitime
  Nutzer mit Tippfehlern erreichen 20 Fehlversuche/15 min nicht.
- Davor liegt das IP-Limit (10/min je vertrauenswürdiger IP); Fehlversuche aus gesperrten IPs
  erreichen den Ziel-Zähler gar nicht.
- **Restrisiko (akzeptiert):** Ein Angreifer mit wechselnden IPs hält ein Konto mit ~1,4
  Fehlversuchen/min dauerhaft gesperrt (während der Sperre wird auch das richtige Passwort
  abgewiesen – das ist der Brute-Force-Schutz). Das Konto bleibt über „Passwort vergessen“ erreichbar
  (eigener Zähler), setzt aber den Login-Zähler nicht zurück. Abhilfe im Betrieb: Fenster/Schwelle per
  `RATE_LIMIT_OVERRIDES` anpassen oder den Schlüssel `auth:login:target:<hmac>` in Redis löschen
  (Operator). Eine IP-gebundene Entsperrung („bekannte Geräte“) ist bewusst nicht Teil dieser Stufe.
- Admin-Konten sind dadurch nicht stärker betroffen als andere; `/v1/admin/*` bleibt zusätzlich hinter
  Session, Rolle, CSRF und Origin.

**`forgot_password:target` (3/h) bleibt** als Schutz gegen Mail-Bomben auf eine fremde Adresse.
Trade-off: Ein Angreifer kann dem Opfer für bis zu eine Stunde das Anfordern einer Reset-Mail
verwehren (die Anforderung des Opfers erhält denselben 429 wie jede andere gesperrte Adresse).

**Mobile:** Mobile-Clients rufen die API ohne BFF auf; ohne Secret ist ihr IP-Schlüssel der Peer des
Ingress → **alle Mobile-Nutzer teilen sich 10 Logins/min** (`auth:mobile-login`). Restrisiko, Empfehlung:
Mobile-Ingress messen (welche Hops, welche `X-Forwarded-For`-Form) und dafür einen vertrauenswürdigen
Proxy-Pfad mit Hops definieren, danach das Limit je Client-IP erlauben. Mobile- und Web-Login teilen
bewusst `auth:login:target` (ein Konto = ein Fehlversuchszähler, sonst wäre der Ziel-Schutz über den
jeweils anderen Kanal umgehbar).

**Zähler-Ausfall (Redis nicht erreichbar):** fail-closed. Das ist die dokumentierte Fassung des
bisherigen Verhaltens (ungefangene Exception → 500): jetzt `503 RATE_LIMIT_UNAVAILABLE` mit
generischem Text, ohne Verbindungsdetails; Log nur mit Policy-Name. Folge: Redis-Ausfall = Anmeldung
nicht möglich (bereits vorher so, nur als 500). `/v1/health/*` ist nicht ratenbegrenzt.

**Atomarität:** `RedisRateLimiter.check` führt INCR und EXPIRE als ein Lua-Skript aus; ein Schlüssel
ohne TTL (z. B. aus dem früheren Zwei-Schritt-Ablauf) wird repariert statt dauerhaft zu sperren.
Ein nicht zählendes `peek` gibt es nicht mehr (Quelle der Race-Condition).

**IPv6:** IP-Schlüssel werden für IPv6 auf das /64-Präfix normalisiert (ein Bucket je /64).
**X-Forwarded-For:** Mehrere Header-Zeilen werden zusammengeführt; es zählt der rechteste Eintrag der letzten Zeile.

**Grenzen:** Fixed-Window (Randburst bleibt), Missbrauchsschutz statt Sicherheitsgrenze. Ein globales
IP-Limit für nicht authentisierte Nicht-Auth-Routen existiert weiterhin nicht (vorher auch nicht).
