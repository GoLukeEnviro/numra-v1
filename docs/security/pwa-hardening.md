# PWA-08 — Hardening-Nachweis

Stand 2026-09-21 (angelegt 2026-09-20). Sammelt die Sicherheits-/Härtungsentscheidungen der PWA-08-Roadmap
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

`bandit` **gepinnt** (`1.8.6`), Umfang `apps/api/src` und `packages`, Schwelle `-ll`
(MEDIUM+). Derselbe Befehl läuft in CI und lokal:

```bash
uv run --with bandit==1.8.6 bandit -q -r apps/api/src packages -ll
```

Gemessen am 2026-09-21 auf `main` (`36de60d`):

```text
449 Findings, alle SEVERITY.LOW (durchgehend B101), 0 MEDIUM, 0 HIGH
loc: 24736
```

Das Gate ist damit heute grün **und** aussagekräftig: es schlägt bei einem neuen
medium/high-Fund fehl, statt eine lange Low-Liste zu verwalten. Bewusst kein
`--baseline`-File und **keine `#nosec`-Unterdrückung**: eine Baseline friert den
Ist-Stand ein und macht neue Funde in alten Dateien unsichtbar, und die 449
LOW-Funde sind nicht unterdrückt, sondern liegen unterhalb der dokumentierten
Schwelle (B101 = `assert`, im Testcode gewollt).

Der Lauf ist an drei Stellen derselbe Befehl: CI-Job `sast`
(`.github/workflows/ci.yml`), `scripts/verify.py` (`sast (bandit, medium+)`) und dieser
Abschnitt — CI und lokale Rezeptur können so nicht auseinanderlaufen. Dass das Gate
wirklich fehlschlagen kann, ist mit einem echten **MEDIUM**-Fund belegt (Fixture →
Job rot, Exit 1 → Fixture entfernt → grün, Exit 0), inklusive Nachweis, dass ein
LOW-only-Fund das Gate **nicht** auslöst: `docs/audits/2026-09-21-pwa-08-sast.md`.

**Offen (Betreiber-Schritt):** der Job ist angelegt, steht aber noch nicht in den
Required Checks der Branch-Protection — Branch-Protection wurde in diesem PR bewusst
nicht angefasst. Solange der Eintrag fehlt, ist ein roter `sast`-Lauf sichtbar, aber
nicht merge-blockierend.

## 4 — Frontend-Coverage

Methode: `pnpm --filter @numra/web exec vitest run --coverage
--coverage.include='src/**/*.{ts,tsx}'`. Gemessen wird `src/**` über die Vitest-Suiten;
die Playwright-Suiten (`e2e/`, `e2e-system/`) zählen nicht dazu — sie laufen als eigene
Jobs. Messung zuletzt 2026-09-21 auf diesem Branch (69 Dateien, 321 Tests, alle grün):

**Erst war die Messung kaputt, nicht der Code.** `@vitest/coverage-v8` stand auf
`4.1.11`, während `vitest` auf `5.0.0` lief; der Provider brach mit
`TypeError: Expected string coverage payload, received object` ab und meldete für jede
Datei 0 %. Mit der passenden Major-Version (`5.0.0`) liefert derselbe Lauf echte Zahlen.
Ohne das wäre jede „Coverage"-Aussage in diesem Dokument geraten gewesen.

Messung nach der Korrektur:

```text
Statements 55.65% (2121/3811) · Branches 48.64% (1288/2648)
Functions  49.34% (607/1230)  · Lines    58.22% (1873/3217)
```

Ein Teil der 0-%-Dateien sind Seiten-Komponenten (`app/**/page.tsx`), die bewusst über
die Playwright-Suiten geprüft werden, nicht über Vitest. Der Zweck der Messung ist
deshalb **nicht** die Prozentzahl, sondern die Frage, welche risikoreichen Zweige
ungetestet sind. Nachgeführt:

* Auth-/Session-Zweige der Sicherheitskarte (`security-card.test.tsx`): falsches
  aktuelles Passwort, Mismatch ohne API-Aufruf, Erfolg, Sitzungsliste, Retry nach
  Ladefehler — vorher 0 % auf dieser Datei.
* Auth-Zweige des `AuthProvider` (`auth-context-login-logout.test.tsx`, 2026-09-21):
  Login-Erfolg, abgelehnte Credentials, Nicht-API-Fehler (Netzwerk) bei Login **und**
  Registrierung sowie Logout, der die lokale Sitzung auch bei fehlgeschlagenem
  API-Aufruf verwirft (`finally`). `lib/auth-context.tsx` geht damit von
  67.44 %/33.33 % (Lines/Branches) auf **100 %/83.33 %** — vorher waren `login`,
  `logout` und der Erfolgspfad von `refresh` überhaupt nicht ausgeführt.
* Fehlerzustände der Oberflächen: `ErrorState`/`LoadingState` waren hartcodiert
  englisch (#145) und sind jetzt katalogisiert; damit greifen die bestehenden
  Zustandstests auch die Übersetzung ab.

## 5 — Bewusst offen

* **Style-`unsafe-inline`** (siehe §2) — akzeptierte Ausnahme, nicht behoben.
* **Keine DAST-/Fuzzing-Stufe.** Der Umfang der Roadmap verlangt SAST; dynamische
  Angriffe auf die Live-Oberflächen sind nicht Teil dieses Nachweises.
* **Hartcodierte englische Fallback-Texte** in `lib/auth-context.tsx`
  (`"Login failed."` / `"Registration failed."`): erreichbar nur bei einem Nicht-API-
  Fehler (z. B. `NetworkError`), während API-Fehler deutsche Meldungen tragen — dieselbe
  Klasse wie der in #145 geschlossene Fall, aber außerhalb des SAST-Scopes und deshalb
  hier nur benannt, nicht geändert.
* **`app-shell.tsx:269`** wartet `logout()` ab, ohne die Ablehnung zu fangen; der
  Provider setzt den Zustand im `finally` trotzdem auf anonym und `RequireAuth`
  leitet auf `/login` um — die Folge ist eine unbehandelte Promise-Ablehnung in der
  Konsole, keine hängende Sitzung. Ebenfalls bewusst nicht in diesem PR geändert.

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

