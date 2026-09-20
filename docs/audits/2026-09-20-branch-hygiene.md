# Branch-Hygiene numra-v1 — Audit, Guard-Kriterien und Restore-Manifest

- **Stand:** 2026-09-20T17:57:37Z (UTC), Remote-Read über `gh` gegen `GoLukeEnviro/numra-v1`
- **Basis:** `main` = `2a8899dd561bb935bcbd508847cd835c046450d7` (HEAD dieses Branches: `2a8899dd561bb935bcbd508847cd835c046450d7`)
- **Ausgangslage:** 36 Remote-Branches ohne `main` (37 inkl. `main`), 9 offene PRs
- **Auftrag:** Operator-GO vom 2026-09-20 — Branch-Hygiene nach Abschluss der Closure-Kette; Mengenangaben aus früheren Audits sind wegen paralleler Merges ungültig und wurden neu berechnet.

## Warum dieses Dokument existiert

Vor der ersten Löschung liegt hier ein dauerhaftes Restore-Manifest: Branch-Name, SHA, PR-Zustand, Entscheidung und Begründung. `/tmp` wäre für einen Restore-Beweis zu flüchtig, deshalb wird das Manifest committet und gepusht, **bevor** der erste Remote-Branch verschwindet. Nach dem Cleanup wird dasselbe Dokument um das Ergebnis ergänzt.

## Korrektur der vorangegangenen Audits

| Aussage im Audit-Text | Geprüfter Stand |
|---|---|
| „39 Branches, 17 an geschlossenen nicht gemergten PRs, 10 ohne PR-Bezug“ | Zum Zeitpunkt jenes Audits (main `e771dfa`): 39 inkl. `main`, davon **1** PR geschlossen-nicht-gemergt und **4** ohne PR. Die übrigen „closed-but-unmerged" waren **squash-gemergt**: ihre Commit-Patches fehlen in der Historie, ihr Inhalt ist über den Merge-Commit nachweislich in `main`. |
| „fast alle offenen PR-Branches 3 Commits hinter `main`“ | real 0 / 5 / 7 / 60 Commits hinter `main` je Branch |
| „37 Branches, 10 offene PRs“ | bestätigt zum Start dieses Laufs (36 ohne `main`), nach dem `#156`-Merge: 36 Branches, 9 offene PRs (alle Dependabot) |

## Guard-Kriterien (je Branch einzeln, unmittelbar vor der Löschung)

Ein Branch wird nur gelöscht, wenn **alle** Punkte gleichzeitig erfüllt sind:

1. nicht `main`,
2. kein Head eines offenen PRs,
3. PR gemergt **oder** Patch nachweislich vollständig in `main`,
4. kein aktives Worktree,
5. keine uncommitteten Änderungen im Checkout,
6. SHA im Restore-Manifest,
7. frischer Remote-Read stimmt mit dem Manifest-SHA überein.

Löschkommando: `gh api -X DELETE repos/GoLukeEnviro/numra-v1/git/refs/heads/<branch>` — kein Force-Push, kein Rebase, kein `git branch -D` gegen den Remote-Bestand.

**Nachweis „Inhalt in main“:** `git merge-base --is-ancestor <ref> origin/main` (Ancestor) **oder** Patch-ID-Gleichheit des Branch-Diffs (gegen die Merge-Base) mit dem Patch des Squash-/Merge-Commits des gemergten PRs (`git diff <mb> <ref> | git patch-id --stable` vs. `git diff <mc>^ <mc> | git patch-id --stable`).

## Restore-Manifest (36 Remote-Branches ohne `main`)

