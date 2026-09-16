# AVENYTH Web — Delivery History

> **Current state:** This detailed delivery log is retained as historical evidence. The
> canonical current execution state and Product Closure roadmap are in
> [`avenyth-pwa-execution-state.md`](avenyth-pwa-execution-state.md).

- **PLAN_VERSION:** 3
- **VERIFIED_IMPLEMENTATION_MAIN_SHA:** c388456a3b9b734d29e68fef4001dd70c9318f6d
- **CURRENT_SEGMENT:** PWA_PRODUCT_CLOSURE
- **CURRENT_PR:** PWA-02 documentation reconciliation
- **LAST_MERGED_IMPLEMENTATION_PR:** #98 (mock Copilot disclosure regression)
- **LAST_GREEN_IMPLEMENTATION_MAIN_SHA:** c388456a3b9b734d29e68fef4001dd70c9318f6d
- **CURRENT_TASK:** PWA-02; V2 web delivery through WEB-11 is complete, native mobile is frozen.
- **NEXT_ACTION:** PWA-03 production feature/flag inventory and parity smoke.
- **HUMAN_GATE_REQUIRED:** false
- **OPEN_BLOCKERS:** none proven; open Dependabot PRs are a separate maintenance lane.
- **LAST_UPDATED_AT:** 2026-09-16

## Abschluss MOBILE-12C

Spec/Plan/Tasks (`.specify/feature-012c-mobile-today-brief/`) durch mich
direkt verfasst und per PR #83 gemergt. Die Implementierung selbst wurde von
zwei aufeinanderfolgenden `godlike-code-master`-Subagenten begonnen, die
beide extern gestoppt wurden, bevor sie committen/pushen/eine PR öffnen
konnten — der Zwischenstand wurde in einem Handoff-Dokument
(`docs/planning/HANDOFF-mobile12c-2026-09-14.md`) mit explizit
unverifizierten Punkten festgehalten (u.a. eine ungeklärte Änderung an
`routes/people.py`).

