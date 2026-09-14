# AVENYTH Web — Execution State

- **PLAN_VERSION:** 2
- **VERIFIED_IMPLEMENTATION_MAIN_SHA:** f444c4a6be103294ed43e4ce9f15f37ef3434146
- **CURRENT_SEGMENT:** SEGMENT_C
- **CURRENT_PR:** MOBILE-12B Native Authentication in PR #79 abgeschlossen (Kette WEB-09→WEB-11→WEB-10→MOBILE-12A→MOBILE-12B).
- **LAST_MERGED_IMPLEMENTATION_PR:** #79 (MOBILE-12B), Doku-Nachzug #81
- **LAST_GREEN_IMPLEMENTATION_MAIN_SHA:** 55f05cf412e19717159a9f2a4eb191e3f4dcfe88
- **CURRENT_TASK:** WEB-09/WEB-11/WEB-10/MOBILE-12A/MOBILE-12B abgeschlossen und unabhängig sicherheitsgeprüft.
- **NEXT_ACTION:** MOBILE-12C (read-only mobile Today-/Daily-Brief, Bearer-Grenze gezielt auf einen read-only Produktvertrag erweitern) planen und umsetzen.
- **HUMAN_GATE_REQUIRED:** false
- **OPEN_BLOCKERS:** PR #74 (Ollama-Sampling) hinter main, 13 offene Dependabot-PRs — beides außerhalb dieses Feature-Stacks, separat zu priorisieren.
- **LAST_UPDATED_AT:** 2026-09-14

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
WEB-07 ist abgeschlossen. Der nächste Abschnitt ist PR-V2-08 Roadmaps + Shared Reflection.