| Branch | SHA | PR | Entscheidung | Nachweis / Begründung |
|---|---|---|---|---|
| `codex/ollama-top-p` | `b04caa62ee268d5d45b577ff3a4a803deb37b5c9` | #74:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 6c512ecd (PR#74) |
| `codex/pr-web-06a` | `00c445b21cc0773f744555c78fd9ddc9437e3683` | #53:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 16d7e1a9 (PR#53) |
| `codex/pr-web-06a-evidence` | `af046998dca991e53b28001a3cf26ffdf332bfac` | #54:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 60391068 (PR#54) |
| `codex/pr-web-06b` | `98986b782fd93195dd443b0b8433232975314938` | #55:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 7e8a1924 (PR#55) |
| `codex/pr-web-06b-docs` | `ef1025ff4968250a8b63c0200ea2f57274d3b2fa` | #56:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 4a72bc20 (PR#56) |
| `codex/pr-web-07` | `ea2ffad676b7d6b9dd3a2ad4d8c2e8c39ac1be6a` | #57:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 935508c6 (PR#57) |
| `codex/pr-web-07-evidence` | `11460ab2d9a072318707ef3a296ba24677e54000` | #58:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit 6344539f (PR#58) |
| `copilot/branches-overview` | `e771dfa5ae5caa26003da29b433356c7d0c3781e` | NO-PR | löschen (vollständig in `main`) | ancestor-of-main |
| `copilot/fix-github-actions-job` | `498c2a0a96c02be269bbd655ac587a2c0e2fff93` | NO-PR | löschen (vollständig in `main`) | ancestor-of-main |
| `copilot/pr-3-merge-and-close-pr-2` | `574a74ff92f69e54cf371af81bfe3de53c936b18` | NO-PR | löschen (vollständig in `main`) | ancestor-of-main |
| `docs/product-closure-roadmap` | `c115d475bd1fa149736e9fea15b2c10d6c7da056` | #99:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `docs/pwa-02-closure` | `be0f0914bfddee9c6db973acaa81ad0b9f41d9fc` | #100:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `docs/pwa-03-code-parity-resolved` | `f15a3068831ddb1a6d62a980d0552afa13f9efc8` | #102:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `docs/pwa-03-production-parity` | `b03a6ec2f430d7e548c386ff50b882e42f1de72d` | #101:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `docs/pwa04-session-handoff` | `ef8818217f3f3f4fcfc6b4c76cf82954dd42f797` | #103:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `docs/release-a-verification-runbook` | `2c750eb6cced9244241d77c0fca4317287faef24` | #10:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `feat/mobile12c-today-daily-brief` | `de4c3d6b5b1f87a0ad15f790ef7ace1586f806ce` | #84:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `feat/numra-v1-5-product-completion` | `5dff301fd1a48462eb2bb33f2610194b5788969c` | #8:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `feat/pr-web-02-personal-workspace` | `35a82dbbb6803a00947f805fab3aef088bbcab20` | #40:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit abeaa82b (PR#40) |
| `feat/pr-web-03-connections-invitations-consent` | `38ab2b5aa38a61078cf077d48221a9b611ac5307` | #41:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit ee205ba1 (PR#41) |
| `feat/pr-web-04-relationship-workspace-core` | `36f40e03d3947f919f33c3da6a7a8e8b1affea7c` | #42:MERGED | löschen (vollständig in `main`) | patch-identical to merge-commit f947976b (PR#42) |
| `fix/copilot-mock-safe-response` | `9a63e9bcceaabb69645bf95a508d599314a8aa15` | #98:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `fix/numra-v1-production-completion` | `109e18f79718a7aa6a5c651543455f7ccfdca880` | #3:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `fix/v1.6-c-timing-report-grounding` | `427fb08c84dba3775cc8193a2f40f64c748a0b26` | #11:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `test/report-output-marker-proofs` | `5ab30715a4d8f91daf3916ab0a64424eaa9a57b4` | #156:MERGED | löschen (vollständig in `main`) | ancestor-of-main |
| `dependabot/npm_and_yarn/eslint-10.10.0` | `38be133dc53ad485f8ed7efa36f0576f346f787e` | #96:OPEN | behalten bis PR-Entscheid | PR#96 open |
| `dependabot/npm_and_yarn/express-5.2.1` | `a240cbcf177c7bb5f38331461e1e6f835840fa10` | #95:OPEN | behalten bis PR-Entscheid | PR#95 open |
| `dependabot/npm_and_yarn/multi-de36fa8f59` | `2349dc0cb11e6cd5285d341aaad1ada0b12df234` | #97:OPEN | behalten bis PR-Entscheid | PR#97 open |
| `dependabot/npm_and_yarn/safe-minor-and-patch-6e65b2d03c` | `7f54aeaa291da05498bfc882577d00f2800d4a64` | #153:OPEN | behalten bis PR-Entscheid | PR#153 open |
| `dependabot/npm_and_yarn/tailwindcss-4.3.3` | `34414fd58d5009e05a13a4839baa9f51b293ece6` | #94:OPEN | behalten bis PR-Entscheid | PR#94 open |
| `dependabot/pip/httpx-gte-0.28.1` | `60c27a9ea6f298c4c53008657201fc92e2bae23d` | #90:OPEN | behalten bis PR-Entscheid | PR#90 open |
| `dependabot/pip/hypothesis-gte-6.168.0` | `9b8b81d03cad9cd2cada962ffbcf086a3a088ff0` | #92:OPEN | behalten bis PR-Entscheid | PR#92 open |
| `dependabot/pip/pytest-gte-9.1.1` | `4f30a81ec4f493e8ac1b98458ba1cd58ec2298ca` | #89:OPEN | behalten bis PR-Entscheid | PR#89 open |
| `dependabot/pip/ruff-gte-0.16.7` | `59f2ab3341c8bfa1188ed6c819f0fa87948a2ebb` | #91:OPEN | behalten bis PR-Entscheid | PR#91 open |
| `feat/report-prompt-v3` | `e87b1552755c357b85c635d321e56a0c615fa6f2` | #15:CLOSED | Archiv-Tag setzen, dann löschen | PR#15 closed, 14 commits not in main |
| `copilot/5df610237a5ff0992a7d9fd3074a7bc5f696455b` | `feea3d13451fcc1cf80a841631457e44b4f6ea85` | NO-PR | löschen (durch spätere Implementierung überholt) | no PR, 1 commits not in main |

