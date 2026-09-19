"""The one rendering boundary every LLM-backed pipeline passes through.

Every rendered string that reaches a user — relationship analysis, shadow
dynamics, copilot replies, report sections — is produced by a provider and then
either persisted or sent to the client. A provider that echoes its own request
back (the deterministic `MockLLMProvider` does this by design; any future
provider could do it by accident) must never have that scaffolding rendered as
product output.

PR #98 patched exactly one call site (the Copilot reply) with an ad-hoc string
replacement, which left the sibling pipelines leaking the same class of data.
`contains_prompt_scaffolding` is the shared detector those pipelines now use, so
the invariant is stated once instead of drifting across four call sites.

Callers raise their own error type on a match (each pipeline already has a
repair-then-fail path). Failing closed — rather than silently rewriting the
text — is deliberate: scaffolding means the provider did not render anything,
and a silent rewrite hides exactly the defect that stayed invisible until now.
The mock provider paths keep their own deterministic substitution on top, since
`MockLLMProvider` echoes by design and is not a failure.
"""

from __future__ import annotations

import re

__all__ = [
    "PROMPT_SCAFFOLDING_MARKERS",
    "contains_prompt_scaffolding",
    "grounding_prose",
]

#: The framing
#: `numra_interpretation.llm.mock_provider.MockLLMProvider._compose_text` emits for
#: each request field and context-block role: ``[system] ...`` for the system
#: instructions, ``[<role>:<label>] ...`` per block, and ``[user_instructions] ...``
#: for the end-user instruction field. A real provider receives the same request
#: shape (see `numra_interpretation.llm.ollama_provider`), so these markers identify
#: prompt scaffolding regardless of which provider produced the text.
PROMPT_SCAFFOLDING_MARKERS: tuple[str, ...] = (
    "[system]",
    "[profile_fact:",
    "[knowledge:",
    "[instruction_supplement:",
    "[untrusted_user_content:",
    "[user_instructions]",
)

#: Anchored to the start of the text or of a line, which is exactly how the
#: scaffolding is composed — so ordinary prose that merely mentions a bracketed
#: word is not rejected.
_SCAFFOLDING_PATTERN = re.compile(
    r"(?m)^[ \t]*(?:" + "|".join(re.escape(marker) for marker in PROMPT_SCAFFOLDING_MARKERS) + r")"
)


def contains_prompt_scaffolding(text: str) -> bool:
    """True when ``text`` carries request scaffolding instead of rendered prose."""
    return bool(_SCAFFOLDING_PATTERN.search(text))


def grounding_prose(*values: str) -> str:
    """The deterministic, scaffolding-free stand-in used wherever
    `MockLLMProvider` (a provider that echoes its request by design, not a failure)
    would otherwise hand back its own prompt framing.

    Composed from values the pipeline already computed — knowledge text it selected
    and canonical metric ids — so the result stays grounded, deterministic, and
    free of any request field (system instructions, block contents, metadata).
    Numeric facts stay as ``{{metric:ID}}`` placeholders; the caller's existing
    resolver turns them into the canonical display values, exactly as it does for a
    real provider's text.
    """
    return " ".join(value.strip() for value in values if value and value.strip())
