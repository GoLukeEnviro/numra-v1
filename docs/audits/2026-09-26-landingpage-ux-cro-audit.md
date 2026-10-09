# Landingpage-Audit: UX/UI, Kommunikation und CRO

- **Datum:** 2026-09-26
- **Gegenstand:** öffentliche Startseite `https://avenyth.de/` (`apps/web/src/app/page.tsx`, Texte in `apps/web/src/i18n/messages/de/public.ts`)
- **Methode:** Code- und Textanalyse, Rendering der Live-Seite (Chromium, 1440×900, 390×844, 360×780, 320×780), Kontrastmessung nach WCAG 2.2, Prüfung der Folgeschritte (`/register`, `/login`, `/settings/privacy`), Abgleich mit Markenrichtlinie (`docs/brand/visual-identity.md`), Produktvision (`specs/v2/product-vision.md`) und Wettbewerbsrecherche.
- **Rahmen:** Alle Vorschläge halten die Markenregeln ein: kurze Sätze im Indikativ, keine Ausrufezeichen, keine Superlative, keine Vorhersagen und keine erfundenen Zahlen oder Testimonials. Der Grundsatz „NO EVIDENCE → NO CLAIM" gilt auch für das Marketing.

---

## 1 · Audit-Analyse

### Gesamtbild

Die Seite ist technisch sauber, markentreu und ruhig. Sie verkauft aber ein anderes, kleineres Produkt als das, das tatsächlich live ist, und sie spricht dabei die Sprache der Entwickler statt die der Zielgruppe. Sie überzeugt Menschen, die schon wissen, was ein Hash ist. Menschen, die sich selbst oder ihre Beziehung besser verstehen wollen, holt sie kaum ab.

| Kategorie | Bewertung (1–5) | Kernaussage |
|---|---|---|
| Markenkonsistenz & Ästhetik | 4 | Ruhig, dunkel, würdevoll. Die Differenzierung zu Esoterik-Kitsch gelingt. |
| Nutzenkommunikation | 1,5 | Die Seite erklärt, wie gerechnet wird, aber kaum, was man davon hat. |
| Vollständigkeit des Angebots | 1,5 | Der V2-Kern (Beziehungs-Workspaces, Check-ins, Roadmaps, Copilot) fehlt komplett. |
| Vertrauen & Einwandbehandlung | 2 | Transparenz wird behauptet, aber nicht gezeigt. Datenschutz-Link führt zum Login, Impressum fehlt. |
| Conversion-Mechanik | 2 | Zwei gleichwertige CTAs, kein Mehrwert vor der Registrierung, mobiler Header-CTA abgeschnitten. |
| Barrierefreiheit | 3,5 | Solide Basis (Fokusring, Reduced Motion, Semantik). Zwei Kontrastfehler, kleine Touch-Ziele. |

### 1.1 Kommunikation & Text

**K1 – Mechanik statt Nutzen (kritisch).** Hero, Schritt 2, Schritt 3, der Transparenz-Block und die Login-Seite wiederholen fünfmal dieselbe Botschaft: Die Engine rechnet, die Sprache erklärt nur. Dass jemand nachrechnen *kann*, ist ein Vertrauensargument. Ein Grund, sich anzumelden, ist es nicht. Nirgends steht, wofür man die Zahlen nutzt: Selbstverständnis, Orientierung in Lebensphasen, bessere Gespräche in der Beziehung.

**K2 – Ingenieursjargon.** Die sichtbaren Texte enthalten „deterministische Engine", „Hash", „Snapshot", „Metrik", „Metadaten", „auditierbar" und „Sprache erklärt nur". Laut Markenrichtlinie sind das „spirituell interessierte Menschen, die Belege statt Behauptungen wollen", also keine Softwareentwickler. Fachbegriffe senken die Verarbeitungsflüssigkeit, und Aussagen, die schwer zu verarbeiten sind, halten Leser eher für unwahr (Processing-Fluency-Effekt). Das schadet genau dem Vertrauen, das die Begriffe aufbauen sollen.