### Wiederherstellung eines gelöschten Branches

```bash
gh api -X POST repos/GoLukeEnviro/numra-v1/git/refs -f ref=refs/heads/<branch> -f sha=<sha>
```

Der SHA-Check vor jeder Löschung stellt sicher, dass genau dieser Stand wiederherstellbar ist; das Manifest ist die einzige Quelle für die SHA-Werte.

## Sonderfall: `feat/report-prompt-v3` (PR #15)

Der Branch enthält 14 Commits (12 Dateien, +416/−502 gegen die Merge-Base), darunter einen kompletten Prompt-Satz `packages/engine-interpretation/src/numra_interpretation/report/prompts/v3/*.md`, der in `main` **nicht** existiert. PR #15 wurde geschlossen und nie gemergt. Entscheidung des Operators: Inhalt bewusst nicht in `main`, aber als Archiv erhalten.

```bash
git tag -a archive/pr-15-report-prompt-v3 <sha> -m 'PR #15 closed, never merged; archived before branch deletion'
git push origin archive/pr-15-report-prompt-v3
```

Der Tag zeigt exakt auf den letzten Branch-SHA; danach wird der Remote-Branch gelöscht. Wiederherstellung später: `git branch <name> archive/pr-15-report-prompt-v3` bzw. `git push origin archive/pr-15-report-prompt-v3:refs/heads/<name>`.

## Dependabot-Entscheidungen

**Majors — eigenes Upgrade-Issue, Dependabot-PR mit Verweis schließen (kein Merge wegen grüner CI):**

| PR | Paket | von → auf | offene Checks |
|---|---|---|---|
| #94 | tailwindcss | 3.4.19 → 4.3.3 | web-lint/build, docker-build, docker-compose-e2e |
| #95 | express (pdf service) | 4.22.2 → 5.2.1 | derzeit grün (BEHIND) — trotzdem Major-Migration |
| #96 | eslint | 8.57.1/9.x → 10.10.0 | web-lint/build |
| #97 | react-dom + @types/react-dom | 18.3.1 → 19.3.0 | web-lint/build, docker-build, docker-compose-e2e |
| #89 | pytest | >=8.0 → >=9.1.1 | BEHIND |

**Sichere Minor/Patch-Updates — Branch-Update, Diff-Review, vollständige CI, dann einzeln oder als kontrollierter Batch:**

| PR | Paket | von → auf | Bemerkung |
|---|---|---|---|
| #91 | ruff | >=0.16.6 → >=0.16.7 | Patch |
| #92 | hypothesis | >=6.100 → >=6.168.0 | Minor |
| #90 | httpx | >=0.27 → >=0.28.1 | aktuell **DIRTY** (Konflikt) — Release Notes + API-Nutzung prüfen |
| #153 | Gruppe „safe-minor-and-patch“ (8 Updates, u. a. lucide-react 1.45→1.47) | — | jedes enthaltene Update einzeln prüfen, nicht blind bündeln |

