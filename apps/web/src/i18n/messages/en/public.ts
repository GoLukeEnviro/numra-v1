import type { dePublic } from "@/i18n/messages/de/public";

/** English counterpart of `de/public.ts`; typed against its key set so `tsc` enforces parity. */
export const enPublic: Record<keyof typeof dePublic, string> = {
  // Landing page
  "public.landing.navSignIn": "Sign in",
  "public.landing.navCreateAccount": "Create account",
  "public.landing.heroEyebrow": "Auditable numerology",
  "public.landing.heroTitle": "Numerology without guessing.",
  "public.landing.heroSubtitle":
    "A deterministic engine computes every number from a documented formula. Language only explains what has already been calculated — nothing is estimated, nothing invented.",
  "public.landing.heroCtaCreate": "Create account",
  "public.landing.heroCtaSignIn": "Sign in",
  "public.landing.signedInHint": "You are already signed in.",
  "public.landing.toDashboard": "Go to dashboard",
  "public.landing.howTitle": "How it works",
  "public.landing.howStep1Title": "Profile data",
  "public.landing.howStep1Body":
    "A birth name and birth date are all it takes. Everything else is optional metadata.",
  "public.landing.howStep2Title": "Deterministic calculation",
  "public.landing.howStep2Body":
    "The engine computes every value from a documented formula. Same input, same result, same hash — reproducible at any time.",
  "public.landing.howStep3Title": "Traceable interpretation",
  "public.landing.howStep3Body":
    "Every number carries its derivation, step by step. Text explains the values; it never produces one.",
  "public.landing.featuresTitle": "Features",
  "public.landing.featureProfileTitle": "Personal profile",
  "public.landing.featureProfileBody": "Birth name, birth date and name history in one place.",
  "public.landing.featureCoreTitle": "Core numbers",
  "public.landing.featureCoreBody": "Life Path, Expression and more — each with its full derivation.",
  "public.landing.featureTodayTitle": "Today & timing",
  "public.landing.featureTodayBody": "Where this date falls in a personal cycle — computed live.",
  "public.landing.featureRelationshipsTitle": "Relationships",
  "public.landing.featureRelationshipsBody": "Two profiles compared metric by metric — never a score.",
  "public.landing.featureReportsTitle": "Reports",
  "public.landing.featureReportsBody": "Long-form readings, every number checked against the calculation.",
  "public.landing.featureHistoryTitle": "History & comparisons",
  "public.landing.featureHistoryBody": "Immutable snapshots that can be compared factually.",
  "public.landing.transparencyTitle": "Transparency",
  "public.landing.transparencyBody":
    "All numbers come from the deterministic engine. The language model only explains them — it never computes a value and never invents one.",
  "public.landing.privacyTitle": "Privacy",
  "public.landing.privacyBody":
    "What you enter is what is stored: profiles, calculations, comparisons, reports and your account. Every profile and the entire account can be deleted completely at any time.",
  "public.landing.disclaimerTitle": "Notice",
  "public.landing.disclaimerBody":
    "NUMRA is a symbolic numerological interpretation tool. It provides no medical, legal, financial or scientific advice.",
  "public.landing.finalCtaTitle": "Evidence instead of claims.",
  "public.landing.finalCtaBody": "Create an account and verify every number yourself.",
  "public.landing.footerPrivacy": "Privacy",

  // Login
  "public.login.brandIntro":
    "An auditable numerology platform. A deterministic engine does the arithmetic; language only ever explains what it already produced.",
  "public.login.promise1": "Every number carries the trace that produced it.",
  "public.login.promise2": "The same inputs always reproduce the same hash.",
  "public.login.promise3": "No compatibility score is ever invented.",
  "public.login.subtitle": "Sign in to your account",
  "public.login.email": "Email",
  "public.login.password": "Password",
  "public.login.submit": "Sign in",
  "public.login.noAccount": "No account yet?",
  "public.login.createAccount": "Create account",

  // Registration
  "public.register.title": "Create account",
  "public.register.subtitle": "One account, all your calculations — verifiable from any device.",
  "public.register.email": "Email",
  "public.register.password": "Password",
  "public.register.passwordConfirm": "Confirm password",
  "public.register.passwordHint": "At least 12 characters.",
  "public.register.submit": "Create account",
  "public.register.haveAccount": "Already have an account?",
  "public.register.toLogin": "Go to login",
  "public.register.checkingConfig": "Preparing registration…",
  "public.register.closedTitle": "Registration is currently closed.",
  "public.register.closedBody":
    "This instance is not accepting new accounts right now. If you already have one, sign in.",
  "public.register.errorMismatch": "The passwords do not match.",
  "public.register.errorTooShort": "The password must be at least 12 characters long.",
  "public.register.errorDuplicate": "An account already exists for this email address.",
  "public.register.errorDisabled": "Registration is currently disabled.",
  "public.register.errorRateLimited": "Too many attempts. Please wait a moment and try again.",
  "public.register.errorServer": "The server could not complete the registration. Please try again later.",
  "public.register.errorValidation": "The server did not accept the input. Please check email and password.",

  // Onboarding
  "public.onboarding.stepLabel": "Step",
  "public.onboarding.of": "of",
  "public.onboarding.welcomeTitle": "Welcome to Numra",
  "public.onboarding.welcomeBody":
    "Three short steps create your first profile and run your first deterministic calculation. Everything produced along the way is traceable and can be deleted at any time.",
  "public.onboarding.start": "Create first profile",
  "public.onboarding.profileTitle": "First profile",
  "public.onboarding.profileBody":
    "The birth name and birth date drive every core number. Everything else is optional.",
  "public.onboarding.calcTitle": "First calculation",
  "public.onboarding.calcBody":
    "The profile has been created. Now run the first calculation — it produces an immutable, hashed snapshot.",
  "public.onboarding.runCalculation": "Run calculation",
  "public.onboarding.calcRunning": "Calculating…",
  "public.onboarding.doneTitle": "Done",
  "public.onboarding.doneBody":
    "Your first profile and its calculation are in place. The analysis shows every number with its full derivation.",
  "public.onboarding.openAnalysis": "Open analysis",
  "public.onboarding.existingTitle": "You are all set",
  "public.onboarding.existingBody":
    "At least one profile already exists for this account — onboarding is not needed.",
  "public.onboarding.creating": "Creating profile…",
};
