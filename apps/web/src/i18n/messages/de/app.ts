/** Angemeldete Produktoberfläche: Übersicht, Personen, Heute, Berichte, Beziehungen, Analyse, Einstellungen. Siehe `messages/de/index.ts` für die Modulaufteilung. */
export const deApp = {
  // Übersicht (Dashboard)
  "app.dashboard.eyebrow": "Übersicht",
  "app.dashboard.heroTitle": "Numerologie, die du nachprüfen kannst",
  "app.dashboard.heroBody":
    "Jede Zahl in Numra stammt aus einer deterministischen Engine und trägt die Herleitung, die sie erzeugt hat. Nichts auf irgendeinem Bildschirm wird geschätzt, geschönt gerundet oder von einem Sprachmodell geschrieben, ohne gegen die Berechnung geprüft zu sein.",
  "app.dashboard.profileSingular": "Profil in deinem Konto",
  "app.dashboard.profilePlural": "Profile in deinem Konto",
  "app.dashboard.qaTodayTitle": "Heute",
  "app.dashboard.qaTodayBody": "Wo dieses Datum in einem persönlichen Zyklus liegt.",
  "app.dashboard.qaNewProfileTitle": "Neues Profil",
  "app.dashboard.qaNewProfileBody": "Geburtsname und Geburtsdatum genügen.",
  "app.dashboard.qaCompareTitle": "Vergleichen",
  "app.dashboard.qaCompareBody": "Zwei Profile, Metrik für Metrik — nie ein Score.",
  "app.dashboard.qaOpen": "Öffnen",
  "app.dashboard.yourPeople": "Deine Personen",
  "app.dashboard.loadingPeople": "Personen werden geladen…",
  "app.dashboard.viewAnalysis": "Analyse ansehen",
  "app.dashboard.profileLink": "Profil",
  "app.dashboard.lastAnalysisPrefix": "Letzte Analyse zum",
  "app.dashboard.noAnalysisYet": "Von diesem Browser aus wurde noch keine Analyse gestartet",

  // Personen (geteilt)
  "app.people.newProfile": "Neues Profil",
  "app.people.born": "Geboren am",
  "app.people.runCalculation": "Berechnung starten",
  "app.people.emptyTitle": "Noch keine Profile",
  "app.people.emptyBody":
    "Lege ein Profil mit Geburtsname und Geburtsdatum an, um die erste deterministische Berechnung zu starten.",

  // Personenliste
  "app.people.title": "Personen",
  "app.people.subtitle": "Alle Profile, die du angelegt hast.",
  "app.people.loading": "Profile werden geladen…",
  "app.people.badgeCurrentName": "Aktueller Name erfasst",
  "app.people.badgePreferredName": "Rufname",
  "app.people.badgeAnalysed": "Analysiert am",
  "app.people.openProfile": "Profil öffnen",

  // Personenformular (Neu / Bearbeiten / Onboarding)
  "app.personForm.birthName": "Geburtsname",
  "app.personForm.firstNames": "Vorname(n) *",
  "app.personForm.lastName": "Nachname *",
  "app.personForm.middleNames": "Zweitname(n)",
  "app.personForm.birthDate": "Geburtsdatum *",
  "app.personForm.birthTimePlace": "Geburtszeit & Geburtsort",
  "app.personForm.birthTimePlaceNote": "(nur Metadaten — beeinflusst nie eine Kernzahl)",
  "app.personForm.birthTime": "Geburtszeit",
  "app.personForm.timePrecision": "Zeitgenauigkeit",
  "app.personForm.precisionExact": "Genau",
  "app.personForm.precisionApproximate": "Ungefähr",
  "app.personForm.precisionUnknown": "Unbekannt",
  "app.personForm.birthPlace": "Geburtsort",
  "app.personForm.birthPlacePlaceholder": "z. B. Meerbusch",
  "app.personForm.countryCode": "Ländercode",
  "app.personForm.countryCodePlaceholder": "z. B. DE",
  "app.personForm.currentPreferred": "Aktueller Name & Rufname",
  "app.personForm.optionalNote": "(optional)",
  "app.personForm.currentFirstNames": "Aktuelle(r) Vorname(n)",
  "app.personForm.currentLastName": "Aktueller Nachname",
  "app.personForm.currentMiddleNames": "Aktuelle(r) Zweitname(n)",
  "app.personForm.preferredName": "Rufname",

  // Neues Profil
  "app.peopleNew.title": "Neues Profil",
  "app.peopleNew.description":
    "Geburtsname und Geburtsdatum steuern jede Kernzahl. Alles Weitere ist optional.",
  "app.peopleNew.creating": "Profil wird angelegt…",
  "app.peopleNew.calculating": "Berechnung läuft…",
  "app.peopleNew.submit": "Profil anlegen & berechnen",

  // Profil bearbeiten
  "app.peopleEdit.title": "Profil bearbeiten",
  "app.peopleEdit.description":
    "Geburtsname und Geburtsdatum steuern jede Kernzahl. Änderungen hier verändern nie eine bereits gelaufene Berechnung.",
  "app.peopleEdit.canonWarning":
    "Bestehende Berechnungen bleiben unverändert. Erst eine neue Berechnung nach dem Speichern verwendet diese Geburtsdaten.",
  "app.peopleEdit.save": "Änderungen speichern",
  "app.peopleEdit.cancel": "Abbrechen",
  "app.peopleEdit.backToProfile": "Zurück zum Profil",
  "app.peopleEdit.loadErrorTitle": "Profil konnte nicht geladen werden",

  // Personendetail
  "app.personDetail.eyebrow": "Profil",
  "app.personDetail.loadingProfile": "Profil wird geladen…",
  "app.personDetail.lastAnalysis": "Letzte Analyse",
  "app.personDetail.today": "Heute",
  "app.personDetail.edit": "Bearbeiten",
  "app.personDetail.birthDataTitle": "Geburtsdaten",
  "app.personDetail.birthDataBody":
    "Das Datum steuert Life Path, Birthday, Attitude und jeden Zyklus. Zeit und Ort werden nur als Metadaten gespeichert.",
  "app.personDetail.birthDate": "Geburtsdatum",
  "app.personDetail.birthTime": "Geburtszeit",
  "app.personDetail.birthPlace": "Geburtsort",
  "app.personDetail.notRecorded": "Nicht erfasst",
  "app.personDetail.historyTitle": "Berechnungshistorie",
  "app.personDetail.historyBody":
    "Jeder Snapshot ist dauerhaft — das Bearbeiten des Profils oben verändert keinen bestehenden. Wähle zwei, um sie zu vergleichen.",
  "app.personDetail.historyError": "Berechnungshistorie konnte nicht geladen werden.",
  "app.personDetail.noCalculations": "Noch keine Berechnungen.",
  "app.personDetail.asOf": "Zum Stichtag",
  "app.personDetail.open": "Öffnen",
  "app.personDetail.compareSelected": "Auswahl vergleichen",
  "app.personDetail.selectTwo": "Wähle zwei Snapshots zum Vergleichen.",
  "app.personDetail.selectOneMore": "Wähle noch einen aus.",
  "app.personDetail.readyToCompare": "Bereit zum Vergleich.",
  "app.personDetail.selectSnapshotAria": "Snapshot für den Vergleich auswählen, Stichtag",
  "app.personDetail.deleteTitle": "Dieses Profil löschen",
  "app.personDetail.deleteBody":
    "Entfernt das Profil und alles, was daraus berechnet wurde. Das lässt sich nicht rückgängig machen.",
  "app.personDetail.deleteButton": "Profil löschen",
  "app.personDetail.deleteConfirm": "Ja, endgültig löschen",
  "app.personDetail.deleteCancel": "Abbrechen",

  // Identität
  "app.identity.title": "Identität",
  "app.identity.body": "Die für dieses Profil erfassten Namen. Nur der Geburtsname geht in eine Berechnung ein.",
  "app.identity.birthLabel": "Geburtsname",
  "app.identity.birthNote": "Jede Kernzahl wird aus diesem Namen berechnet (canon-spec §5).",
  "app.identity.currentLabel": "Aktueller Name",
  "app.identity.currentNote": "Als Metadatum erfasst — verändert in dieser Version keine Kernzahl.",
  "app.identity.preferredLabel": "Rufname",
  "app.identity.preferredNote": "So wird diese Person in Numra angesprochen. Geht nie in eine Berechnung ein.",
  "app.identity.usedForCore": "Für Kernzahlen verwendet",
  "app.identity.partial": "Teilweise erfasst",
  "app.identity.partialNote":
    "Angezeigt werden nur die für dieses Profil gespeicherten Namensbestandteile — fehlende Teile werden nicht aus dem Geburtsnamen ergänzt.",
  "app.identity.noExtraNames":
    "Für dieses Profil ist kein aktueller Name und kein Rufname erfasst. Numra zeigt nur Namen, die es tatsächlich gespeichert hat.",
  "app.identity.recordedHistory": "Erfasste Historie",
  "app.identity.kindBirth": "Geburt",
  "app.identity.kindCurrent": "Aktuell",
  "app.identity.kindPreferred": "Rufname",
  "app.identity.validFrom": "Gültig ab",
  "app.identity.recordedAt": "Erfasst am",

  // Heute
  "app.today.title": "Heute",
  "app.today.subtitle": "Wo dieses Datum in einem persönlichen Zyklus liegt — live berechnet, nie geraten.",
  "app.today.whoseDay": "Wessen Tag?",
  "app.today.loadingPeople": "Personen werden geladen…",
  "app.today.reading": "Heutige Werte werden gelesen…",
  "app.today.timingErrorTitle": "Timing für heute konnte nicht gelesen werden",
  "app.today.unreadableTiming": "Unlesbares Timing",
  "app.today.emptyTitle": "Noch keine Profile",
  "app.today.emptyBody":
    "Heute braucht ein Geburtsdatum als Grundlage. Lege ein Profil an, und diese Seite wird deine Tagesansicht.",
  "app.today.masterNumber": "Meisterzahl",
  "app.today.derivedShow": "Wie wurden diese Werte hergeleitet?",
  "app.today.derivedHide": "Herleitung ausblenden",
  "app.today.footnote":
    "Diese Werte werden auf Anfrage für das heutige Datum neu berechnet und nicht als Snapshot gespeichert. Für einen datierten, gehashten Beleg starte eine Berechnung im Profil der Person.",
  "app.today.reflection": "Reflexion",
  "app.today.composing": "Reflexion wird zusammengestellt…",
  "app.today.reflectionErrorTitle": "Die Reflexion konnte nicht geladen werden",
  "app.today.reflectionFootnotePrefix":
    "Reflexiv und symbolisch, bezogen aus Numras Wissenspaket — keine Vorhersage und nicht von einem Sprachmodell geschrieben. Neu berechnet für",
  "app.today.reflectionFootnoteSuffix": "nicht gespeichert.",

  // Berichte (Liste)
  "app.reports.title": "Berichte",
  "app.reports.subtitle": "Jede ausführliche Lesung, die du erzeugt hast — serverseitig, von jedem Gerät sichtbar.",
  "app.reports.filterAll": "Alle",
  "app.reports.filterPending": "In Arbeit",
  "app.reports.filterComplete": "Fertig",
  "app.reports.filterFailed": "Fehlgeschlagen",
  "app.reports.filterByStatus": "Nach Status filtern",
  "app.reports.filterByPerson": "Nach Person filtern",
  "app.reports.allPeople": "Alle Personen",
  "app.reports.generated": "Erzeugt am",
  "app.reports.started": "Gestartet am",
  "app.reports.words": "Wörter",
  "app.reports.openCalculation": "Berechnung",
  "app.reports.open": "Öffnen",
  "app.reports.loading": "Berichte werden geladen…",
  "app.reports.errorTitle": "Deine Berichte konnten nicht geladen werden",
  "app.reports.emptyTitle": "Noch keine Berichte",
  "app.reports.emptyBody": "Erzeuge einen Bericht auf der Analyseseite einer Berechnung, um ihn hier zu sehen.",

  // Berichtsdetail
  "app.reportDetail.back": "Zurück zur Berechnung",
  "app.reportDetail.loading": "Bericht wird geladen…",
  "app.reportDetail.errorTitle": "Dieser Bericht konnte nicht geladen werden",
  "app.reportDetail.unreadableTitle": "Unlesbarer Bericht",

  // Analyse
  "app.analysis.eyebrow": "Berechnung",
  "app.analysis.asOf": "Zum Stichtag",
  "app.analysis.writtenReport": "Schriftlicher Bericht",
  "app.analysis.immutableNote":
    "Dieser Snapshot ist unveränderlich. Dieselbe Person am selben Stichtag reproduziert exakt den obigen Hash — jeder Wert auf dieser Seite lässt sich Schritt für Schritt auf seine Eingaben zurückführen.",
  "app.analysis.tabCore": "Kernzahlen",
  "app.analysis.tabInspector": "Rechen-Inspektor",
  "app.analysis.tabCycles": "Zyklen & Timing",
  "app.analysis.tabsAria": "Analyse-Ansichten",
  "app.analysis.loading": "Berechnung wird geladen…",
  "app.analysis.errorTitle": "Diese Analyse konnte nicht geladen werden",
  "app.analysis.unreadableTitle": "Unlesbare Berechnung",

  // Snapshot-Vergleich
  "app.compare.back": "Zurück zum Profil",
  "app.compare.title": "Snapshot-Vergleich",
  "app.compare.loading": "Beide Snapshots werden geladen…",
  "app.compare.loadingOne": "Vergleich wird geladen…",
  "app.compare.errorTitle": "Die Snapshots konnten nicht geladen werden",
  "app.compare.unreadableTitle": "Unlesbarer Snapshot",
  "app.compare.differentPeopleTitle": "Diese Snapshots gehören zu verschiedenen Personen",
  "app.compare.differentPeopleBody":
    "Ein Vergleich ergibt nur zwischen zwei Berechnungen derselben Person Sinn.",
  "app.compare.chooseTitle": "Wähle zwei Snapshots",
  "app.compare.chooseBody":
    "Öffne das Profil einer Person, wähle zwei Berechnungen aus der Historie und dann „Auswahl vergleichen“.",
  "app.compare.factualNote":
    "Dies ist ein sachlicher Diff, nicht mehr: Er zeigt, welche Werte sich zwischen den beiden Snapshots unterscheiden — und hört dort auf. Numra berechnet keinen Wachstums-Score, keinen Verbesserungs-Prozentsatz und kein Urteil, welcher Snapshot „besser“ wäre.",
  "app.compare.stableTitle": "Stabile Kernzahlen",
  "app.compare.stableChanged":
    "Diese Werte unterscheiden sich zwischen den Snapshots — vermutlich, weil Name oder Geburtsdaten der Person zwischenzeitlich bearbeitet wurden.",
  "app.compare.stableUnchanged":
    "In beiden Snapshots identisch — wie erwartet, wenn die zugrunde liegende Identität unverändert blieb.",
  "app.compare.timingTitle": "Datumsabhängiges Timing",
  "app.compare.timingBody": "Unterschiede sind erwartbar — jeder Snapshot wurde für einen anderen Stichtag berechnet.",
  "app.compare.metricColumn": "Metrik",

  // Beziehungen
  "app.relationships.title": "Beziehungen",
  "app.relationships.subtitle": "Vergleiche zwei berechnete Profile, Metrik für Metrik.",
  "app.relationships.formTitle": "Zwei Profile vergleichen",
  "app.relationships.formBody":
    "Numra vergleicht die jeweils neueste Berechnung beider Personen. Wer noch keine hat, braucht zuerst eine.",
  "app.relationships.personA": "Erste Person",
  "app.relationships.personB": "Zweite Person",
  "app.relationships.compare": "Vergleichen",
  "app.relationships.chooseDifferent": "Wähle zwei verschiedene Personen.",
  "app.relationships.noCalcYet": "Dieses Profil hat noch keine Berechnung.",
  "app.relationships.openProfileToRun": "Profil öffnen und Berechnung starten",
  "app.relationships.recent": "Letzte Vergleiche",
  "app.relationships.loadingProfiles": "Profile werden geladen…",
  "app.relationships.loadingComparisons": "Vergleiche werden geladen…",
  "app.relationships.comparisonsErrorTitle": "Deine Vergleiche konnten nicht geladen werden",
  "app.relationships.emptyTitle": "Lege ein zweites Profil zum Vergleichen an",
  "app.relationships.emptyBody":
    "Numra braucht mindestens zwei Personen mit je einer Berechnung, bevor es sie vergleichen kann.",
  "app.relationships.open": "Öffnen",

  // Beziehungsdetail
  "app.relationshipDetail.all": "Alle Vergleiche",
  "app.relationshipDetail.eyebrow": "Vergleich",
  "app.relationshipDetail.created": "Erstellt am",
  "app.relationshipDetail.loading": "Vergleich wird geladen…",
  "app.relationshipDetail.errorTitle": "Dieser Vergleich konnte nicht geladen werden",
  "app.relationshipDetail.noScoreNote":
    "Numra vergleicht zwei Profile Metrik für Metrik und hört dort auf. Es berechnet keinen Kompatibilitäts-Prozentsatz, keine Trefferzahl und keinen kombinierten Score — dafür gibt es keine vertretbare deterministische Methode, und eine erfundene Zahl würde alles andere auf dieser Seite untergraben.",
  "app.relationshipDetail.coreTitle": "Kernzahlen",
  "app.relationshipDetail.coreBody":
    "Abgeleitet aus Geburtsname und Geburtsdatum jeder Person. Diese Werte ändern sich nicht.",
  "app.relationshipDetail.timingTitle": "Timing",
  "app.relationshipDetail.timingBody":
    "Abgeleitet aus dem Stichtag jeder Berechnung — sinnvoll vergleichbar nur, wenn beide Berechnungen denselben Stichtag teilen.",
  "app.relationshipDetail.sameValue": "Gleicher Wert",
  "app.relationshipDetail.differentValues": "Unterschiedliche Werte",
  "app.relationshipDetail.noMetrics": "Dieser Vergleich enthielt keine der erwarteten Metriken.",
  "app.relationshipDetail.notesTitle": "Beziehungsnotizen",
  "app.relationshipDetail.notesBody":
    "Wie sich die Zahl jeder Person in Beziehungen typischerweise zeigt, Seite an Seite — bezogen aus Numras Wissenspaket, nicht pro Vergleich generiert.",
  "app.relationshipDetail.sameNumber": "Gleiche Zahl",
  "app.relationshipDetail.calcA": "Berechnung A",
  "app.relationshipDetail.calcB": "Berechnung B",

  // Einstellungen: Datenschutz
  "app.privacy.title": "Datenschutz & Daten",
  "app.privacy.subtitle": "Was Numra speichert, was es nie berechnet und wie du alles entfernst.",
  "app.privacy.storedTitle": "Was auf dem Server gespeichert wird",
  "app.privacy.storedProfiles": "Personenprofile",
  "app.privacy.storedProfilesBody":
    "— Geburtsname, Geburtsdatum sowie optional Geburtszeit / Geburtsort / aktueller Name, wie beim Anlegen eingegeben.",
  "app.privacy.storedCalculations": "Berechnungen",
  "app.privacy.storedCalculationsBody":
    "— unveränderliche, deterministische Snapshots des kanonischen Ergebnisses zu einem Stichtag, inklusive vollständiger Herleitung und einem Hash über Eingaben und Ergebnis.",
  "app.privacy.storedRelationships": "Beziehungsvergleiche",
  "app.privacy.storedRelationshipsBody":
    "— die beiden verglichenen Berechnungs-IDs und der daraus entstandene Metrik-Vergleich.",
  "app.privacy.storedReports": "Berichte und Exporte",
  "app.privacy.storedReportsBody":
    "— der Text jedes erzeugten Berichts und jedes daraus gerenderte PDF (als Datei auf dem Server, bis du es löschst).",
  "app.privacy.storedAccount": "Dein Konto",
  "app.privacy.storedAccountBody":
    "— E-Mail-Adresse und Sitzungsdaten, ausschließlich zur Anmeldung verwendet.",
  "app.privacy.neverTitle": "Was diese App nie berechnet oder speichert",
  "app.privacy.neverScore": "Für Beziehungsvergleiche wird nie ein Kompatibilitäts-Prozentsatz berechnet.",
  "app.privacy.neverDiagnosis": "Es werden keine Diagnosen und keine medizinisch-psychologischen Aussagen erzeugt.",
  "app.privacy.neverBirthTime":
    "Geburtszeit und Geburtsort sind reine Metadaten — sie beeinflussen in dieser Version keine Kernzahl.",
  "app.privacy.deleteOneTitle": "Ein einzelnes Profil löschen",
  "app.privacy.deleteOneBody":
    "Jedes Profil lässt sich auf seiner eigenen Seite löschen; dabei wird auch entfernt, was daraus berechnet wurde.",

  // Einstellungen: Sicherheit
  "app.security.title": "Sicherheit",
  "app.security.body": "Passwort ändern und verwalten, wo du angemeldet bist.",
  "app.security.currentPassword": "Aktuelles Passwort",
  "app.security.newPassword": "Neues Passwort",
  "app.security.confirmPassword": "Neues Passwort bestätigen",
  "app.security.mismatch": "Die neuen Passwörter stimmen nicht überein.",
  "app.security.changed": "Passwort geändert. Andere Geräte wurden abgemeldet; dieses bleibt angemeldet.",
  "app.security.changeButton": "Passwort ändern",
  "app.security.activeSessions": "Aktive Sitzungen",
  "app.security.loadingSessions": "Sitzungen werden geladen…",
  "app.security.sessionsErrorTitle": "Sitzungen konnten nicht geladen werden",
  "app.security.thisDevice": "Dieses Gerät",
  "app.security.otherDevice": "Anderes Gerät",
  "app.security.signedIn": "Angemeldet am",
  "app.security.current": "Aktuell",
  "app.security.logoutOthers": "Andere Geräte abmelden",
  "app.security.othersLoggedOut": "Andere Geräte wurden abgemeldet.",

  // Einstellungen: Systeminfo
  "app.systemInfo.title": "Systeminfo",
  "app.systemInfo.body": "Womit diese Numra-Instanz läuft.",
  "app.systemInfo.environment": "Umgebung",
  "app.systemInfo.timezone": "App-Zeitzone",
  "app.systemInfo.sessionLifetime": "Sitzungsdauer",
  "app.systemInfo.selfSignup": "Selbstregistrierung",
  "app.systemInfo.llmProvider": "LLM-Anbieter",
  "app.systemInfo.pdfExport": "PDF-Export",
  "app.systemInfo.enabled": "aktiviert",
  "app.systemInfo.disabled": "deaktiviert",
  "app.systemInfo.errorTitle": "Systeminfo konnte nicht geladen werden",

  // Konto löschen
  "app.deleteAccount.title": "Mein Konto löschen",
  "app.deleteAccount.body":
    "Löscht dauerhaft alles, was Numra über dich speichert. Es gibt kein Zurück, keinen nachträglichen Export und keine Schonfrist.",
  "app.deleteAccount.listIntro": "Endgültig gelöscht werden:",
  "app.deleteAccount.itemProfiles": "jedes Personenprofil, das du angelegt hast",
  "app.deleteAccount.itemCalculations": "jede Berechnung samt gespeicherter Herleitung",
  "app.deleteAccount.itemRelationships": "jeder Beziehungsvergleich",
  "app.deleteAccount.itemReports": "jeder erzeugte Bericht",
  "app.deleteAccount.itemExports": "jedes exportierte PDF, inklusive der Dateien auf dem Server",
  "app.deleteAccount.itemAccount": "dein Konto und seine Zugangsdaten",
  "app.deleteAccount.exportHint":
    "Wenn du eine Kopie eines Berichts behalten willst, exportiere vorher sein PDF — exportierte Dateien werden ebenfalls gelöscht.",
  "app.deleteAccount.confirmLabel": "Mit deinem Passwort bestätigen",
  "app.deleteAccount.wrongPassword": "Das Passwort stimmte nicht. Es wurde nichts gelöscht.",
  "app.deleteAccount.submit": "Alles endgültig löschen",
  "app.deleteAccount.submitting": "Alles wird gelöscht…",
  "app.deleteAccount.cancel": "Abbrechen",

  // Berichts-Start & Export & Fortschritt
  "app.reportLauncher.title": "Schriftlicher Bericht",
  "app.reportLauncher.body":
    "Eine ausführliche Lesung, geschrieben aus genau dieser Berechnung. Jede genannte Zahl wird vor dem Zusammenstellen gegen das kanonische Profil geprüft.",
  "app.reportLauncher.length": "Berichtslänge",
  "app.reportLauncher.generate": "Bericht erzeugen",
  "app.reportLauncher.starting": "Erzeugung wird gestartet…",
  "app.reportLauncher.previous": "Bereits aus dieser Berechnung gestartete Berichte",
  "app.reportLauncher.startedAt": "Gestartet am",
  "app.reportLauncher.open": "Öffnen",
  "app.export.title": "Export",
  "app.export.body":
    "Rendert diesen Bericht als PDF. Die Datei entsteht aus dem Bericht exakt wie gespeichert — ein Export erzeugt oder verändert nie Text.",
  "app.export.button": "PDF exportieren",
  "app.export.rendering": "PDF wird gerendert…",
  "app.export.renderingHint": "Das PDF wird auf dem Server gerendert; das dauert meist ein paar Sekunden.",
  "app.export.failed": "Das PDF konnte nicht gerendert werden. Du kannst den Export erneut versuchen.",
  "app.export.available": "Verfügbare Dateien",
  "app.export.download": "Herunterladen",
  "app.export.none": "Für diesen Bericht wurde noch kein PDF gerendert.",
  "app.export.earlierFailedBadge": "Früherer Versuch fehlgeschlagen",
  "app.export.earlierFailedBody": "Ein früherer Export dieses Berichts wurde nicht abgeschlossen.",
  "app.reportProgress.writing": "Dein Bericht wird geschrieben",
  "app.reportProgress.aria": "Fortschritt der Berichtserzeugung",
  "app.reportProgress.contacting": "Verbindung zur Erzeugungs-Warteschlange…",
  "app.reportProgress.retriedPrefix": "Versuch",
  "app.reportProgress.retriedSuffix": "— die Warteschlange hat nach einem behebbaren Fehler neu gestartet.",
  "app.reportProgress.checkNote":
    "Jede Zahl im fertigen Text wird gegen das kanonische Profil dieser Berechnung geprüft. Hier erscheint nichts, bevor diese Prüfung bestanden ist.",
  "app.reportFailed.title": "Berichtserzeugung fehlgeschlagen",
  "app.reportFailed.reportedBy": "gemeldet vom Erzeugungs-Job",
  "app.reportFailed.afterAttempts": "Versuchen",
  "app.reportFailed.after": "nach",
  "app.reportFailed.untouched":
    "Deine Berechnung ist unberührt — sie ist unveränderlich und wurde von diesem Lauf nie verändert. Ein Neustart stellt einen komplett neuen Bericht aus derselben Berechnung in die Warteschlange.",
  "app.reportFailed.retry": "Neuen Bericht erzeugen",
} as const;
