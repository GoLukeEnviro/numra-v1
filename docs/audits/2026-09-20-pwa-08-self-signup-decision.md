# PWA-08 — `ALLOW_SELF_SIGNUP`: Entscheidung, Sollzustand je Umgebung, Verifikation

Stand 2026-09-20. Dieses Dokument schließt die Produktentscheidung aus Issue #115 ab:
offene Selbstregistrierung in Produktion — ja oder nein — und hält fest, was danach
tatsächlich läuft.

## Befund vor der Entscheidung

```
GET https://agent0-1.taile6801f.ts.net:8443/api/v1/public/config   (numra-prod)
→ {"self_signup_enabled":true, ...}
```

Der Wert war **kein Migrationsregress**: derselbe Wert stand im HermesTrader-
Übergabebundle und wurde identisch übernommen. Er widersprach aber dem dokumentierten
Default (`.env.example`: `ALLOW_SELF_SIGNUP=false`) und der Annahme „Selbstregistrierung
ist eine Non-Prod-Eigenschaft" aus mehreren Handoff-/Overlay-Kommentaren.

Der historisch dokumentierte Grund für `true` ist der V1.6-B-Rollout
(`docs/releases/v1.6-b.md` §Production rollout, Schritt 5): die Freigabe wurde damals
**nach** der vollständigen Produktionsverifikation als eigener Schritt gesetzt und über
`/v1/public/config` bestätigt. Diese Freigabe gehörte zu jenem Release; für den
aktuellen Stand (PWA Product Closure, Produktion noch nicht auf dem Closure-SHA) gilt
wieder die Regel desselben Dokuments: Registrierung bleibt zu, bis der Release in
Produktion verifiziert ist.

## Entscheidung (Issue #115)

| Umgebung | `ALLOW_SELF_SIGNUP` | Begründung |
|---|---|---|
| `numra-prod` (agent0, `:8443`) | **`false`** | Ungesteuerte Kontoanlage über einen öffentlich erreichbaren Endpunkt; das Rate Limit (5/h/IP) ist Abuse-Schutz, keine Zugangskontrolle. Einladungs-/Beta-Zugang bleibt die Produktentscheidung, offene Registrierung die Ausnahme. |
| `numra-audit` (agent0, `:8444`) | `true` | Die Abnahme-Suite registriert ihre synthetischen Konten selbst (`scripts/rc2-e2e.sh`, RC2-Journey). |
| RC2 lokal / CI | `true` | Wegwerf-Stack, vom Runner erzeugt und entfernt. |

Diese Entscheidung ist konsistent mit `.env.example` (`false`) und mit
`Settings.allow_self_signup = False` als Code-Default.

## Durchführung und Verifikation (Produktion)

```bash
# Backup + Wert setzen (keine Secrets in der Ausgabe)
sudo cp /etc/numra/numra.env /etc/numra/numra.env.bak-pre-signup-<UTC>
sudo sed -i 's/^ALLOW_SELF_SIGNUP=.*/ALLOW_SELF_SIGNUP=false/' /etc/numra/numra.env

# Nur den api-Container neu erzeugen (kein Image-Neubau, keine Migration)
docker compose -p numra-prod --env-file /etc/numra/numra.env \
  -f /opt/numra/compose.production.yml up -d api
```

Ergebnis (frisch gelesen, nicht aus dem Log):

| Prüfung | Ergebnis |
|---|---|
| `GET :17800/v1/health/ready` | `{"status":"healthy","database":"healthy","numerology_engine":"healthy","llm":"healthy","pdf":"healthy"}` |
| `GET :17800/v1/public/config` | `{"self_signup_enabled":false,"app_name":"AVENYTH","supported_ui_locales":["de","en"]}` |
| `POST :17800/v1/auth/register` (synthetische Adresse) | `403 {"code":"SELF_SIGNUP_DISABLED"}` — es wurde **kein** Konto angelegt |
| Audit-Stack `:17801/v1/public/config` | unverändert `self_signup_enabled:true` (Abnahme braucht Registrierung) |

Rollback ist ein Einzelbefehl in beide Richtungen (Wert zurücksetzen, `up -d api`);
kein Datenverlust, keine Migration, kein Image-Neubau.

## Was bewusst nicht geändert wurde

* **Kein `Settings`-Validator-Backstop.** Ein Validator analog zu
  `_forbid_mock_llm_provider_in_production` würde die *gewollte* Öffnung (V1.6-B-Rollout
  in einer verifizierten Release-Phase) verhindern. Die Eigenschaft bleibt eine
  Deployment-Entscheidung — jetzt aber eine dokumentierte. Die Frage ist als
  Folgefrage in #115 beschrieben und nicht stillschweigend umgangen.
* **Keine Änderung am Registrierungspfad, an der UI-Sichtbarkeit oder am Rate Limit.**
  Die Oberfläche liest `self_signup_enabled` aus der öffentlichen Config; mit `false`
  bleibt der Registrierungsweg geschlossen, ohne dass Produktcode angefasst wurde
  (verifiziert über die Config-API; die UI-Sichtbarkeit folgt genau diesem Wert).