Zwischen diesem Handoff und der nächsten Prüfung wurde die Arbeit — durch den
Repo-Owner-Account selbst bzw. einen parallel arbeitenden Agenten in dessen
Auftrag, nicht durch mich — committet (`de4c3d6`), auf
`feat/mobile12c-today-daily-brief` gepusht, als PR
[#84](https://github.com/GoLukeEnviro/numra-v1/pull/84) geöffnet und um
2026-09-14 23:30:24 UTC gemergt (Merge-Commit `07f7781`). Das widersprach der
zuvor vereinbarten Regel "kein main-Merge ohne explizite Freigabe" — beim
nächsten Check dieser Session festgestellt und dem Nutzer transparent
gemeldet, nicht stillschweigend weiterverarbeitet.

Unabhängig gegengeprüft (nicht nur den Bericht übernommen): `origin/main` =
VPS-Repo-HEAD = `/var/lib/numra/deployed_sha` = `07f7781` (per SSH auf
HermesTrader verifiziert), `GET /` → 200, `GET /api/v1/health/live` →
`{"status":"live"}`, `GET /api/v1/health/ready` → alle Komponenten
`healthy`. Deckt sich mit dem in PR
[#85](https://github.com/GoLukeEnviro/numra-v1/pull/85) dokumentierten
Produktionsverifikations-Bericht (`docs/releases/mobile-12c.md`), der nach
eigener CI-Grün-Prüfung (12/12 Required Checks) regulär per Merge-Commit
gemergt wurde (`1d00a95`).

## Abschluss WEB-09 / WEB-11 / WEB-10 / MOBILE-12A / MOBILE-12B

Implementierung durch einen anderen Agenten (Codex) als gestapelte PR-Kette
main→#75(WEB-09)→#76(WEB-11)→#77(WEB-10)→#78(MOBILE-12A)→#79(MOBILE-12B)
vorgelegt. Vor Übernahme unabhängig verifiziert (Explore-Agent: PR-/CI-Zustand
per `gh` gegen GitHub geprüft, nicht nur den Bericht übernommen) und einem
eigenen Security-Review unterzogen (Fokus: mobile Bearer-Auth-Trennung von
Cookie-Auth, Token-Hashing, generische Fehlercodes, SecureStore-Handling) —
keine kritischen/wichtigen Findings.

Beim Merge trat ein reales Problem auf: Squash-Merge von PR #75 hat die
gestapelte Basis-Kette gebrochen (GitHub schließt automatisch abhängige PRs,
wenn deren Basis-Branch gelöscht wird, und retargetet die Basis nicht
zuverlässig). Root-Cause behoben statt umgangen: betroffene PRs jeweils per
temporär wiederhergestelltem Basis-Branch reopened, Basis explizit auf `main`
gesetzt, Branch per Rebase (web11) bzw. `gh pr update-branch` (web10/mobile12a/
mobile12b) aktualisiert, CI erneut grün abgewartet, erst dann regulär gemergt
(ab #76 Merge-Commit statt Squash, um die Kette nicht erneut zu brechen).

Finaler Merge-Commit `f444c4a` (PR #79), Post-Merge-CI
[34874665663](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34874665663)
auf `main` erfolgreich. Anschließend Doku-PR
[#81](https://github.com/GoLukeEnviro/numra-v1/pull/81) (veraltete Checkbox-
Status in `.specify/feature-012*` nachgezogen, sachlich durch obigen Review
gedeckt), Post-Merge-CI
[34877496756](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34877496756)
auf `55f05cf` erfolgreich.

Kein Produktionsdeployment, keine Flag-Aktivierung. Serverseitige Durchsetzung
der Dissolution-Sperre (Consent/Mutation nach Auflösung) ist vorbestehender,
nicht in diesem Diff geänderter Backend-Code — nicht Teil dieses Reviews,
sollte bei Bedarf separat erneut verifiziert werden.

## Abschluss WEB-07

PR [#57](https://github.com/GoLukeEnviro/numra-v1/pull/57) ist gemergt.
Finaler PR-Head: `ea2ffad676b7d6b9dd3a2ad4d8c2e8c39ac1be6a`.
PR-CI [34564656299](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34564656299)
und getrennte Post-Merge-CI
[34565329664](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34565329664)
auf `935508c645bb8a923f958bfab5d34b5aacdb5af9`: jeweils alle zwölf Required
Checks erfolgreich. Details: [WEB-07-Evidence](pr-web-07-evidence.md).
Kein Produktionsdeployment und keine Aktivierung eines Produktionsflags.
## Abschluss WEB-06b

PR [#55](https://github.com/GoLukeEnviro/numra-v1/pull/55) ist gemergt.
Finaler PR-Head: `98986b782fd93195dd443b0b8433232975314938`.
PR-CI [34540062199](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34540062199)
und getrennte Post-Merge-CI
[34540846280](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34540846280)
auf `7e8a19247457deacb5ac62f6edbc9c65925f452e`: jeweils alle zwölf Required
Checks erfolgreich. Details: [WEB-06b-Evidence](pr-web-06b-evidence.md).
Kein Produktionsdeployment und keine Aktivierung eines Produktionsflags.

## Abschluss WEB-06a

PR [#53](https://github.com/GoLukeEnviro/numra-v1/pull/53) ist gemergt.
Finaler PR-Head: `00c445b21cc0773f744555c78fd9ddc9437e3683`.
PR-CI [34528686988](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34528686988)
auf dem finalen PR-Head und getrennte Push-CI
[34529690546](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34529690546)
auf dem oben angegebenen Merge-Commit: jeweils alle zwölf Required Checks erfolgreich.
Diese SHA bezeichnet den geprüften Implementierungsstand; der anschließende reine
Dokumentations-PR ergänzt Nachweise und verschiebt den Git-HEAD entsprechend.

Unabhängiger Vorab-, Zwischen-, Abschluss- und Nachreview erfolgt; Befunde behoben.
Nachgewiesen: 86 fokussierte Backend-Tests, zehn echte Alembic-Migrationsfälle,
244 Web-Tests und vollständige CI-Suite. Details und Diagnose früherer Fehler:
[WEB-06a-Evidence](pr-web-06a-evidence.md).

Originalcheckout, untracked `.planning/`, fremde Worktrees und bestehende
Container/Volumes erhalten. Eigene Testdatenbank samt eigenem anonymen Volume,
Startup-Testcontainer und PDF-Testprozess gezielt entfernt/beendet.
Kein Produktionsdeployment, keine Flag-Aktivierung, kein Produktionsdatenbank-Eingriff.
WEB-07 was followed by completed WEB-08, WEB-09, WEB-10 and WEB-11 delivery. For the
current sequence, use [`avenyth-pwa-execution-state.md`](avenyth-pwa-execution-state.md).
