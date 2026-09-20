# PWA-08 — Hardening-Nachweis

Stand 2026-09-20. Sammelt die Sicherheits-/Härtungsentscheidungen der PWA-08-Roadmap
mit Begründung und sagt ausdrücklich, was offen bleibt.

## 1 — Dependency-Alert (triagiert)

GitHub meldete einen moderaten Dependabot-Alert auf dem Default-Branch: `uuid`
(GHSA-w5hq-g745-h8pq). Triage in #128: die Bibliothek ist im Produktionspfad nicht
erreichbar — die betroffene API ist im Code nicht verwendet, und der `dependency-security`
CI-Job (`pnpm audit --prod --audit-level=high` + `pip-audit`) bricht bei einer
fixbaren kritischen/hohen Produktionsschwachstelle ab. Ergebnis: keine Maßnahme nötig,
kein offener Blocker.

## 2 — Security-Header und CSP

| Header | Zustand | Wo |
|---|---|---|
| `Content-Security-Policy` | Nonce je Antwort + `strict-dynamic`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`, `connect-src 'self'`, `worker-src 'self'` | `apps/web/src/middleware.ts` |
| `Strict-Transport-Security` | `max-age=31536000` auf beiden Live-Oberflächen (Middleware + `next.config.mjs` für die vom Matcher ausgenommenen Pfade) | #127 |
| `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` | gesetzt und durch Tests fixiert | #127, `apps/api/tests/integration/test_security_headers.py` |

**Warum `style-src 'self' 'unsafe-inline'` bleibt:** Next.js schreibt für jedes
gerenderte Dokument Inline-Styles (u. a. `style={{…}}` in Shell/Progress-Komponenten).
Hashes wären pro Render instabil, Nonces gelten für `style-src` erst mit
`style-src-elem`-Unterstützung durch den Renderer. `'unsafe-inline'` für Styles ist die
verbleibende, bewusst dokumentierte Ausnahme; Skripte sind davon nicht betroffen
(Nonce + `strict-dynamic`).

## 3 — SAST

`bandit` **gepinnt** (`1.8.6`) über `apps/api/src` und `packages`, Schwelle `-ll`
(MEDIUM+). Messung vor der Einführung:

```text
447 Findings, alle SEVERITY.LOW, 0 MEDIUM, 0 HIGH
loc: 24574
```

Das Gate ist damit heute grün **und** aussagekräftig: es schlägt bei einem neuen
medium/high-Fund fehl, statt eine lange Low-Liste zu verwalten. Bewusst kein
`--baseline`-File — eine Baseline friert den Ist-Stand ein und macht neue Funde in
alten Dateien unsichtbar.

Der Lauf ist Teil von `scripts/verify.py` (`sast (bandit, medium+)`), also der
Verifikationsrezeptur des Repos.

**Offen und blockiert:** derselbe Befehl als eigener CI-Job
(`sast` in `.github/workflows/ci.yml`) ist vorbereitet, aber nicht ausrollbar — das
OAuth-Token dieses Hosts hat die Scopes `gist, read:org, repo`, und GitHub lehnt jeden
Push auf `.github/workflows/**` ohne `workflow`-Scope ab
(`refusing to allow an OAuth App to create or update workflow ...`). Der Job selbst ist
in #140 hinterlegt; die Freigabe ist ein einmaliger, interaktiver Schritt des Betreibers
(`gh auth refresh -h github.com -s workflow`). Bis dahin läuft die Prüfung lokal über
`scripts/verify.py`.

## 4 — Frontend-Coverage

Methode: `npx vitest run --coverage --coverage.include='src/**/*.{ts,tsx}'` im
`apps/web`-Workspace. Gemessen wird `src/**` über die Vitest-Suiten; die
Playwright-Suiten (`e2e/`, `e2e-system/`) zählen nicht dazu — sie laufen als eigene
Jobs.

**Erst war die Messung kaputt, nicht der Code.** `@vitest/coverage-v8` stand auf
`4.1.11`, während `vitest` auf `5.0.0` lief; der Provider brach mit
`TypeError: Expected string coverage payload, received object` ab und meldete für jede
Datei 0 %. Mit der passenden Major-Version (`5.0.0`) liefert derselbe Lauf echte Zahlen.
Ohne das wäre jede „Coverage"-Aussage in diesem Dokument geraten gewesen.

Messung nach der Korrektur:

```text
Statements 53.97% (2055/3807) · Branches 47.73% (1263/2646)
Functions  48.29% (594/1230)  · Lines    56.33% (1810/3213)
```

Ein Teil der 0-%-Dateien sind Seiten-Komponenten (`app/**/page.tsx`), die bewusst über
die Playwright-Suiten geprüft werden, nicht über Vitest. Der Zweck der Messung ist
deshalb **nicht** die Prozentzahl, sondern die Frage, welche risikoreichen Zweige
ungetestet sind. Nachgeführt:

* Auth-/Session-Zweige der Sicherheitskarte (`security-card.test.tsx`): falsches
  aktuelles Passwort, Mismatch ohne API-Aufruf, Erfolg, Sitzungsliste, Retry nach
  Ladefehler — vorher 0 % auf dieser Datei.
* Fehlerzustände der Oberflächen: `ErrorState`/`LoadingState` waren hartcodiert
  englisch (#145) und sind jetzt katalogisiert; damit greifen die bestehenden
  Zustandstests auch die Übersetzung ab.

## 5 — Bewusst offen

* **Style-`unsafe-inline`** (siehe §2) — akzeptierte Ausnahme, nicht behoben.
* **Keine DAST-/Fuzzing-Stufe.** Der Umfang der Roadmap verlangt SAST; dynamische
  Angriffe auf die Live-Oberflächen sind nicht Teil dieses Nachweises.

## 6 — Promise-Lint-Gate (nachtraeglich geschlossen, #136)

`@typescript-eslint/no-floating-promises` und `no-misused-promises` sind jetzt als
**Fehler** aktiv (typbewusstes Linting ueber `parserOptions.project`). Damit ist die
manuelle Zusicherung aus §5 ersetzt:

* `apps/web/.eslintrc.json`: beide Regeln fuer `**/*.ts`/`**/*.tsx`;
  `checksVoidReturn.attributes` ist aus, weil `onClick={async () => ...}` in React
  bewusst so geschrieben wird und kein vergessenes `await` ist.
* `apps/web/tsconfig.e2e.json` (neu): die gemockten Playwright-Specs unter `e2e/` waren
  aus `tsconfig.json` **ausgeschlossen** und damit fuer typbewusstes Linting und fuer
  `tsc --noEmit` unsichtbar — genau dort ist eine nicht abgewartete Zusicherung
  (`expect(locator).toBeVisible()`) der teuerste stille Fehlschlag. Sie sind jetzt
  typgeprueft.
* Wirksamkeitsnachweis, nicht nur "lint ist gruen": eine Wegwerfdatei mit einem
  vergessenen `await` wurde von der Regel gefangen, dieselbe Zeile mit `void` nicht.