**K3 – Das halbe Produkt fehlt (kritisch).** Die Seite stammt aus V1.6 (Kommentar „V1.6 B" in `page.tsx`). Sie zeigt Profil, Kernzahlen, Today, Vergleich, Berichte und Historie. Laut `docs/planning/avenyth-pwa-execution-state.md` ist aber der ganze V2-Beziehungskern live: Beziehungs-Workspaces, getrennt beantwortete Check-ins, gemeinsame Roadmaps, geteilte Reflexionen, persönlicher Copilot und Beziehungs-Copilot, Evidenz-Layer sowie Einwilligungssteuerung. Die Marke positioniert sich als „Personal & Relationship Development OS". Auf der Seite kommen weder „Entwicklung" noch „gemeinsam" vor. Selbst die Logo-Geschichte (zwei Wege, die sich mittendrin treffen) wird nicht erzählt.

**K4 – Die Seite klingt kälter als das Produkt.** In der App gibt es bereits warme, menschliche Texte, zum Beispiel „Wie geht es euch miteinander?", „Ihr beantwortet dieselben Fragen getrennt. Erst wenn beide abgegeben haben, entsteht eine gemeinsame, sachliche Auswertung." oder „Eure privaten Reflexionen bleiben privat." (`de/app.ts`). Die Startseite fällt hinter diese Tonalität zurück. Die beste Copy steckt hinter dem Login.

**K5 – Negationsrahmen ohne positives Versprechen.** „Numerologie ohne Raten." ist ein starker Unterscheidungs-Claim. Er sagt aber nur, was AVENYTH *nicht* ist. Ohne ein positives Nutzenversprechen daneben bleibt offen, was man bekommt.

**K6 – Generische Abschnittstitel und gemischte Sprache.** Titel wie „Funktionen", „Transparenz", „Datenschutz" und „Hinweis" sind austauschbare Etiketten. „Today & Timing", „Life Path, Expression" stehen auf Englisch in einer deutschen Seite, während die App-Navigation „Heute" sagt. „Alles Weitere ist optionale Metadaten" ist grammatisch holprig und technisch.

**K7 – Fehlende Einwandbehandlung.** Unbeantwortet bleiben die Fragen, die kurz vor einer Registrierung entscheiden:
- Was kostet das?
- Brauche ich meine Geburtszeit? (Nein. Das ist ein starker Reibungsabbau, steht aber versteckt in Schritt 1.)
- Wer sieht meine Beziehungsdaten?
- Was macht die KI genau?
- Warum zeigen andere Rechner andere Zahlen?
- Wer steht hinter AVENYTH?

**K8 – CTA-Text beschreibt Aufwand statt Ergebnis.** „Konto erstellen" nennt die Arbeit, die man leisten muss. Den Gewinn nennt der Button nicht.

**K9 – Metadaten.** Der Seitentitel ist nur „AVENYTH". Die Beschreibung ist technisch formuliert, und es gibt kein Open-Graph-Bild. Gerade bei einem Beziehungsprodukt wird der Link aber per Messenger geteilt, und dort erscheint dann nur eine nackte Vorschau.

### 1.2 Visuelles Design & UX

**V1 – Mobiler Header-CTA abgeschnitten (kritisch, gemessen).** Die Buttonleiste im Header bricht nicht um. „Konto erstellen" endet bei jeder Viewport-Breite bei x = 391 px. Bei 360 px (verbreitete Android-Breite) ist der Button sichtbar abgeschnitten („Konto erstell…"), bei 320 px ragt er 71 px aus dem Bild. Die Seite scrollt horizontal (`scrollWidth` 391 bei 320/360/390 px). Betroffen ist ausgerechnet der primäre CTA im permanent sichtbaren Bereich.

**V2 – „Datenschutz" im Footer führt zum Login (kritisch).** Der Link zeigt auf `/settings/privacy`. Diese Seite liegt hinter `RequireAuth`, und anonyme Besucher landen gemessen auf `/login`. Wer vor der Registrierung den Datenschutz prüfen will, und das sind gerade die skeptischen Wunschnutzer, stößt auf eine Wand. Das Impressum fehlt ganz (bekannter offener Punkt im Execution State). Für eine kommerzielle deutsche Website ist es Pflicht (§ 5 DDG), und es ist ein Vertrauenssignal.

**V3 – Kein Produktbild, keine Demonstration.** Der Hero besteht nur aus Text. Der stärkste Beleg des Produkts ist der sichtbare Rechenweg in Monospace, die „Sprache der Verifikation" aus der Markenrichtlinie. Er taucht nirgends auf. Transparenz wird behauptet statt gezeigt. Auf Desktop bleiben unter den Buttons rund 40 % des sichtbaren Bereichs leer.

**V4 – Zwölf gleich aussehende Karten, kein Blickfang.** 3 + 6 + 2 + 1 Kästen mit identischem Stil (`rounded-xl border bg-surface`). Nach dem Gestaltgesetz der Ähnlichkeit wirkt dadurch alles gleich wichtig, und das Auge findet keinen Ankerpunkt. Die Seite hat keinen Rhythmus: kein Wechsel zwischen breit und schmal, zwischen Bild und Text, zwischen dicht und luftig.

**V5 – Falsche Gewichtung beim Hinweis.** Der Haftungshinweis steht in `surface-2`, der *hellsten* Fläche der Seite, und damit in der auffälligsten Box. Er sitzt direkt vor dem finalen CTA. Nach dem Von-Restorff-Effekt bleibt so ausgerechnet die Warnung im Gedächtnis, genau im Moment der Entscheidung.

