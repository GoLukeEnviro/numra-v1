# Interne Template-Tokens: Grammatik, Erkennung, Gates

**Stand:** 2026-10-09 · **Code:** `packages/engine-interpretation/src/numra_interpretation/llm/rendering_guard.py`
**Zweck:** Festhalten, welche Formen der Detektor als „interner Rest im fertigen Text" ablehnt, warum genau diese, und wo die Prüfung im System sitzt. Der Docstring des Moduls ist die kurze Fassung dieses Dokuments.

## 1. Woher die Grammatik kommt

Nicht aus einer allgemeinen Vorstellung von „Template-Syntax", sondern aus dem, was Prompts, `MockLLMProvider` und Pipelines tatsächlich erzeugen oder ein Modell daraus ableitet:

| Form | Erzeuger | Beispiel |
|---|---|---|
| Block-Label `[ROLE:LABEL]` | `MockLLMProvider._compose_text` und die Request-Rahmung jedes Providers | `[profile_fact:a:life_path]`, `[knowledge:communication:semantic_context]` |
| Rahmen ohne Label | dieselbe Rahmung | `[system]`, `[user_instructions]` |
| Kurz-Label `[PERSON:ID]` | ein generatives Modell kürzt das Block-Label (Audit 2026-10-09) | `[a:life_path]`, `[b:expression]` |
| Platzhalter | Prompt-Anweisung `_PLACEHOLDER_SYNTAX_INSTRUCTION`, Validator | `{{metric:life_path}}`, `{{special:a:hidden_passion}}` |
| Format-Feld | `str.format` (`refrain.format(title=...)` in den Report-Refrains) und Modelle, die eine Vorlage nachahmen | `{title}`, `{0}`, `{name!r}`, `{:>10}` |
| Sonstige Reste | Vorlagen anderer Systeme | `<partner_a>`, `%(name)s` |

ROLE ist eines von `profile_fact`, `knowledge`, `instruction_supplement`, `untrusted_user_content`. PERSON ist `a` oder `b`. ID ist eine Fakt-ID aus `KNOWN_FACT_IDS` (ein Test bindet die Menge an die Profil-Indizes) oder ein beliebiger snake_case-Bezeichner.

**Nicht Teil der Grammatik:** `$name` / `${name}` (kein Erzeuger im Repository; `${name}` fällt über das Format-Feld ohnehin auf), `%s` / `%d` (dito), Jinja (`{% … %}`; nicht eingesetzt). Wer einen dieser Erzeuger einführt, ergänzt zuerst den Test und dann das Muster.

## 2. Zwei Modi

| | `strict_braces=True` | `strict_braces=False` |
|---|---|---|
| Verwendet von | Beziehungsanalyse, Schatten-Dynamik | Report (Abschnitt, Zusammenfassung, Titel), Copilot-Antwort |
| Begründung | Der Prompt verbietet eckige Klammern ausdrücklich, und die Prosa braucht keine Klammer. | Freier Produkttext: einzelne Klammern, Mengen, Code, Mathematik und Anmerkungen in eckigen Klammern sind legitim. |
| Geschweifte Klammern | **jede** `{` oder `}` | nur konkrete Formen: `{{`/`}}` (auch unbalanciert), `{bezeichner}` mit optionalen `:`/`.`-Teilen, ungeschlossenes `{metric`/`{special`, jedes `str.format`-Feld |
| Kurz-Label | bekannte ID, snake_case-Bezeichner **und jeder geschlossene** `[a|b:bezeichner]` mit mindestens zwei Zeichen | bekannte ID oder snake_case-Bezeichner |

Gemeinsam in beiden Modi: die Rahmen-Marker (auch mit Blanks, Groß-/Kleinschreibung und Look-alikes), `[metric:`/`<special:`, `<partner_a>`, `%(name)s`, ein am Textende abgeschnittenes Label (`… [a:`, `… [b:soul_u`).

### Format-Feld im lockeren Modus

Erkannt wird die echte `str.format`-Grammatik `{` [Feldname] [`!`r|s|a] [`:` Spezifikation] `}`:

