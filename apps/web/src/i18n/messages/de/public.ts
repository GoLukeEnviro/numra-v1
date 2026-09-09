/** Öffentliche, nicht angemeldete Oberfläche: Landingpage, Login, Registrierung, Onboarding. Siehe `messages/de/index.ts` für die Modulaufteilung. */
export const dePublic = {
  // Landingpage
  "public.landing.navSignIn": "Anmelden",
  "public.landing.navCreateAccount": "Konto erstellen",
  "public.landing.heroEyebrow": "Auditierbare Numerologie",
  "public.landing.heroTitle": "Numerologie ohne Raten.",
  "public.landing.heroSubtitle":
    "Eine deterministische Engine berechnet jede Zahl nach dokumentierter Formel. Sprache erklärt nur, was bereits berechnet wurde — nichts wird geschätzt, nichts erfunden.",
  "public.landing.heroCtaCreate": "Konto erstellen",
  "public.landing.heroCtaSignIn": "Anmelden",
  "public.landing.signedInHint": "Du bist bereits angemeldet.",
  "public.landing.toDashboard": "Zur Übersicht",
  "public.landing.howTitle": "So funktioniert es",
  "public.landing.howStep1Title": "Profildaten",
  "public.landing.howStep1Body":
    "Geburtsname und Geburtsdatum genügen. Alles Weitere ist optionale Metadaten.",
  "public.landing.howStep2Title": "Deterministische Berechnung",
  "public.landing.howStep2Body":
    "Die Engine berechnet jeden Wert nach dokumentierter Formel. Gleiche Eingabe, gleiches Ergebnis, gleicher Hash — jederzeit reproduzierbar.",
  "public.landing.howStep3Title": "Nachvollziehbare Interpretation",
  "public.landing.howStep3Body":
    "Jede Zahl trägt ihre Herleitung Schritt für Schritt. Texte erklären die Werte, sie erzeugen keine.",
  "public.landing.featuresTitle": "Funktionen",
  "public.landing.featureProfileTitle": "Persönliches Profil",
  "public.landing.featureProfileBody": "Geburtsname, Geburtsdatum und Namenshistorie an einem Ort.",
  "public.landing.featureCoreTitle": "Kernzahlen",
  "public.landing.featureCoreBody": "Life Path, Expression und mehr — jede mit vollständigem Rechenweg.",
  "public.landing.featureTodayTitle": "Today & Timing",
  "public.landing.featureTodayBody": "Wo dieses Datum in einem persönlichen Zyklus liegt — live berechnet.",
  "public.landing.featureRelationshipsTitle": "Beziehungen",
  "public.landing.featureRelationshipsBody": "Zwei Profile im Vergleich, Metrik für Metrik — nie ein Score.",
  "public.landing.featureReportsTitle": "Berichte",
  "public.landing.featureReportsBody": "Ausführliche Lesungen, jede Zahl gegen die Berechnung geprüft.",
  "public.landing.featureHistoryTitle": "Historie & Vergleiche",
  "public.landing.featureHistoryBody": "Unveränderliche Snapshots, die sich sachlich vergleichen lassen.",
  "public.landing.transparencyTitle": "Transparenz",
  "public.landing.transparencyBody":
    "Alle Zahlen stammen aus der deterministischen Engine. Das Sprachmodell erklärt sie nur — es berechnet niemals einen Wert und erfindet keinen.",
  "public.landing.privacyTitle": "Datenschutz",
  "public.landing.privacyBody":
    "Gespeichert wird, was du eingibst: Profile, Berechnungen, Vergleiche, Berichte und dein Konto. Jedes Profil und das gesamte Konto sind jederzeit vollständig löschbar.",
  "public.landing.disclaimerTitle": "Hinweis",
  "public.landing.disclaimerBody":
    "AVENYTH ist ein symbolisches numerologisches Interpretationswerkzeug. Es bietet keine medizinische, rechtliche, finanzielle oder wissenschaftliche Beratung.",
  "public.landing.finalCtaTitle": "Belege statt Behauptungen.",
  "public.landing.finalCtaBody": "Erstelle ein Konto und prüfe jede Zahl selbst nach.",
  "public.landing.footerPrivacy": "Datenschutz",

  // Login
  "public.login.brandIntro":
    "Eine auditierbare Numerologie-Plattform. Eine deterministische Engine rechnet; Sprache erklärt nur, was sie bereits erzeugt hat.",
  "public.login.promise1": "Jede Zahl trägt die Herleitung, die sie erzeugt hat.",
  "public.login.promise2": "Gleiche Eingaben reproduzieren immer denselben Hash.",
  "public.login.promise3": "Kein Kompatibilitäts-Score wird jemals erfunden.",
  "public.login.subtitle": "Mit deinem Konto anmelden",
  "public.login.email": "E-Mail",
  "public.login.password": "Passwort",
  "public.login.submit": "Anmelden",
  "public.login.noAccount": "Noch kein Konto?",
  "public.login.createAccount": "Konto erstellen",
  "public.login.forgotPassword": "Passwort vergessen?",

  // Passwort vergessen
  "public.forgotPassword.title": "Passwort vergessen",
  "public.forgotPassword.subtitle": "Wir senden dir einen Link zum Zurücksetzen.",
  "public.forgotPassword.email": "E-Mail",
  "public.forgotPassword.submit": "Link anfordern",
  "public.forgotPassword.successTitle": "Anfrage gesendet",
  "public.forgotPassword.successBody":
    "Falls ein Konto mit dieser Adresse existiert, haben wir einen Link zum Zurücksetzen gesendet.",
  "public.forgotPassword.errorRateLimited": "Zu viele Versuche. Bitte versuche es später erneut.",
  "public.forgotPassword.backToLogin": "Zurück zum Login",

  // Passwort zurücksetzen
  "public.resetPassword.title": "Neues Passwort festlegen",
  "public.resetPassword.subtitle": "Lege ein neues Passwort für dein Konto fest.",
  "public.resetPassword.newPassword": "Neues Passwort",
  "public.resetPassword.passwordHint": "Mindestens 12 Zeichen.",
  "public.resetPassword.confirmPassword": "Neues Passwort bestätigen",
  "public.resetPassword.submit": "Passwort festlegen",
  "public.resetPassword.errorMismatch": "Die Passwörter stimmen nicht überein.",
  "public.resetPassword.errorTooShort": "Das Passwort muss mindestens 12 Zeichen lang sein.",
  "public.resetPassword.missingTokenTitle": "Link unvollständig",
  "public.resetPassword.missingTokenBody":
    "Dieser Link enthält kein gültiges Token. Fordere einen neuen Link an.",
  "public.resetPassword.successTitle": "Passwort geändert",
  "public.resetPassword.successBody":
    "Passwort wurde geändert. Alle Sitzungen wurden abgemeldet — bitte melde dich erneut an.",
  "public.resetPassword.successCta": "Zum Login",
  "public.resetPassword.invalidTitle": "Link nicht mehr gültig",
  "public.resetPassword.invalidBody":
    "Dieser Link kann nicht mehr verwendet werden. Fordere einen neuen Link an.",
  "public.resetPassword.invalidCta": "Neuen Link anfordern",
  "public.resetPassword.errorRateLimited": "Zu viele Versuche. Bitte versuche es später erneut.",

  // E-Mail bestätigen
  "public.verifyEmail.title": "E-Mail bestätigen",
  "public.verifyEmail.verifying": "E-Mail wird bestätigt…",
  "public.verifyEmail.successTitle": "E-Mail bestätigt",
  "public.verifyEmail.successBody": "Deine E-Mail-Adresse wurde erfolgreich bestätigt.",
  "public.verifyEmail.successCtaDashboard": "Zur Übersicht",
  "public.verifyEmail.successCtaLogin": "Zum Login",
  "public.verifyEmail.missingTokenTitle": "Link unvollständig",
  "public.verifyEmail.missingTokenBody": "Dieser Link enthält kein gültiges Token.",
  "public.verifyEmail.invalidTitle": "Link nicht mehr gültig",
  "public.verifyEmail.invalidBodySignedIn":
    "Dieser Bestätigungslink kann nicht mehr verwendet werden. Fordere einen neuen an.",
  "public.verifyEmail.invalidBodySignedOut":
    "Dieser Bestätigungslink kann nicht mehr verwendet werden. Melde dich an, um einen neuen anzufordern.",
  "public.verifyEmail.resendButton": "Neuen Bestätigungslink senden",
  "public.verifyEmail.resendSent": "Ein neuer Bestätigungslink wurde gesendet.",
  "public.verifyEmail.toLogin": "Zum Login",
  "public.verifyEmail.errorRateLimited": "Zu viele Versuche. Bitte versuche es später erneut.",

  // Registrierung
  "public.register.title": "Konto erstellen",
  "public.register.subtitle": "Ein Konto, alle Berechnungen — überprüfbar von jedem Gerät.",
  "public.register.email": "E-Mail",
  "public.register.password": "Passwort",
  "public.register.passwordConfirm": "Passwort bestätigen",
  "public.register.passwordHint": "Mindestens 12 Zeichen.",
  "public.register.submit": "Konto erstellen",
  "public.register.haveAccount": "Bereits ein Konto?",
  "public.register.toLogin": "Zum Login",
  "public.register.checkingConfig": "Registrierung wird vorbereitet…",
  "public.register.closedTitle": "Registrierung derzeit geschlossen.",
  "public.register.closedBody":
    "Diese Instanz nimmt aktuell keine neuen Konten an. Wenn du bereits eines hast, melde dich an.",
  "public.register.errorMismatch": "Die Passwörter stimmen nicht überein.",
  "public.register.errorTooShort": "Das Passwort muss mindestens 12 Zeichen lang sein.",
  "public.register.errorDuplicate": "Für diese E-Mail-Adresse existiert bereits ein Konto.",
  "public.register.errorDisabled": "Die Registrierung ist derzeit deaktiviert.",
  "public.register.errorRateLimited": "Zu viele Versuche. Bitte warte einen Moment und versuche es erneut.",
  "public.register.errorServer": "Der Server konnte die Registrierung nicht abschließen. Bitte versuche es später erneut.",
  "public.register.errorValidation": "Die Angaben wurden vom Server nicht akzeptiert. Bitte prüfe E-Mail und Passwort.",

  // Onboarding
  "public.onboarding.stepLabel": "Schritt",
  "public.onboarding.of": "von",
  "public.onboarding.welcomeTitle": "Willkommen bei AVENYTH",
  "public.onboarding.welcomeBody":
    "In drei kurzen Schritten legst du dein erstes Profil an und startest die erste deterministische Berechnung. Alles, was dabei entsteht, ist nachvollziehbar und jederzeit löschbar.",
  "public.onboarding.start": "Erstes Profil anlegen",
  "public.onboarding.profileTitle": "Erstes Profil",
  "public.onboarding.profileBody":
    "Geburtsname und Geburtsdatum steuern jede Kernzahl. Alles Weitere ist optional.",
  "public.onboarding.calcTitle": "Erste Berechnung",
  "public.onboarding.calcBody":
    "Das Profil ist angelegt. Starte jetzt die erste Berechnung — sie erzeugt einen unveränderlichen, gehashten Snapshot.",
  "public.onboarding.runCalculation": "Berechnung starten",
  "public.onboarding.calcRunning": "Berechnung läuft…",
  "public.onboarding.doneTitle": "Fertig",
  "public.onboarding.doneBody":
    "Dein erstes Profil und seine Berechnung sind angelegt. Die Analyse zeigt jede Zahl mit vollständiger Herleitung.",
  "public.onboarding.openAnalysis": "Analyse öffnen",
  "public.onboarding.existingTitle": "Du bist startklar",
  "public.onboarding.existingBody":
    "Für dieses Konto existiert bereits mindestens ein Profil — das Onboarding ist nicht nötig.",
  "public.onboarding.creating": "Profil wird angelegt…",
} as const;