**V6 – Konkurrierende CTAs.** Im Hero und im Schluss-CTA stehen „Konto erstellen" und „Anmelden" als zwei große Buttons nebeneinander. Bestandsnutzer haben ihren Weg bereits im Header. Für Neue wirkt der zweite Button wie eine gleichwertige Alternative (Hick's Law). Er hält außerdem den Platz für einen Einstieg mit wenig Verbindlichkeit besetzt, etwa „Beispiel ansehen".

**V7 – Kleine Touch-Ziele (Fitts's Law).** Die Header-Buttons sind 32 px hoch, die Footer-Links 20 px. WCAG 2.5.8 (AA, 24 px) ist im Header erfüllt. Die Plattformempfehlung von 44 px verfehlen beide, und im Footer sind die Links sehr klein.

**V8 – Kontrastfehler (gemessen).**

| Element | Kontrast | Soll (WCAG 1.4.3) |
|---|---|---|
| Hero-Eyebrow, Bronze `#8F6B3E` auf `#0B0B0F`, 12 px | 4,06 : 1 | 4,5 : 1 (nicht erfüllt) |
| Schrittnummern „01–03", Bronze auf `#13131A`, 14 px | 3,82 : 1 | 4,5 : 1 (nicht erfüllt) |
| Fließtext Asche auf Obsidian | 6,59 : 1 | erfüllt |
| CTA-Text auf Gold | 8,74 : 1 | erfüllt |

**V9 – Motiv überlagert Headline auf Mobil.** Die Knoten des NumericWheel liegen auf 360–390 px direkt über „Raten." und dem Fließtext. Das bleibt dekorativ und barrierefrei, wirkt aber unruhig und widerspricht der Regel, das Emblem nicht auf unruhige Flächen zu setzen.

**V10 – Typografie.** Die Seite nutzt System-Serif (Georgia/ui-serif). Je nach Betriebssystem erscheint dadurch eine andere Schrift, und die Anmutung ist solide, aber nicht hochwertig. Die CSP (`font-src 'self'`) erlaubt selbst gehostete Schriften bereits, technisch gibt es also keine Hürde.

**V11 – Registrierungsformular.** Es hat drei Felder, eines davon „Passwort bestätigen". Laut Formularanalyse-Studien (Zuko) ist dieses Feld ein häufiger Abbruchgrund. Es gibt keine Anzeigen-Option für das Passwort. Fehlermeldungen zeigen technische Codes wie `PASSWORD_TOO_SHORT` als Chip vor dem Text. Der Untertitel „überprüfbar von jedem Gerät" ist Jargon und kein Nutzen.

**V12 – Kleinigkeiten.** Die ganze Seite ist eine Client-Komponente. Während der Auth-Status lädt, sehen angemeldete Nutzer kurz die Gast-CTAs, bevor „Zur Übersicht" erscheint. Für SEO und LCP wäre eine Server-Komponente mit kleiner Client-Insel für die auth-abhängigen Buttons besser.

**Stärken, die erhalten bleiben sollen:** konsistente Tokens, sehr gute Fließtextkontraste, sichtbarer goldener Fokusring, `prefers-reduced-motion`, semantische Überschriften, `role="note"` beim Hinweis, schnelle Antwortzeiten und eine gute Lesebreite im Hero.

### 1.3 Psychologische Wirkung

**Was wirkt:** Die Seite differenziert sich klar vom Esoterik-Kitsch und strahlt Ruhe und Ernsthaftigkeit aus. Für die Zielgruppe der „skeptischen Suchenden" ist das ein echter Vorteil. Die konsistente Gestaltung erzeugt Kompetenzvermutung (Halo-Effekt).

**Was fehlt:** Die Seite spricht fast nur das analytische System 2 an. Einen emotionalen Einstieg (System 1) gibt es nicht. Keine Frage, keine Situation, kein „das kenne ich" holt die Leser ab.

| Prinzip (Cialdini u. a.) | Ist-Zustand | Potenzial |
|---|---|---|
| **Reziprozität** | Jeder Wert liegt hinter der Registrierung. | Etwas vor der Anmeldung schenken: Beispielanalyse, später ein öffentlicher Lebenszahl-Rechner. |
| **Autorität** | Nur behauptet („deterministische Engine"). | Zeigen: echter Rechenweg, dokumentierte Methode, kuratierte Wissensbasis mit erkennbaren Autoren. |
| **Soziale Bewährtheit** | Nicht vorhanden. | Nur echte, eingewilligte Stimmen, etwa aus dem Testkreis. Keine erfundenen Zahlen. Bis dahin „Transparenz als Beleg". |
| **Sympathie** | Kein Mensch, keine Stimme, kein „Wir". | Kurze Gründer- bzw. Haltungsnotiz: warum AVENYTH nicht rät. |
| **Commitment & Konsistenz** | Der erste Schritt ist gleich die volle Registrierung. | Mikro-Schritt vorab, zum Beispiel ein Geburtsdatum eingeben und ein Teilergebnis sehen. |
| **Einheit (Unity)** | Kein Identitätsangebot. | „Für Menschen, die Numerologie ernst nehmen und deshalb Belege wollen." Das ist eine starke Wir-Gruppe. |
| **Knappheit** | Nicht vorhanden. | **Bewusst nicht einsetzen.** Künstliche Verknappung widerspricht der Markenwürde. |
| **Zeigarnik / Neugierlücke** | Nicht genutzt. | Ein Teilergebnis zeigen, die vollständige Herleitung mit Konto. |
| **Risikoumkehr / Verlustaversion** | „Jederzeit löschbar" steht versteckt im Datenschutz-Block. | Direkt unter den CTA: „jederzeit vollständig löschbar", „nur zwei Angaben". |
| **Gestalt: Figur/Grund, Nähe** | Keine Figur, alles ist Grund. | Ein dominantes Hero-Element (Rechenweg-Demo). Gruppierung in „Für dich" und „Für euch". |

---

## 2 · Benchmark-Vergleich

| Anbieter | Erfolgsmuster | Übertragung auf AVENYTH |
|---|---|---|
| **Co–Star** | Technische Glaubwürdigkeit („NASA-Daten") gepaart mit einem emotionalen Versprechen („das Rätsel menschlicher Beziehungen entschlüsseln"). Presse-Logos als Autorität. | Methode und menschliches Ergebnis in *einem* Satz verbinden. Die Methode ist die Begründung, das Ergebnis ist das Versprechen. |
| **The Pattern** | Verzichtet vollständig auf Fachjargon. Übersetzt Chart-Daten in psychologische Themenkarten („Sich selbst vertrauen"). „Bonds" sind ein zentraler Einstieg. | Zahlen auf der Landingpage in menschliche Themen übersetzen. Beziehungen als gleichrangigen Einstieg zeigen. |
| **CHANI** | „Von echten Astrologen, nicht von KI" als Vertrauensanker. Freemium mit weicher Paywall: erst Wert, dann Bitte. | „Kuratiert, nicht generiert": Die Deutungen stammen aus einer versionierten, redaktionell gepflegten Wissensbasis (`knowledge/`, `AUTHORING_GUIDE.md`), die KI erklärt nur. 2026 ist das ein seltenes und glaubwürdiges Differenzierungsmerkmal. |
| **Deutsche Numerologie-Rechner** (numerologie.app, astro-seek, soultarot) | Sofortwert ohne Anmeldung: „Lebenszahl berechnen" ist Einstiegspunkt, SEO-Kopfbegriff und Lead-Magnet zugleich. | Größte Marktlücke von AVENYTH. Die Rechner liefern oft unterschiedliche Ergebnisse. „Warum zeigt jeder Rechner etwas anderes?" ist ein realer Schmerzpunkt, den nur AVENYTH mit Herleitung beantworten kann. |
| **Paar-Apps** (Paired, Connected) | „Forschungsbasiert" bzw. Expertenrahmen, Quiz-Einstieg, Stimmen echter Paare, Einladung der Partnerin oder des Partners als Wachstumsschleife. | Eine eigene Seite für eingeladene Personen. Den Check-in-Mechanismus („getrennt beantworten, gemeinsam auswerten") als Beleg für Fairness und Privatsphäre zeigen. |
| **Product-Led-Growth-Daten** | Interaktive Produktdemos erzielen deutlich höhere Interaktion als statische Seiten (Chameleon/HowdyGo, Walnut, Forrester 2024). | Den Rechenweg interaktiv zeigen statt ihn zu beschreiben. |
| **Formular-Forschung** (Zuko) | Das Weglassen von „Passwort bestätigen" zugunsten eines Anzeigen-Schalters erhöhte die Conversion in einer Fallstudie um 56 %, ohne mehr Passwort-Resets. | Direkt übertragbar auf `/register`. |

**Die sieben Muster, die AVENYTH umsetzen sollte:**
1. Ergebnis zuerst, Methode als Begründung.
2. Den Beweis zeigen statt ihn zu behaupten.
3. Einen Wert vor der Registrierung geben.
4. Menschliche Autorschaft sichtbar machen („kuratiert, nicht generiert").
5. Beziehungen als zweiten, gleichrangigen Einstieg anbieten.
6. Einwände vor dem CTA beantworten (Mikrotexte, FAQ).
7. Nur echte soziale Belege verwenden, sonst gar keine.

---

## 3 · Konkreter Optimierungsplan

### 3.1 Quick Wins (Aufwand: Stunden bis wenige Tage)

| # | Maßnahme | Psychologische Begründung |
|---|---|---|
| QW1 | **Mobilen Header reparieren:** unter 400 px den Ghost-Button „Anmelden" durch ein kompaktes Icon oder einen Textlink ersetzen oder den CTA auf „Starten" kürzen. `min-h-11` (44 px) für Header-CTAs, Footer-Links mit `py-2`. | Fitts's Law: Ein erreichbares, großes Ziel senkt den Aufwand. Ein abgeschnittener CTA wirkt zudem wie ein Qualitätsmangel (Halo-Effekt umgekehrt). |
| QW2 | **Hero-Texte neu** (siehe Copy-Deck unten): Nutzen zuerst, „Ohne Raten" als Begründung. | Processing Fluency, Benefit-Framing. |
| QW3 | **CTA-Text und Mikrotext:** „Konto erstellen" wird zu „Mein Profil berechnen". Darunter: „Nur Name und Geburtsdatum · keine Geburtszeit nötig · jederzeit vollständig löschbar". | Ergebnis- statt Aufwandsframing. Risikoumkehr und Reibungsabbau direkt am Entscheidungspunkt. |
| QW4 | **Zweiter Hero-Button:** „Anmelden" wird zu „So sieht eine Analyse aus" (Anker zu einem Beispielabschnitt). „Anmelden" bleibt im Header. | Hick's Law. Foot-in-the-door: ein unverbindlicher erster Schritt. |
| QW5 | **Datenschutz-Link reparieren:** Bis `/datenschutz` existiert, auf einen öffentlichen Datenschutz-Abschnitt der Startseite verlinken, nicht auf eine Login-Wand. Impressum und Datenschutz haben ohnehin höchste Priorität (NEXT_ACTION 1). | Vertrauen entsteht durch Überprüfbarkeit. Eine Login-Wand an dieser Stelle wirkt wie Verschleierung, das Gegenteil des Markenversprechens. |
| QW6 | **Registrierung entschlacken:** „Passwort bestätigen" entfernen und einen Anzeigen-Schalter ergänzen. Fehler-Codes nur noch als `data-`Attribut bzw. für den Support, nicht sichtbar. Untertitel neu. | Weniger Felder bedeuten weniger kognitive Last. Zuko-Daten. |
| QW7 | **Jargon ersetzen:** „Hash", „deterministisch", „Snapshot", „Metrik" und „Metadaten" aus den sichtbaren Texten nehmen oder übersetzen. Die Fachbegriffe wandern in eine aufklappbare Ebene „Für Genaue: Wie wir rechnen". | Processing Fluency. Wer Tiefe sucht, findet sie auf Wunsch (Progressive Disclosure). |
| QW8 | **Hinweis umgestalten:** gleiche Flächenfarbe wie die übrigen Karten oder als ruhige Textzeile über dem Footer. Titel „Was AVENYTH ist, und was nicht". Sichtbar bleibt er in jedem Fall. | Von-Restorff-Effekt gezielt nutzen: Die Aufmerksamkeit gehört dem Nutzen. Eine ehrliche Abgrenzung erhöht zugleich die Glaubwürdigkeit. |
| QW9 | **Kontraste beheben:** Eyebrow und Schrittnummern in Gold `#C8A96B` (etwa 8,7 : 1) oder ein aufgehelltes Bronze mit mindestens 4,5 : 1. | Lesbarkeit, WCAG 1.4.3. |
| QW10 | **Metadaten:** Titel „AVENYTH · Numerologie mit Herleitung, für dich und deine Beziehungen", eine menschliche Beschreibung, ein OG-Bild mit Emblem und Claim. | Die erste Berührung findet oft im Messenger statt. Mere Exposure: Ein wiedererkennbares Bild prägt sich ein. |
| QW11 | **Sprache vereinheitlichen:** „Today & Timing" wird zu „Heute & Zyklen". Deutsche Namen der Kernzahlen, bei Bedarf mit dem englischen Begriff in Klammern. | Konsistenz senkt Reibung. Einheitliche Sprache wirkt sorgfältig. |

#### Copy-Deck für die Quick Wins

**Hero, Variante A (Selbst + Beziehung, empfohlen als Standard):**
> *Eyebrow:* Numerologie mit Herleitung
> **Verstehe dich. Und euch. Ohne Raten.**
> AVENYTH berechnet deine Zahlen nach dokumentierten Formeln und zeigt dir jeden Rechenschritt. So entsteht ein ruhiger Raum für deine eigene Entwicklung und für das, was ihr gemeinsam gestaltet.
> **[Mein Profil berechnen]**  [So sieht eine Analyse aus]
> *Nur Name und Geburtsdatum · keine Geburtszeit nötig · jederzeit vollständig löschbar*

**Hero, Variante B (Skeptiker, Schmerzpunkt zuerst):**
> **Drei Rechner, drei Ergebnisse? Hier siehst du jeden Schritt.**
> Viele Numerologie-Seiten liefern unterschiedliche Zahlen und erklären keine davon. AVENYTH rechnet nach einer dokumentierten Formel: Gleiche Angaben ergeben immer dasselbe Ergebnis, und du siehst, wie es entsteht.

**Hero, Variante C (Beziehung, erzählt das Logo):**
> **Zwei Wege. Ein gemeinsamer Moment.**
> Vergleicht eure Profile Zahl für Zahl, ohne erfundenen Kompatibilitätswert. Dann gestaltet ihr, was euch wichtig ist: mit Check-ins, gemeinsamen Roadmaps und Reflexionen. Ihr entscheidet, was geteilt wird.

**Registrierung, Untertitel:**
> Ein Konto für dein Profil, deine Berechnungen und deine Beziehungen. Jederzeit exportierbar und vollständig löschbar.

**Onboarding, Willkommen** (statt „erste deterministische Berechnung"):
> In drei kurzen Schritten zu deinem ersten Profil. Du siehst jede Zahl mit ihrem Rechenweg und kannst alles jederzeit wieder löschen.

**Schluss-CTA:**
> **Belege statt Behauptungen.** *(bleibt, der Claim trägt)*
> Mit zwei Angaben zu deinem ersten vollständigen Profil, jeder Rechenschritt inklusive.
> **[Mein Profil berechnen]**

> Wörter wie „kostenlos", „kein Abo", „Server in Deutschland" oder „keine Werbung" sind starke Reibungsabbauer. Sie dürfen **nur** verwendet werden, wenn sie nachweislich zutreffen (UWG § 5, und „NO EVIDENCE → NO CLAIM"). Das muss der Betreiber vorab bestätigen.

### 3.2 Strategische Neuausrichtung (Aufwand: Wochen, Markenbildung)

**S1 – Die Seite neu erzählen: vom Rechner zum Entwicklungsraum.** Neue Dramaturgie nach dem Muster Problem, Beleg, Nutzen, Einwand, Handlung:

1. **Hero** mit Rechenweg-Demo (S2)
2. **„Kennst du das?"**: vier Schmerzpunkte mit Antwort
3. **So funktioniert es**: drei bis vier Schritte, ohne Jargon
4. **Für dich / Für euch**: zweispaltig, die Logo-Geschichte als verbindendes Motiv
5. **Kuratiert, nicht generiert**: Methode und Wissensbasis
6. **Deine Daten, deine Entscheidung**: Privatsphäre und Einwilligung
7. **Häufige Fragen**
8. **Was AVENYTH ist, und was nicht**
9. **Schluss-CTA**

*Begründung:* Das AIDA-Muster in Kombination mit Einwandbehandlung vor dem CTA, Unity durch die Wir-Gruppe und die Gestalt-Nähe in der Aufteilung „Für dich / Für euch".

**Copy für „Kennst du das?"** (Schmerzpunkt, dann Antwort):
- *„Drei Rechner, drei Ergebnisse. Und keiner sagt, warum."* Bei AVENYTH trägt jede Zahl ihren vollständigen Rechenweg.
- *„Eine App gibt eurer Beziehung 63 %. Und jetzt?"* Wir zeigen Gemeinsamkeiten und Unterschiede einzeln, als Anlass für ein Gespräch statt als Note.
- *„KI-Texte klingen tief und sagen alles und nichts."* Unsere Deutungen stammen aus einer kuratierten Wissensbasis. Die KI erklärt nur, was bereits berechnet ist.
- *„Du willst Gedanken festhalten, ohne alles zu teilen."* Privat bleibt privat. Gemeinsam sichtbar wird nur, was du ausdrücklich freigibst.

**Copy für „Für dich / Für euch"** (orientiert an der vorhandenen App-Tonalität):

| Für dich | Für euch |
|---|---|
| **Deine Kernzahlen**: Lebenszahl, Ausdruckszahl und weitere, jede mit vollständigem Rechenweg. | **Vergleich ohne Score**: Zwei Profile nebeneinander, Zahl für Zahl. Nie eine erfundene Gesamtnote. |
| **Heute**: Wo der heutige Tag in deinem persönlichen Zyklus liegt. | **Check-ins**: Ihr beantwortet dieselben Fragen getrennt. Erst wenn beide abgegeben haben, entsteht eine gemeinsame Auswertung. |
| **Persönliches Gespräch**: Stell Fragen zu deinem Profil. Die Antworten stützen sich nur auf deine berechneten Werte. | **Gemeinsame Roadmaps**: Plant euren nächsten Abschnitt in kleinen, greifbaren Schritten. |
| **Ausführliche Berichte**: Lesungen zum Nachlesen und als PDF, jede Zahl gegen die Berechnung geprüft. | **Geteilte Reflexionen**: Nur ausdrücklich geteilte Gedanken erscheinen gemeinsam. |

> **Vor der Veröffentlichung abgleichen:** Nur Funktionen bewerben, deren Feature-Flag in Produktion aktiv ist. Die App kennt Zustände wie „Check-ins sind noch nicht verfügbar" und „Copilot kommt bald".

**S2 – „Zeigen statt behaupten": Rechenweg-Demo im Hero.** Ein stilisiertes, echtes Produktfragment für ein **fiktives** Beispielprofil. Es darf nicht das Golden-Fixture mit Klarnamen sein. Beispiel: „Mara Lindqvist, 14.03.1991", daraus drei Rechenschritte in Monospace, daraus „Lebenszahl 1" mit einer Zeile Deutung. Statisch oder als dezente Schritt-für-Schritt-Einblendung; mit `prefers-reduced-motion` erscheint alles sofort. Es genügt eine vorab berechnete, statische Darstellung, dafür ist keine neue API nötig.
*Begründung:* Demonstrierte Autorität wirkt stärker als behauptete. Die Demo wird zur Figur vor dem Grund und schafft den fehlenden Blickfang.

**S3 – Wert vor der Registrierung: öffentlicher Lebenszahl-Rechner.** Eingabe eines Geburtsdatums, Ergebnis Lebenszahl plus Rechenweg. Eine Zeile verweist auf den Rest: „Ausdruckszahl, Seelenzahl, persönlicher Zyklus und die vollständige Deutung: mit Profil." Technisch wäre das ein zustandsloser, rate-limitierter öffentlicher Endpunkt ohne Speicherung. Die Engine ist deterministisch und läuft ohne Netzwerkzugriff, fachlich ist das also risikoarm. Die Entscheidung braucht ein ADR, weil „keine Numerologie-Logik im Browser" gilt und bisher jede Berechnung authentifiziert ist. Später entsteht daraus die deutsche SEO-Landingpage „Lebenszahl berechnen" für den Kopfbegriff im DACH-Markt.
*Begründung:* Reziprozität, Zeigarnik-Effekt, Commitment durch einen Mikro-Schritt und der IKEA-Effekt: Das eigene Ergebnis wird wertvoller.

**S4 – „Kuratiert, nicht generiert" als Markensäule.** Ein eigener Abschnitt bzw. eine Seite „Unsere Methode": woher die Deutungen kommen (versionierte Wissensbasis, Autorenrichtlinie), was die KI darf und was nicht, warum es keinen Kompatibilitätswert gibt. Optional veröffentlicht AVENYTH die Formelspezifikation. Das wäre ein Autoritätsbeleg, den kein Wettbewerber bieten kann. Ergänzend eine kurze, persönliche Haltungsnotiz der Gründerin oder des Gründers.
*Begründung:* Autorität durch Transparenz und Sympathie durch ein menschliches Gesicht. Das CHANI-Muster passt in einer Zeit wachsender KI-Skepsis besonders gut.

**S5 – Ethisches Social-Proof-Programm.** Nach dem Testkreis (`docs/planning/web08-test-circle-readiness.md`) echte Zitate mit schriftlicher Einwilligung sammeln, mit Vorname oder Initial und Kontext („nutzt AVENYTH mit ihrem Partner"). Keine erfundenen Nutzerzahlen, keine Sterne ohne Quelle. Bis dahin ersetzt die Rechenweg-Demo den sozialen Beleg.
*Begründung:* Soziale Bewährtheit. Echtheit ist hier die Bedingung, sonst bricht das Markenversprechen.

**S6 – Wachstumsschleife über Einladungen.** Eine eigene Landing-Variante für eingeladene Personen (`/connections/redeem`): „[Name] möchte mit dir einen gemeinsamen Raum auf AVENYTH öffnen." Dazu Klartext, was geteilt wird und was privat bleibt. Diesen Einstieg nutzen die erfolgreichen Paar-Apps.
*Begründung:* Unity, Commitment durch eine persönliche Bitte und eine vertraute Absenderin oder ein vertrauter Absender als Vertrauenstransfer.

**S7 – High-End-Anhebung des Markenbilds.**
- Eine selbst gehostete, lizenzierte Display-Serifenschrift mit hohem Kontrast für H1 und H2. Georgia bleibt als Fallback.
- Ein editoriales Layout mit asymmetrischem Raster und wechselndem Abschnittsrhythmus: breiter Hero, schmale Textspalte, ein großflächiges Motiv, ein dichtes Kartenraster.
- Das konstruierte A großformatig als Linienmotiv (Gold-Hairlines, Pflaume für das Gemeinsame) statt des NumericWheel am Rand.
- Produktbilder in Geräterahmen.
- Die Bewegungsregel (≤ 4 px) bleibt bestehen. Eine einzige sequenzielle Einblendung der Rechenweg-Demo wäre eine bewusste, dokumentierte Ausnahme in der Markenrichtlinie.

*Begründung:* Hochwertig wirkt Zurückhaltung mit Präzision und Rhythmus, nicht zusätzliche Dekoration. Das Gestaltgesetz der Prägnanz spricht für ein starkes Motiv statt vieler schwacher.

**S8 – Architektur.** Die Landingpage wird Server-Komponente, die auth-abhängigen Buttons werden eine kleine Client-Insel. Das bringt besseres LCP, SEO-Fähigkeit und beseitigt das Umschalten der Gast-CTAs.

**S9 – Preis-Transparenz, sobald Billing kommt.** Eine eigene Preissektion mit klarem kostenlosem Einstieg. Ein Ankerpreis ist nur zulässig, wenn es ihn wirklich gibt.

---

## 4 · Implementierungs-Roadmap

### Phase 0: Voraussetzungen (Woche 1)

1. **Rechtliches:** Öffentliche Seiten `/impressum` und `/datenschutz` einrichten (NEXT_ACTION 1, wartet auf Angaben des Betreibers). Den Footer-Link darauf umstellen.
2. **Messung aufsetzen:** Die CSP (`connect-src 'self'`) schließt Drittanbieter-Analytics aus. Das passt zur Marke. Nötig ist deshalb ein First-Party-Event-Endpunkt in der eigenen API oder ein selbst gehostetes, cookieloses Tool. Ob es datenschutzrechtlich ohne Einwilligung auskommt (§ 25 TDDDG), muss juristisch geprüft werden.
3. **Funnel-Events definieren:**
   `landing_view → cta_click{position, variant} → register_view → register_submit → register_success → onboarding_profile_created → first_calculation_done → analysis_opened → return_d7`
4. **Baseline** zwei bis vier Wochen messen. `robots.txt` bleibt bei `Disallow: /`, bis die rechtlichen Seiten live sind.

### Phase 1: Quick Wins (Woche 1–3)

- QW1, QW5, QW6 und QW9 sind Fehlerbehebungen. Sie gehen **ohne A/B-Test** live, weil sie reine Defekte beheben.
- QW2 bis QW4, QW7, QW8, QW10 und QW11 sind Copy- und Hierarchieänderungen. Sie werden, wenn der Traffic reicht, als erster Test ausgespielt (T1/T2), sonst als Vorher-Nachher-Vergleich mit qualitativer Absicherung.
- Qualitativ: ein 5-Sekunden-Test mit fünf bis acht Personen aus der Zielgruppe mit der Frage „Was bietet AVENYTH, und für wen?". Erfolgskriterium: mindestens 70 % nennen sowohl die eigene Entwicklung als auch Beziehungen. Heute ist zu erwarten, dass die meisten „Numerologie-Rechner" antworten.

### Phase 2: Neue Dramaturgie und Beleg (Woche 3–8)

- S1 (Seitenstruktur mit Copy-Deck), S2 (Rechenweg-Demo), S4 (Methode, Haltungsnotiz), FAQ.
- Die beworbenen Funktionen gegen die Produktions-Flags abgleichen.
- Usability-Test mit fünf Personen: den Weg von der Landingpage bis zur ersten Analyse laut denkend durchlaufen lassen.

### Phase 3: Wert vor der Registrierung (Woche 8–14)

- ADR für den öffentlichen Rechen-Endpunkt, dann S3 umsetzen.
- Deutsche SEO-Unterseiten („Lebenszahl berechnen", „Warum Numerologie-Rechner unterschiedliche Ergebnisse liefern").
- `robots.txt` öffnen, sobald Rechtsseiten und ehrlicher Conversion-Pfad stehen.

### Phase 4: Markenaufbau (ab Quartal 2)

- S7 (Typografie, Art Direction), S5 (Testkreis-Zitate), S6 (Einladungs-Landing), S8 (Server-Komponente), S9 (Preise mit Billing).

### Validierungsstrategie und A/B-Testdesign

**Metriken**
- **Primär:** Registrierungsrate = `register_success` ÷ eindeutige `landing_view`.
- **North-Star (Aktivierung):** `first_calculation_done` innerhalb von 24 h ÷ `landing_view`. So ist sichergestellt, dass nicht nur mehr, sondern die *richtigen* Menschen kommen.
- **Guardrails:**
  - Aktivierungsquote unter den Registrierten
  - Fehlerquote bei der Registrierung
  - Kontolöschungen innerhalb von 7 Tagen (ein Hinweis auf übertriebene Versprechen)
  - Absprungrate

**Testmatrix** (nacheinander, nicht parallel auf derselben Fläche):

| Test | Hypothese | Varianten |
|---|---|---|
| T1 Hero | Nutzen zuerst steigert die Registrierungsrate, weil Besucher schneller verstehen, was sie bekommen. | Kontrolle vs. A (Selbst + Beziehung) vs. B (Skeptiker) |
| T2 CTA | Ergebnisorientierter CTA-Text plus Mikrotext zur Risikoumkehr steigert die CTA-Klickrate. | „Konto erstellen" vs. „Mein Profil berechnen" + Mikrotext |
| T3 Formular | Zwei Felder statt drei steigern die Abschlussrate. | Mit vs. ohne „Passwort bestätigen" |
| T4 Beleg | Eine Rechenweg-Demo steigert Vertrauen und Registrierung. | Text-Hero vs. Demo-Hero |
| T5 Reziprozität | Ein öffentlicher Rechner steigert die Aktivierung. | Ohne vs. mit Rechner (Gewinnerseite aus T1–T4) |

**Stichprobe, ehrlich gerechnet:** Bei einer angenommenen Basis von 3 % Registrierungsrate und einer relativen Mindestwirkung von 20 % (3,0 % → 3,6 %) braucht es bei α = 0,05 und 80 % Power rund **14.000 Besucher pro Variante**. Solange `robots.txt` die Seite sperrt und kein bezahlter Traffic fließt, ist das nicht erreichbar. Daraus folgt:
- Nur große Unterschiede testen (neuer Hero statt Wortvarianten).
- Sequenzielle oder bayessche Auswertung mit vorab festgelegten Abbruchkriterien.
- In Niedrigtraffic-Phasen qualitative Tests (5-Sekunden-Test, Usability-Test) und Vorher-Nachher-Vergleiche mit gleicher Dauer und gleichem Wochentagsmix.
- Das Test-Setup steht in Phase 0 bereit und wird aktiviert, sobald nach der Öffnung genug Traffic ankommt.

**Technik:** Die Varianten werden serverseitig in `apps/web/src/middleware.ts` zugewiesen, das ohnehin bei jeder Anfrage läuft. Die Zuweisung bleibt über einen First-Party-Wert stabil. Ob dafür eine Einwilligung nötig ist, muss juristisch geprüft werden, alternativ bietet sich eine cookielose, täglich rotierende Zuweisung an. Die Variante wird an jedem Funnel-Event mitgeloggt, und die Auswertung ist vorab in einem kurzen Testprotokoll festgelegt: Hypothese, Metrik, Laufzeit, Abbruchkriterium.

---

## Quellen (Benchmark-Recherche)

- [Co–Star: Hyper-Personalized, Real-Time Horoscopes](https://www.costarastrology.com/)
- [Design Critique: Co-Star (IXD@Pratt)](https://ixd.prattsi.org/2024/09/design-critique-co-star-ios-app/)
- [App Showcase: The Pattern (screensdesign)](https://screensdesign.com/showcase/the-pattern)
- [The Pattern App Review 2026 (Aurae)](https://www.auraeastrology.com/blog/the-pattern-app-review-2026-an-astrologers-honest-opinion)
- [The CHANI App](https://www.chani.com/app)
- [App Showcase: CHANI (screensdesign)](https://screensdesign.com/showcase/chani-your-astrology-guide)
- [Numerologie.app: Lebenszahl berechnen](https://www.numerologie.app/lebenszahl-berechnen)
- [Astro-Seek: Numerologie-Rechner](https://de.astro-seek.com/numerologie-online-rechner-gratis)
- [Connected: The App for Couples](https://www.connectedcouples.app/)
- [Onboarding Funnels That Convert (SwipeTogether)](https://swipetogether.com/blog/onboarding-funnels-that-convert)
- [Interactive Demo Best Practices (Chameleon)](https://www.chameleon.io/blog/interactive-demo-best-practices)
- [Interactive Demos & B2B Conversion Rates (Walnut)](https://www.walnut.io/blog/product-demos/interactive-demos-conversion-rates-b2b-2026-data/)
- [Should you use "Confirm Password"? Case Study (Zuko)](https://www.zuko.io/blog/should-you-use-confirm-password-on-your-forms-and-websites-case-study)
- [Why the Confirm Password Field Must Die (UX Movement)](https://uxmovement.com/forms/why-the-confirm-password-field-must-die/)
- [Landing Page Social Proof (KlientBoost)](https://www.klientboost.com/landing-pages/landing-page-testimonials/)
