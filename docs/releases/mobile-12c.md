# MOBILE-12C — Produktionsabschluss

## Release

- Pull Request: [#84](https://github.com/GoLukeEnviro/numra-v1/pull/84)
- Titel: `MOBILE-12C: Native Today/Daily-Brief (read-only)`
- Merge-Zeit: 2026-09-14 23:30:24 UTC
- Merge-Commit: `07f77819c35e95360c78d242c768b97300caa11a`
- Deployment: automatischer `numra-update.timer`; nach dem Lauf um 23:43 UTC
  verifiziert.

## Produktionsverifikation

Die maßgeblichen Release-Revisionen waren identisch:

```
origin/main = /opt/numra/repo HEAD = /var/lib/numra/deployed_sha
            = 07f77819c35e95360c78d242c768b97300caa11a
```

Das explizit abgefragte Compose-Projekt `numra-prod` war betriebsbereit: API,
PDF, PostgreSQL, Redis und Web meldeten `running` und `healthy`; der Worker
lief ebenfalls. Die externen, Tailnet-internen Smoke-Checks waren erfolgreich:

- `GET /` → `200`
- `GET /api/v1/health/live` → `{"status":"live"}`
- `GET /api/v1/health/ready` → `healthy` für Datenbank, Numerologie-Engine,
  LLM und PDF.

## Ollama Cloud / DeepSeek

Am 2026-09-14 nach dem Deployment direkt im laufenden API-Container geprüft:

- `NUMRA_LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL` gesetzt auf die Ollama-Cloud-API
- `OLLAMA_API_KEY` vorhanden (Wert nicht ausgegeben)
- Premium-Modell: `deepseek-v4-pro:0813`
- Fast-Modell: `deepseek-v4-flash:0731`
- Der Provider-Readiness-Check war `healthy`.
- Ein minimaler, nicht-personenbezogener Chat-Test gegen das konfigurierte
  Premium-Modell lieferte HTTP `200` und nichtleeren Inhalt.

Ollama dokumentiert aktuell `deepseek-v4-pro:cloud` als regulären Cloud-Tag;
die laufende, absichtlich gepinnte Revision `deepseek-v4-pro:0813` wurde nicht
ohne gesonderte Freigabe verändert.