## Repository-Einstellung

`delete_branch_on_merge` steht auf `false`; wird im Rahmen dieses Auftrags auf `true` gesetzt (einzige freigegebene Einstellungsänderung). Verifikation nach dem nächsten Merge: genau der Head-Branch dieses PRs verschwindet, die Einstellung wird frisch zurückgelesen.

## Lokale Branches im Checkout (nicht Remote)

| Branch | Zustand | Entscheidung |
|---|---|---|
| `fix/mock-prompt-leak-all-pipelines` | Inhalt in `main` (ancestor) | lokal entfernen |
| `fix/error-code-classification` | Duplikat des PR-#152-Inhalts (Branch `84c1d2e`), lokal veraltet | lokal entfernen |
| `fix/user-visible-error-codes` | Head von PR #154 (gemergt) | lokal entfernen |
| `main` | lokaler Stand hinter `origin/main` | nur Fast-Forward auf `origin/main` |

Lokale Löschung erst nach Worktree- und Dirty-Check; Remote-Branches sind davon nicht betroffen.

## Ergebnis des Laufs

**Reihenfolge wie freigegeben:** erst die Closure-Kette abschließen, dann Hygiene. Die Closure-Kette endete mit dem Merge von PR #156 (`test/report-output-marker-proofs`, Merge-Commit `2a8899d`), der mit vollständiger CI (16 Checks) und grünem Post-Merge-Lauf auf `main` landete.

### Gelöschte Remote-Branches

**25 Branches** wurden einzeln durch den Pre-Delete-Guard gelassen und gelöscht (frischer Remote-Read == Manifest-SHA, kein offener PR-Head, kein fremdes Worktree, sauberer Checkout, Nachweis in `main`):

- `ancestor-of-main` (vollständig in der Historie): 15 Branches — `copilot/branches-overview`, `copilot/fix-github-actions-job`, `copilot/pr-3-merge-and-close-pr-2`, `docs/product-closure-roadmap`, `docs/pwa-02-closure`, `docs/pwa-03-code-parity-resolved`, `docs/pwa-03-production-parity`, `docs/pwa04-session-handoff`, `docs/release-a-verification-runbook`, `feat/mobile12c-today-daily-brief`, `feat/numra-v1-5-product-completion`, `fix/copilot-mock-safe-response`, `fix/numra-v1-production-completion`, `fix/v1.6-c-timing-report-grounding`, `test/report-output-marker-proofs`
- `patch-identical zum Merge-Commit des gemergten PRs` (Squash-Merges): 10 Branches — `codex/ollama-top-p`, `codex/pr-web-06a`, `codex/pr-web-06a-evidence`, `codex/pr-web-06b`, `codex/pr-web-06b-docs`, `codex/pr-web-07`, `codex/pr-web-07-evidence`, `feat/pr-web-02-personal-workspace`, `feat/pr-web-03-connections-invitations-consent`, `feat/pr-web-04-relationship-workspace-core`

**Sonderfälle:**