* benannte Felder: `{name}`, `{name!r}`, `{name:>10}`, `{a.b[0]!s:^5}`;
* positionale Felder mit Ziffern: `{0}`, `{12:>3}`, `{0.attr}` – **nicht** unmittelbar nach einem Wortzeichen, `^`, `_`, `\` oder einer schließenden Klammer (`a{3}`, `x^{2}`, `\frac{1}{2}` bleiben Prosa);
* Felder ohne Namen mit Konvertierung oder Spezifikation: `{!r}`, `{:>10}`, `{:.2f}`, `{:,}`.

Die Spezifikation folgt der echten Mini-Sprache (`[[fill]align][sign][z][#][0][width][grouping][.precision][type]`) und nicht „alles nach dem Doppelpunkt", damit Mengenschreibweise (`{x: x>0}`), JSON (`{"a": 1}`), Quantoren (`a{1,2}`), `{ 3 }`, `{1, 2, 3}` und `{}` Prosa bleiben.

## 3. Die Prüfansicht

Erkannt wird ausschließlich auf `canonical_for_check(text)`; **der gespeicherte oder ausgelieferte Text wird nie verändert** (Test: `test_the_check_never_changes_or_depends_on_the_stored_text`, `test_clean_text_is_stored_exactly_as_the_provider_wrote_it`, `test_copilot_reply_text_is_returned_unchanged`). Die Ansicht entsteht so:

1. `NFKD`, `casefold`, nochmals `NFKD` (`casefold` kann Combining-Zeichen erzeugen, z. B. `İ`). Vorher werden die beiden Lunate-Sigma-Zeichen auf `c` gefaltet, weil NFKD/casefold sie sonst zu `σ` machen.
2. Entfernt wird alles, was nichts darstellt: Formatzeichen `Cf` (Zero-Width, BiDi, Tags, Soft Hyphen), Combining Marks `Mn/Mc/Me`, Private Use/Surrogate/Unassigned `Co/Cs/Cn`, alle `Cc` außer Tab/Zeilenumbruch, dazu Hangul-Füller (U+115F, U+1160, U+3164, U+FFA0) und Braille-Blank (U+2800).
3. Nicht-ASCII-Dezimalziffern werden zu ASCII-Ziffern (`pinnacle_١` → `pinnacle_1`).
4. Look-alikes werden auf lateinische Kleinbuchstaben bzw. Satzzeichen gefaltet:
   * **systematisch aus dem Unicode-Namen** abgeleitet: `LATIN … LETTER X WITH …` (Strich, Haken, Schwanz: `ø`, `ł`, `đ`, `ƒ`, `ħ`), `SCRIPT G` (`ɡ`, U+0261), `LATIN LETTER SMALL CAPITAL X` (`ᴀ`, `ʙ`, `ꜱ` …), `DOTLESS I/J` (`ı`, `ȷ`). Ein Test scannt **ganz Unicode** nach diesen Namen, damit kein Zeichen außerhalb der eingelesenen Blöcke fehlt;
   * **per Liste** (`_VISUAL_CONFUSABLES`): Cyrillic, Greek, Armenian, einige Latin-Buchstaben ohne systematischen Namen, exotische Klammern (`❴ ⟦ 【 ⟨ …`), Doppelpunkte (`꞉ ː ∶ …`) und `ˍ` als Unterstrich.

Die Faltung kann nur zusätzliche Treffer erzeugen, wenn ein Text bereits die **Form** eines Tokens hat (Klammer, Buchstabe, Doppelpunkt, Bezeichner). Darum belegt eine Property-Prüfung: Text ohne jedes Klammerzeichen wird nie gemeldet (`test_property_text_without_bracket_characters_is_never_flagged`).

## 4. Entscheidungen mit Preis

* **`[a:foo]` (unbekannte ID ohne Unterstrich)** – in Analysen ein Rest (Prompt verbietet Klammern, ein geschlossenes `[a|b:wort]` ist ein kopiertes oder falsch geschriebenes Label). In Report und Copilot bleibt es Prosa: dort gibt es keinen Beleg, dass das Modell die Form erzeugt, und Anmerkungen in eckigen Klammern sind erlaubt. Bleibt die einzige bekannte Lücke dieser Form; die Zählung in `docs/ops/2026-10-09-stored-token-audit.md` zeigt in den Produktionsdaten keinen Fall.
* **`[a: Balance …]` als Dialogzeile** – beginnt mit einer bekannten Fakt-ID und wird wie das Label gelesen (beide Modi). Bewertung: Die Prüfansicht ist case-gefaltet und kann `[a: Balance` nicht von `[a: balance` trennen. Ein false negative speichert ein internes Token als fertigen Text, ein false positive kostet einen Wiederholungsversuch (danach `FAILED` mit Kategorie-Code, nichts gespeichert). Bleibt streng; durch Test festgeschrieben (`test_the_known_id_dialogue_case_is_a_documented_tradeoff`).
* **`{3}` im lockeren Modus** – ein positionales Feld, auch wenn jemand einen Quantor meint. Quantoren nach einem Wortzeichen (`a{3}`) und LaTeX bleiben Prosa; ein freistehendes `{3}` wird abgelehnt.
* **Länge** – Text über `MAX_CHECKED_TEXT_CHARS` (200 000 Zeichen) wird nicht gescannt und mit `OVERSIZE_TOKEN` abgelehnt. Kein Produkttext der Anwendung liegt auch nur in der Nähe (ein Report-Abschnitt hat einige tausend Zeichen). Innerhalb der Grenze sind alle Schritte linear; `_find_in_canonical_form` wird in den Tests ohne Grenze mit 300 000 Zeichen gegen die bekannten Worst-Case-Formen geprüft (der frühere quadratische Fall des Endankers in `_short_label_alternatives` bleibt damit Regressionsfall).

## 5. Wo geprüft wird

| Pfad | Gate in der Pipeline | Gate am Speicherpunkt |
|---|---|---|
| Beziehungsanalyse | pro Aussage `_validate_and_resolve_text`; am Ende `_assert_no_unresolved_tokens` über das **komplette** Ergebnis (`model_dump`), streng | `relationship_analysis_service`: `assert_no_unresolved_tokens` vor `finalize_*`, streng |
| Schatten-Dynamik | wie oben, inklusive Micro-Tasks und Herkunftsfelder | wie oben |
| Report | pro Abschnitt Text und Zusammenfassung, danach `lint_report` (Text, Summary, Titel), locker | `report_service`: Gate über `content_json` **vor** `persist_report_sections`, locker |
| Copilot | `_validate_reply`, locker; Mock-Antworten werden durch einen festen Satz ersetzt | `copilot_service`: Gate über `result.text` vor `COMPLETE`, locker |

Das Gate am Speicherpunkt (`apps/api/src/numra_api/services/persistence_gate.py`) ist unabhängig von den Pipelines: Es läuft über alle Zeichenketten (Werte und Schlüssel, beliebige Tiefe, ohne Rekursion). Ein Rest in einem Feld, das keine Pipeline-Prüfung kennt, endet damit im bestehenden Retry-/Fail-Pfad (`ANALYSIS_GENERATION_ERROR` bzw. `REPORT_GENERATION_ERROR`), nie als `COMPLETE`. Die Fehlermeldung nennt nur das Token (höchstens 64 Zeichen), nie den umgebenden Text.

## 6. Erweitern

1. Neue Form zuerst als roter Test in `packages/engine-interpretation/tests/unit/test_token_detector_hardening.py` (Treffer **und** Gegenprobe in Prosa).
2. Muster in `rendering_guard.py`; jede Teilklasse beschränkt oder aus disjunkten Zeichenklassen aufgebaut, damit die Worst-Case-Formen linear bleiben.
3. Bestehende Daten mit `scripts/ops/audit_stored_tokens.py` (schreibfrei, nur Zähler) gegenprüfen.
