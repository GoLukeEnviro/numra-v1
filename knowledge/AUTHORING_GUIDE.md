# Knowledge Authoring Guide

Wave 3 Schritt 4: a short, binding style contract for anyone writing or migrating
`knowledge/**/*.yaml` content, so the numbers 1-9/11/22/33 and the four karmic debts
migrated in Wave 3 Schritt 2-3 and any greenfield content written after them (Schritt
5: `relationships`, `work_and_creation`, `shadow-interaction/rules.yaml`,
`relationship-frames/*.yaml`) read as one voice instead of two. This does not invent
new rules — every rule below already exists as enforced code (`report/linter.py`,
`report/evidence_linter.py`) or as canon (`specs/canon-spec.md`); this document just
states them once, up front, for a human author instead of leaving them to be
discovered as a lint failure.

## Tone

Hedged, never asserted. Every sentence about a number's meaning is a *reading a
person may recognize*, not a fact about them. The migrated content (de-v3.json)
already does this — keep matching it:

- "Die Symbolik kann ... einladen/anregen/ermutigen" — never "Du bist ...".
- Pair every `constructive_expression` with a `shadow_expression`: no purely
  flattering reading without its own tension.
- `counter_hypotheses` are not optional decoration — every long-form entry gets at
  least one alternative, non-numerological explanation for the same observed
  pattern (see any existing `numbers/*.yaml` for the shape).
- No second-person diagnosis ("Du hast Angst vor ..."). Reflection prompts ask
  open questions ("Wo erlebst du ...?"), they don't tell the reader what they feel.

## Forbidden language

Identical to the patterns actually enforced in code — do not improvise new
forbidden words; if a pattern is missing here that should be caught, add it to the
linter, not just to this list:

- `report/linter.py` `_UNSUPPORTED_CLAIM_PATTERNS`: "wissenschaftlich
  bewiesen/belegt", "medizinisch(e) diagnos...", "garantiert...", "heilt",
  "psychiatrisch... diagnos...".
- `report/evidence_linter.py` `_CAUSAL_PATTERNS`: "verursach...", "führt zu",
  "bewirk...", "sorgt für" — a symbolic reading is never a cause.

## `claim_class`

Every long-form entry sets `claim_class: "traditional_claim"` — traditional
numerological meaning, explicitly not an empirical claim. NUMRA v1 does not yet
define other classes formally (`numerology-analyst-agent`, the predecessor project,
has a six-class taxonomy — `input_fact`, `calculation_fact`, `traditional_claim`,
`interpretive_hypothesis`, `empirical_evidence`, `practical_suggestion` — but only
`traditional_claim` has a home in this repo's schema so far). Don't invent a new
value; if content genuinely doesn't fit `traditional_claim`, raise it as a schema
question rather than picking a class ad hoc.

## Master numbers vs. compounds

Per `specs/canon-spec.md` §1: only 11, 22, 33 are Master Numbers. `44`, `55`, `66`,
`77`, `88`, `99` reduce further (`44 → 8`, display `"44/8"`, `master_number = null`)
and are compounds, not masters — never write "Meisterzahl 44" or describe a
compound's constructive/shadow expression the way a master's is described (no
`uncertainty` disclaimer about "Meisterzahlen" on a compound entry; that disclaimer
is master-specific).

## Karmic debt scope

Only the canon allowlist gets karmic-debt content: `13/4`, `14/5`, `16/7`, `19/1`
(`knowledge/karmic-debts/*.yaml`, matching `packages/engine-numerology`'s
`KARMIC_DEBT` flag logic). Never write karmic-debt framing into a number or
compound entry outside that allowlist — a Pinnacle landing on `13/4` is a plain
compound reduction there, not an automatic karmic-debt flag (see
`test_compose_section_includes_karmic_debt_text_when_flagged` /
`test_compose_section_without_karmic_debt_flag_has_no_karmic_text` in
`test_composer.py` for the boundary this protects).

## Long-form vs. short list

Long-form fields (`constructive_expression`, `shadow_expression`,
`development_theme`, `practical_suggestions`, `counter_hypotheses`,
`reflection_prompts`) are the canonical deutungstexte and win over the short label
lists (`core_themes`, `strengths`, `shadows`, `development`, `cautions`) once
present — `composer.py`'s `_core_shadow_sentences`/`_karmic_sentence` already
implement this preference. Never edit a short list to match new long-form prose by
hand: leave the short lists as an independent, terse index/chip layer. If both
exist for the same entry, they're allowed to overlap in theme without repeating
each other's exact wording.
