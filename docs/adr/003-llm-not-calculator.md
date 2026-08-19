# ADR 003 — The LLM Renders, It Never Calculates

## Status

Accepted.

## Context

A language model asked to "explain someone's Life Path" will, if given free rein,
sometimes recompute or "helpfully correct" a number it was told, especially across a
long multi-section generation where earlier context has scrolled out of the effective
window. That is exactly the failure mode this project cannot tolerate: a report whose
prose disagrees with the canonical numbers it's supposed to be describing.

## Decision

Structural containment at every layer, not just a system-prompt instruction:

- `GenerationRequest`/`StructuredGenerationRequest` (`numra_interpretation.llm.types`)
  separate `system_instructions`, `context_blocks` (role-tagged, developer-assembled),
  and `user_instructions` into distinct fields — never one concatenated string, closing
  the classic prompt-injection vector where user text is mistaken for an instruction.
- Numeric facts are cited as `{{metric:ID}}` placeholders, not typed digits. The
  pipeline's renderer (`report/pipeline.py::_resolve_placeholders`) is the *only* code
  path allowed to turn a placeholder into a display value, and it always reads that
  value from the `CanonicalProfile` — never from anything the LLM said.
- Every `NumericClaim` an LLM response makes is checked against the profile
  (`llm/validator.py::validate_numeric_claims`) before acceptance; a mismatch raises
  `InvalidReportSection`, triggering exactly one repair attempt and then a hard failure
  — never a silent correction or a best-guess average.
- The Report Linter's `PlaceholderResolution`/`MetricReferenceIntegrity` checks run
  again on the *assembled* report as a final guard, not just per-section.

## Consequences

- Swapping providers (mock ↔ Ollama Cloud ↔ a future provider) never changes the
  numeric-integrity guarantee, because it's enforced outside the provider, not inside
  a specific model's prompt-following behavior.
- A provider that ignores instructions and states a wrong number produces a caught
  validation failure, not a published wrong report.
- The system prompt's "do not calculate" instruction (canon-spec-adjacent, in
  `pipeline.py::_SYSTEM_INSTRUCTIONS`) is defense-in-depth, not the actual safety
  mechanism — the mechanism is the placeholder/claim validation, which holds even if a
  future model completely ignores the instruction text.