- `feat/report-prompt-v3` (PR #15, nie gemergt): annotierter Archiv-Tag `archive/pr-15-report-prompt-v3` (Tag-Objekt `720ed2fe4c266caac6da27d69513c0d1238b2e73`) zeigt auf den verifizierten Head-SHA `e87b1552755c357b85c635d321e56a0c615fa6f2`; der Tag ist auf dem Remote verifiziert, danach wurde der Branch gelöscht.
- `copilot/5df610237a5ff0992a7d9fd3074a7bc5f696455b`: gelöscht (SHA `feea3d13451fcc1cf80a841631457e44b4f6ea85`), kein Archiv-Tag — der Inhalt ist durch die spätere Implementierung überholt.
- Die vier Dependabot-Branches (`dependabot/pip/httpx-gte-0.28.1`, `dependabot/pip/ruff-gte-0.16.7`, `dependabot/pip/hypothesis-gte-6.168.0`, `dependabot/npm_and_yarn/safe-minor-and-patch-6e65b2d03c`) verschwanden mit dem Schließen ihrer PRs: GitHub entfernt den Head-Branch einer geschlossenen Dependabot-PR — verifiziert durch die leere Branch-Abfrage danach. Der `safe-minor-and-patch`-Branch enthielt zusätzlich die bewusst nicht übernommenen Updates (vitest 5.0.1 → #164, apps/mobile → #165); ihre Versionen stehen dort, deshalb ist der Branch ohne Informationsverlust entbehrlich.

### Merges

| PR | Inhalt | Merge-Commit | Post-Merge-CI |
|---|---|---|---|
| #156 | Prompt-Material-Nachweis für Report → DOM/PDF/Export (Closure-Kette) | `2a8899d` | grün, 20 Checks |
| #158 | Sicherer Dependency-Batch (httpx, ruff, hypothesis, lucide-react, tailwind-merge, autoprefixer) | `fa869f6` | siehe Abschnitt `Post-Merge-Verifikation` |

Der Batch war nötig, weil die Branch-Protection `strict: true` erzwingt: vier Einzelmerges hätten vier serielle CI-Zyklen gekostet, ein kontrollierter Batch einen.

### Ausgeschlossen und mit eigenem Issue versehen

| Thema | Issue | Begründung |
|---|---|---|
| Tailwind 3 → 4 | #159 | Major-Migration, im Dependabot-PR drei rote Jobs |
| Express 4 → 5 (PDF-Service) | #160 | Major-Migration, PR nur `BEHIND` — grüne Checks bedeuteten nichts |
| ESLint 8/9 → 10 | #161 | Major, `web-lint-typecheck-build-test` rot |
| React 18 → 19 | #162 | Major, drei rote Jobs |
| pytest-Konstraint | #163 | `uv.lock` installiert bereits 9.1.1; es geht nur um die Deklaration |
| vitest 5.0.1 | #164 | bricht die jest-dom-Typaugmentierung → `tsc --noEmit` rot (lokal reproduziert) |
| apps/mobile | #165 | wird von CI überhaupt nicht gebaut/getestet — grüne CI bewiese dort nichts |

Die zugehörigen Dependabot-PRs (#89, #94, #95, #96, #97) wurden mit Verweis auf ihr Issue geschlossen; #90, #91, #92 und #153 mit Verweis auf den Batch-PR #158.

### Repository-Einstellung

`delete_branch_on_merge` wurde von `false` auf `true` gesetzt und frisch zurückgelesen (`{"delete_branch_on_merge": true}`). Weitere Einstellungen wurden nicht angefasst. Die Verifikation dieser Einstellung ist der Merge dieses Dokumentations-PRs selbst: danach muss genau sein Head-Branch verschwunden sein.

### Lokale Branches

- `fix/mock-prompt-leak-all-pipelines` (Inhalt in `main`) — entfernt.
- `fix/error-code-classification` — entfernt; sein eigener Inhalt war überholt (die neuere Fassung ohne Ausnahmetext im nutzersichtbaren Fehlercode steht in `main`).
- `test/report-output-marker-proofs` (nach dem #156-Merge tot) — entfernt.
- `fix/user-visible-error-codes` war beim Aufräumen bereits nicht mehr vorhanden.
- `main` wurde per Fast-Forward auf `origin/main` gezogen; der Checkout steht auf `main`.

### Restore

Jeder gelöschte Branch ist über seinen SHA in der Tabelle oben wiederherstellbar (Kommando siehe Abschnitt „Wiederherstellung eines gelöschten Branches"); PR #15 zusätzlich über den Archiv-Tag.

### Post-Merge-Verifikation

| `main`-Stand | Herkunft | Ergebnis |
|---|---|---|
| `2a8899d` | Merge PR #156 (Closure-Kette) | 20 Checks, 0 Fehler — grün |
| `fa869f6` | Merge PR #158 (Dependency-Batch) | 16 Checks, 0 Fehler; CI-Lauf `35528510287` 12/12 Jobs grün |

Der Merge dieses Dokumentations-PRs ist zugleich der angekündigte Test für
`delete_branch_on_merge`: danach muss dessen Head-Branch verschwunden und nur `main`
übrig geblieben sein.

