import type { deApp } from "@/i18n/messages/de/app";

/** English counterpart of `de/app.ts`; typed against its key set so `tsc` enforces parity. */
export const enApp: Record<keyof typeof deApp, string> = {
  // Dashboard
  "app.dashboard.eyebrow": "Overview",
  "app.dashboard.heroTitle": "Numerology you can check",
  "app.dashboard.heroBody":
    "Every number in Numra is produced by a deterministic engine and carries the trace that produced it. Nothing on any screen is estimated, rounded towards a nicer answer, or written by a language model without being checked against the calculation first.",
  "app.dashboard.profileSingular": "profile in your account",
  "app.dashboard.profilePlural": "profiles in your account",
  "app.dashboard.qaTodayTitle": "Today",
  "app.dashboard.qaTodayBody": "Where this date falls in a personal cycle.",
  "app.dashboard.qaNewProfileTitle": "New profile",
  "app.dashboard.qaNewProfileBody": "A birth name and date is all it takes.",
  "app.dashboard.qaCompareTitle": "Compare",
  "app.dashboard.qaCompareBody": "Two profiles, metric by metric — never a score.",
  "app.dashboard.qaOpen": "Open",
  "app.dashboard.yourPeople": "Your people",
  "app.dashboard.loadingPeople": "Loading your people…",
  "app.dashboard.viewAnalysis": "View analysis",
  "app.dashboard.profileLink": "Profile",
  "app.dashboard.lastAnalysisPrefix": "Last analysis as of",
  "app.dashboard.noAnalysisYet": "No analysis run from this browser yet",

  // People (shared)
  "app.people.newProfile": "New profile",
  "app.people.born": "Born",
  "app.people.runCalculation": "Run calculation",
  "app.people.emptyTitle": "No profiles yet",
  "app.people.emptyBody":
    "Create a profile with a birth name and birth date to run its first deterministic calculation.",

  // People list
  "app.people.title": "People",
  "app.people.subtitle": "Every profile you have created.",
  "app.people.loading": "Loading people…",
  "app.people.badgeCurrentName": "Current name recorded",
  "app.people.badgePreferredName": "Preferred name",
  "app.people.badgeAnalysed": "Analysed",
  "app.people.openProfile": "Open profile",

  // Person form (new / edit / onboarding)
  "app.personForm.birthName": "Birth name",
  "app.personForm.firstNames": "First name(s) *",
  "app.personForm.lastName": "Last name *",
  "app.personForm.middleNames": "Middle name(s)",
  "app.personForm.birthDate": "Birth date *",
  "app.personForm.birthTimePlace": "Birth time & place",
  "app.personForm.birthTimePlaceNote": "(metadata only — never affects a core number)",
  "app.personForm.birthTime": "Birth time",
  "app.personForm.timePrecision": "Time precision",
  "app.personForm.precisionExact": "Exact",
  "app.personForm.precisionApproximate": "Approximate",
  "app.personForm.precisionUnknown": "Unknown",
  "app.personForm.birthPlace": "Birth place",
  "app.personForm.birthPlacePlaceholder": "e.g. Meerbusch",
  "app.personForm.countryCode": "Country code",
  "app.personForm.countryCodePlaceholder": "e.g. DE",
  "app.personForm.currentPreferred": "Current name & preferred name",
  "app.personForm.optionalNote": "(optional)",
  "app.personForm.currentFirstNames": "Current first name(s)",
  "app.personForm.currentLastName": "Current last name",
  "app.personForm.currentMiddleNames": "Current middle name(s)",
  "app.personForm.preferredName": "Preferred name",

  // New profile
  "app.peopleNew.title": "New profile",
  "app.peopleNew.description":
    "The birth name and birth date drive every core number. Everything else is optional.",
  "app.peopleNew.creating": "Creating profile…",
  "app.peopleNew.calculating": "Running calculation…",
  "app.peopleNew.submit": "Create profile & calculate",

  // Edit profile
  "app.peopleEdit.title": "Edit profile",
  "app.peopleEdit.description":
    "The birth name and birth date drive every core number. Editing them here never changes a calculation you have already run.",
  "app.peopleEdit.canonWarning":
    "Existing calculations remain unchanged. Only a new calculation you run after saving will use this updated birth data.",
  "app.peopleEdit.save": "Save changes",
  "app.peopleEdit.cancel": "Cancel",
  "app.peopleEdit.backToProfile": "Back to profile",
  "app.peopleEdit.loadErrorTitle": "Could not load profile",

  // Person detail
  "app.personDetail.eyebrow": "Profile",
  "app.personDetail.loadingProfile": "Loading profile…",
  "app.personDetail.lastAnalysis": "Last analysis",
  "app.personDetail.today": "Today",
  "app.personDetail.edit": "Edit",
  "app.personDetail.birthDataTitle": "Birth data",
  "app.personDetail.birthDataBody":
    "The date drives Life Path, Birthday, Attitude and every cycle. Time and place are stored as metadata only.",
  "app.personDetail.birthDate": "Birth date",
  "app.personDetail.birthTime": "Birth time",
  "app.personDetail.birthPlace": "Birth place",
  "app.personDetail.notRecorded": "Not recorded",
  "app.personDetail.historyTitle": "Calculation history",
  "app.personDetail.historyBody":
    "Every snapshot is permanent — editing the profile above never changes one that already exists. Pick two to compare them.",
  "app.personDetail.historyError": "Could not load calculation history.",
  "app.personDetail.noCalculations": "No calculations yet.",
  "app.personDetail.asOf": "As of",
  "app.personDetail.open": "Open",
  "app.personDetail.compareSelected": "Compare selected",
  "app.personDetail.selectTwo": "Select two snapshots to compare.",
  "app.personDetail.selectOneMore": "Select one more.",
  "app.personDetail.readyToCompare": "Ready to compare.",
  "app.personDetail.selectSnapshotAria": "Select snapshot for comparison, as of",
  "app.personDetail.deleteTitle": "Delete this profile",
  "app.personDetail.deleteBody":
    "Removes the profile and everything calculated from it. This cannot be undone.",
  "app.personDetail.deleteButton": "Delete profile",
  "app.personDetail.deleteConfirm": "Yes, delete permanently",
  "app.personDetail.deleteCancel": "Cancel",

  // Identity
  "app.identity.title": "Identity",
  "app.identity.body": "The names recorded for this profile. Only the birth name enters a calculation.",
  "app.identity.birthLabel": "Birth name",
  "app.identity.birthNote": "Every core number is computed from this name (canon-spec §5).",
  "app.identity.currentLabel": "Current name",
  "app.identity.currentNote": "Recorded as metadata — it does not change any core number in this version.",
  "app.identity.preferredLabel": "Preferred name",
  "app.identity.preferredNote": "How this person is addressed in Numra. Never used in a calculation.",
  "app.identity.usedForCore": "Used for core numbers",
  "app.identity.partial": "Partially recorded",
  "app.identity.partialNote":
    "Only the name parts stored for this profile are shown — the missing parts are not filled in from the birth name.",
  "app.identity.noExtraNames":
    "No current or preferred name is recorded for this profile. Numra shows only the names it actually holds.",
  "app.identity.recordedHistory": "Recorded history",
  "app.identity.kindBirth": "Birth",
  "app.identity.kindCurrent": "Current",
  "app.identity.kindPreferred": "Preferred",
  "app.identity.validFrom": "Valid from",
  "app.identity.recordedAt": "Recorded",

  // Today
  "app.today.title": "Today",
  "app.today.subtitle": "Where this date falls in a personal cycle — recomputed live, never guessed.",
  "app.today.whoseDay": "Whose day?",
  "app.today.loadingPeople": "Loading your people…",
  "app.today.reading": "Reading today…",
  "app.today.timingErrorTitle": "Could not read today's timing",
  "app.today.unreadableTiming": "Unreadable timing",
  "app.today.emptyTitle": "No profiles yet",
  "app.today.emptyBody":
    "Today needs a birth date to work from. Create a profile and this page becomes your daily view.",
  "app.today.masterNumber": "Master Number",
  "app.today.derivedShow": "How were these derived?",
  "app.today.derivedHide": "Hide how these were derived",
  "app.today.footnote":
    "These values are recomputed on request for today's date and are not stored as a calculation snapshot. To pin a dated, hashed record, run a calculation from the person's profile instead.",
  "app.today.reflection": "Reflection",
  "app.today.composing": "Composing reflection…",
  "app.today.reflectionErrorTitle": "Could not load the reflection",
  "app.today.reflectionFootnotePrefix":
    "Reflective and symbolic, sourced from Numra's knowledge package — not a prediction and not written by a language model. Recomputed for",
  "app.today.reflectionFootnoteSuffix": "not stored.",

  // Reports (list)
  "app.reports.title": "Reports",
  "app.reports.subtitle": "Every long-form reading you have generated — server-side, visible from any device.",
  "app.reports.filterAll": "All",
  "app.reports.filterPending": "In progress",
  "app.reports.filterComplete": "Complete",
  "app.reports.filterFailed": "Failed",
  "app.reports.filterByStatus": "Filter by status",
  "app.reports.filterByPerson": "Filter by person",
  "app.reports.allPeople": "All people",
  "app.reports.generated": "Generated",
  "app.reports.started": "Started",
  "app.reports.words": "words",
  "app.reports.openCalculation": "Calculation",
  "app.reports.open": "Open",
  "app.reports.loading": "Loading reports…",
  "app.reports.errorTitle": "Could not load your reports",
  "app.reports.emptyTitle": "No reports yet",
  "app.reports.emptyBody": "Generate a report from any calculation's analysis page to see it here.",

  // Report detail
  "app.reportDetail.back": "Back to the calculation",
  "app.reportDetail.loading": "Loading report…",
  "app.reportDetail.errorTitle": "Could not load this report",
  "app.reportDetail.unreadableTitle": "Unreadable report",

  // Analysis
  "app.analysis.eyebrow": "Calculation",
  "app.analysis.asOf": "As of",
  "app.analysis.writtenReport": "Written report",
  "app.analysis.immutableNote":
    "This snapshot is immutable. Re-running the same person on the same as-of date reproduces the identical hash above — every value on this page traces back to its inputs, step by step.",
  "app.analysis.tabCore": "Core Numbers",
  "app.analysis.tabInspector": "Calculation Inspector",
  "app.analysis.tabCycles": "Cycles & Timing",
  "app.analysis.tabsAria": "Analysis views",
  "app.analysis.loading": "Loading calculation…",
  "app.analysis.errorTitle": "Could not load this analysis",
  "app.analysis.unreadableTitle": "Unreadable calculation",

  // Snapshot comparison
  "app.compare.back": "Back to profile",
  "app.compare.title": "Snapshot comparison",
  "app.compare.loading": "Loading both snapshots…",
  "app.compare.loadingOne": "Loading comparison…",
  "app.compare.errorTitle": "Could not load both snapshots",
  "app.compare.unreadableTitle": "Unreadable snapshot",
  "app.compare.differentPeopleTitle": "These snapshots belong to different people",
  "app.compare.differentPeopleBody":
    "A comparison only makes sense between two calculations of the same person.",
  "app.compare.chooseTitle": "Choose two snapshots",
  "app.compare.chooseBody":
    "Open a person's profile, select two calculations from their history, and choose \"Compare selected\".",
  "app.compare.factualNote":
    "This is a factual diff, nothing more: it shows which values differ between the two snapshots and stops there. Numra does not compute a growth score, an improvement percentage, or any judgment of which snapshot is \"better\".",
  "app.compare.stableTitle": "Stable core numbers",
  "app.compare.stableChanged":
    "These differ between the two snapshots — likely because the person's name or birth data was edited in between.",
  "app.compare.stableUnchanged":
    "Identical in both snapshots, as expected when the underlying identity has not changed.",
  "app.compare.timingTitle": "Date-dependent timing",
  "app.compare.timingBody": "Expected to differ — each snapshot was computed for a different as-of date.",
  "app.compare.metricColumn": "Metric",

  // Relationships
  "app.relationships.title": "Relationships",
  "app.relationships.subtitle": "Compare two calculated profiles, metric by metric.",
  "app.relationships.formTitle": "Compare two profiles",
  "app.relationships.formBody":
    "Numra compares each person's latest calculation. If someone has no calculation yet, run one first.",
  "app.relationships.personA": "Person A",
  "app.relationships.personB": "Person B",
  "app.relationships.compare": "Compare",
  "app.relationships.chooseDifferent": "Choose two different people.",
  "app.relationships.noCalcYet": "That profile has no calculation yet.",
  "app.relationships.openProfileToRun": "Open profile to run a calculation",
  "app.relationships.recent": "Recent comparisons",
  "app.relationships.loadingProfiles": "Loading profiles…",
  "app.relationships.loadingComparisons": "Loading comparisons…",
  "app.relationships.comparisonsErrorTitle": "Could not load your comparisons",
  "app.relationships.emptyTitle": "Add a second profile to compare",
  "app.relationships.emptyBody":
    "Numra needs at least two people, each with a calculation, before it can compare them.",
  "app.relationships.open": "Open",

  // Relationship detail
  "app.relationshipDetail.all": "All comparisons",
  "app.relationshipDetail.eyebrow": "Comparison",
  "app.relationshipDetail.created": "Created",
  "app.relationshipDetail.loading": "Loading comparison…",
  "app.relationshipDetail.errorTitle": "Could not load this comparison",
  "app.relationshipDetail.noScoreNote":
    "Numra compares two profiles metric by metric and stops there. It does not compute a compatibility percentage, a match count, or any other combined score — there is no defensible deterministic method for one, so inventing a number would undermine everything else on this page.",
  "app.relationshipDetail.coreTitle": "Core numbers",
  "app.relationshipDetail.coreBody":
    "Derived from each person's birth name and birth date. These do not change.",
  "app.relationshipDetail.timingTitle": "Timing",
  "app.relationshipDetail.timingBody":
    "Derived from each calculation's as-of date — meaningful to compare only when both calculations share that date.",
  "app.relationshipDetail.sameValue": "Same value",
  "app.relationshipDetail.differentValues": "Different values",
  "app.relationshipDetail.noMetrics": "This comparison did not include any of the expected metrics.",
  "app.relationshipDetail.notesTitle": "Relationship notes",
  "app.relationshipDetail.notesBody":
    "How each person's number tends to show up in relationships, side by side — sourced from Numra's knowledge package, not generated per comparison.",
  "app.relationshipDetail.sameNumber": "Same number",
  "app.relationshipDetail.calcA": "Calculation A",
  "app.relationshipDetail.calcB": "Calculation B",

  // Settings: privacy
  "app.privacy.title": "Privacy & data",
  "app.privacy.subtitle": "What Numra stores, what it never computes, and how to remove all of it.",
  "app.privacy.storedTitle": "What is stored on the server",
  "app.privacy.storedProfiles": "Person profiles",
  "app.privacy.storedProfilesBody":
    "— the birth name, birth date, and optional birth time / birth place / current name you enter when creating a profile.",
  "app.privacy.storedCalculations": "Calculations",
  "app.privacy.storedCalculationsBody":
    "— immutable, deterministic snapshots of the canonical result at a given as-of date, including the full calculation trace and a hash of the inputs and result.",
  "app.privacy.storedRelationships": "Relationship comparisons",
  "app.privacy.storedRelationshipsBody":
    "— the two calculation IDs you compared and the resulting per-metric comparison.",
  "app.privacy.storedReports": "Reports and exports",
  "app.privacy.storedReportsBody":
    "— the text of any long-form report you generate, and any PDF rendered from it (stored as a file on the server until you delete it).",
  "app.privacy.storedAccount": "Your account",
  "app.privacy.storedAccountBody":
    "— email address and session credentials, used only to authenticate you.",
  "app.privacy.neverTitle": "What this app never computes or stores",
  "app.privacy.neverScore": "No compatibility percentage is ever calculated for a relationship comparison.",
  "app.privacy.neverDiagnosis": "No diagnosis or medical/psychological language is generated.",
  "app.privacy.neverBirthTime":
    "Birth time and birth place are stored as metadata only — they never influence a core number in this version.",
  "app.privacy.deleteOneTitle": "Deleting a single profile",
  "app.privacy.deleteOneBody":
    "Any individual profile can be deleted from that profile's own page, which also removes what was calculated from it.",

  // Settings: security
  "app.security.title": "Security",
  "app.security.body": "Change your password and manage where you're signed in.",
  "app.security.currentPassword": "Current password",
  "app.security.newPassword": "New password",
  "app.security.confirmPassword": "Confirm new password",
  "app.security.mismatch": "The new passwords do not match.",
  "app.security.changed": "Password changed. Other devices have been signed out; this one stays signed in.",
  "app.security.changeButton": "Change password",
  "app.security.activeSessions": "Active sessions",
  "app.security.loadingSessions": "Loading sessions…",
  "app.security.sessionsErrorTitle": "Could not load sessions",
  "app.security.thisDevice": "This device",
  "app.security.otherDevice": "Another device",
  "app.security.signedIn": "Signed in",
  "app.security.current": "Current",
  "app.security.logoutOthers": "Log out other devices",
  "app.security.othersLoggedOut": "Other devices have been signed out.",

  // Settings: system info
  "app.systemInfo.title": "System info",
  "app.systemInfo.body": "What this Numra instance is running.",
  "app.systemInfo.environment": "Environment",
  "app.systemInfo.timezone": "App timezone",
  "app.systemInfo.sessionLifetime": "Session lifetime",
  "app.systemInfo.selfSignup": "Self-signup",
  "app.systemInfo.llmProvider": "LLM provider",
  "app.systemInfo.pdfExport": "PDF export",
  "app.systemInfo.enabled": "enabled",
  "app.systemInfo.disabled": "disabled",
  "app.systemInfo.errorTitle": "Could not load system info",

  // Delete account
  "app.deleteAccount.title": "Delete my account",
  "app.deleteAccount.body":
    "Permanently erases everything Numra stores for you. There is no undo, no export step afterwards and no grace period.",
  "app.deleteAccount.listIntro": "This deletes, permanently:",
  "app.deleteAccount.itemProfiles": "every person profile you have created",
  "app.deleteAccount.itemCalculations": "every calculation and its stored trace",
  "app.deleteAccount.itemRelationships": "every relationship comparison",
  "app.deleteAccount.itemReports": "every generated report",
  "app.deleteAccount.itemExports": "every exported PDF, including the files on the server",
  "app.deleteAccount.itemAccount": "your account and its login credentials",
  "app.deleteAccount.exportHint":
    "If you want a copy of a report, export its PDF before continuing — exported files are deleted from disk too.",
  "app.deleteAccount.confirmLabel": "Confirm with your password",
  "app.deleteAccount.wrongPassword": "That password did not match. Nothing has been deleted.",
  "app.deleteAccount.submit": "Delete everything permanently",
  "app.deleteAccount.submitting": "Deleting everything…",
  "app.deleteAccount.cancel": "Cancel",

  // Report launcher & export & progress
  "app.reportLauncher.title": "Written report",
  "app.reportLauncher.body":
    "A long-form reading written from this exact calculation. Every number it states is verified against the canonical profile before the report is assembled.",
  "app.reportLauncher.length": "Report length",
  "app.reportLauncher.generate": "Generate report",
  "app.reportLauncher.starting": "Starting generation…",
  "app.reportLauncher.previous": "Reports started from this calculation",
  "app.reportLauncher.startedAt": "Started",
  "app.reportLauncher.open": "Open",
  "app.export.title": "Export",
  "app.export.body":
    "Render this report as a PDF. The file is produced from the report exactly as it is stored — exporting never regenerates or changes the text.",
  "app.export.button": "Export PDF",
  "app.export.rendering": "Rendering PDF…",
  "app.export.renderingHint": "The PDF is rendered on the server; this usually takes a few seconds.",
  "app.export.failed": "The PDF could not be rendered. You can try the export again.",
  "app.export.available": "Available files",
  "app.export.download": "Download",
  "app.export.none": "No PDF has been rendered for this report yet.",
  "app.export.earlierFailedBadge": "Earlier attempt failed",
  "app.export.earlierFailedBody": "A previous export of this report did not complete.",
  "app.reportProgress.writing": "Writing your report",
  "app.reportProgress.aria": "Report generation progress",
  "app.reportProgress.contacting": "Contacting the generation queue…",
  "app.reportProgress.retriedPrefix": "Attempt",
  "app.reportProgress.retriedSuffix": "— the queue retried after a recoverable error.",
  "app.reportProgress.checkNote":
    "Every number that appears in the finished text is checked against this calculation's canonical profile before the report is assembled. Nothing is shown here until that check has passed.",
  "app.reportFailed.title": "Report generation failed",
  "app.reportFailed.reportedBy": "reported by the generation job",
  "app.reportFailed.afterAttempts": "attempts",
  "app.reportFailed.after": "after",
  "app.reportFailed.untouched":
    "Your calculation is untouched — it is immutable and was never modified by this run. Starting again queues a completely new report from the same calculation.",
  "app.reportFailed.retry": "Generate a new report",
};
