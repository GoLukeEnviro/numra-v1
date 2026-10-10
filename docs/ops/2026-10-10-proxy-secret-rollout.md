# Runbook — Shared Secret Web↔API: Einführung, Rotation, Rückroll

Stand: 2026-10-10. Hintergrund: `docs/engineering/2026-10-10-adr-proxy-trust-and-rate-limit-keys.md`.
Alle Befehle verwenden nur Platzhalter; echte Werte liegen ausschließlich in
`/etc/numra/numra.env` (root, 0600) bzw. `/etc/numra/audit.env`. Nie im Repo, nie in
Prozessargumenten, nie in Chat/Tickets.

## Variablen

| Variable | Wo | Bedeutung |
|---|---|---|
| `INTERNAL_PROXY_SHARED_SECRET` | API **und** Web | aktuelles Secret, ≥ 32 Zeichen |
| `INTERNAL_PROXY_SHARED_SECRET_PREVIOUS` | nur API | zweites gültiges Secret (Rotation/Rückroll) |
| `PROXY_SECRET_ENFORCED` | API | `false` Übergang, `true` erzwingen (braucht gesetztes Secret, sonst Start-Fehler) |
| `TRUSTED_PROXY_CIDRS` | API | Peer-Netze, von denen eine weitergeleitete Client-IP akzeptiert wird (z. B. Compose-Netz des Web-Containers) |
| `TRUSTED_PROXY_HOPS` | Web | Anzahl vertrauenswürdiger Proxys vor Next.js; `0` = keine Client-IP |

Generierung (auf dem Host, Ausgabe nicht anzeigen/loggen):

```bash
umask 077; openssl rand -base64 48 | tr -d '\n' > /root/.new_proxy_secret   # dann per Editor in die Env-Datei übernehmen, Datei danach shred -u
```

## Einführung ohne Ausfall (Reihenfolge verbindlich)

0. Vorab (read-only): Compose-Netz des Web-Containers bestimmen, `docker network inspect <projekt>_default`
   → Subnetz für `TRUSTED_PROXY_CIDRS`. Prüfen, welche `X-Forwarded-For`-Form Cloudflare- und
   Tailscale-Pfad am Web ankommen lassen (genau ein rechter Eintrag je vertrauenswürdigem Hop).
1. **API zuerst, Übergangsmodus:** Secret + `TRUSTED_PROXY_CIDRS` setzen, `PROXY_SECRET_ENFORCED=false`;
   API neu starten. Web sendet noch kein Secret → Verhalten unverändert (Peer-IP).
2. **Web:** gleiches `INTERNAL_PROXY_SHARED_SECRET` setzen, zunächst `TRUSTED_PROXY_HOPS=0`;
   Web neu starten. Prüfen: Login im Browser funktioniert, `/api/v1/health/ready` liefert 200,
   API-Log enthält **keine** `proxy auth rejected`-Zeilen.
3. **Client-IP aktivieren:** `TRUSTED_PROXY_HOPS=1` am Web; neu starten. Prüfen: zwei Nutzer
   mit verschiedener IP teilen keinen Login-Zähler mehr (z. B. eigener Test-Account, Login-Fehlversuche
   von zwei Quellen); kein `forwarded client ip not accepted`-Warn-Log.
4. **Erzwingen:** `PROXY_SECRET_ENFORCED=true`, API neu starten. Prüfen: Browser-Login ok,
   Mobile-Login (Bearer) ok, Host-Healthcheck und Uptime-Probe ok;
   `curl -H 'Cookie: …'` direkt gegen die API ohne Header → `403 PROXY_AUTH_FAILED`.

Rückfall in jedem Schritt: Variable zurücksetzen und den betroffenen Dienst neu starten
(Schritt 4 → `PROXY_SECRET_ENFORCED=false`).

## Rotation

Das Web sendet immer nur das aktuelle Secret; die API akzeptiert bis zu zwei.

1. API: `INTERNAL_PROXY_SHARED_SECRET_PREVIOUS=<altes>`, `INTERNAL_PROXY_SHARED_SECRET=<neues>`; API neu starten
   (beide gültig, Web mit dem alten läuft weiter).
2. Web: `INTERNAL_PROXY_SHARED_SECRET=<neues>`; Web neu starten. Prüfen wie Einführung Schritt 2.
3. Nach Beobachtungsfenster (z. B. 24 h, keine `secret_mismatch`-Warnungen): API
   `INTERNAL_PROXY_SHARED_SECRET_PREVIOUS` entfernen; neu starten. Das alte Secret ist tot.

## Rückroll (neues Secret fehlerhaft/kompromittiert)

Solange Schritt 3 der Rotation **nicht** ausgeführt wurde, akzeptiert die API das alte Secret noch:
Web wieder auf das alte Secret stellen und neu starten. Danach API: `INTERNAL_PROXY_SHARED_SECRET=<altes>`,
`INTERNAL_PROXY_SHARED_SECRET_PREVIOUS=<neues>` (Rollen tauschen), neu starten – beide bleiben gültig, bis geklärt ist.
Nach Schritt 3 gibt es kein Rückrollfenster: dann Rotation mit einem frischen Secret wiederholen
(Schritt 1–3), `PROXY_SECRET_ENFORCED=false` als Notausgang.

## Akzeptanzchecks (ohne Prod zu verändern)

- `grep -c "<Secret-Fragment>"` über Logs ist verboten (würde das Secret in die Shell-History bringen);
  stattdessen: API-Logs nach `proxy auth rejected` / `forwarded client ip not accepted` filtern. Das
  Secret selbst wird nirgends geloggt (Test `test_secret_never_appears_in_logs_or_responses`).
- Reihenfolge-Verstoß erkennen: sendet das Web ein Secret, das die API (noch) nicht kennt, erscheint
  nur ein `proxy auth rejected`-Warn-Log und die Peer-IP gilt (kein Ausfall, solange `enforced=false`);
  mit `enforced=true` wäre es ein `403`. Deshalb API immer zuerst.
