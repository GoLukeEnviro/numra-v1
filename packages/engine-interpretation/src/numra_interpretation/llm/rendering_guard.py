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
import unicodedata

from numra_interpretation.llm.validator import KNOWN_FACT_IDS

__all__ = [
    "PROMPT_SCAFFOLDING_MARKERS",
    "LENIENT_UNRESOLVED_TOKEN_PATTERN",
    "UNRESOLVED_TOKEN_PATTERN",
    "canonical_for_check",
    "contains_prompt_scaffolding",
    "find_unresolved_template_token",
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


def contains_prompt_scaffolding(text: str) -> bool:
    """True when ``text`` carries request scaffolding instead of rendered prose.

    Matches a marker **anywhere** in the text, not only at the start of a line. Two
    shapes reach product output and both are the same defect:

    * a provider that *echoes* its request composes one line per request field, so the
      marker starts a line (``MockLLMProvider`` by design, any future provider by
      accident);
    * a *generative* model does not echo — it copies a block's label into the middle of
      its own sentence (``"... die durch [profile_fact:a:expression] gepraegt ist ..."``,
      captured on the audit stack on 2026-09-20).

    An earlier line-anchored version of this check let the second shape through, which
    is how prompt scaffolding ended up rendered in a relationship analysis. The markers
    are bracketed and role-prefixed, so ordinary prose cannot collide with them.
    """
    return any(marker in text for marker in PROMPT_SCAFFOLDING_MARKERS)


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


#: Latin look-alikes that NFKC does not fold (it only folds compatibility forms such as
#: full-width brackets and colons). Used for *checking* only, see `canonical_for_check`.
_CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ѕ": "s",
        "ј": "j",
        "ԁ": "d",
        "ӏ": "l",
        "к": "k",
        "т": "t",
        "м": "m",
        "ԝ": "w",
        "ο": "o",
        "ν": "v",
        "ι": "i",
        "α": "a",
        "ε": "e",
        "ρ": "p",
        "κ": "k",
        "τ": "t",
        "υ": "u",
    }
)

#: Unicode categories dropped from the check form: format characters and all combining marks.
_IGNORED_CATEGORIES = frozenset({"Cf", "Mn", "Mc", "Me"})


def canonical_for_check(text: str) -> str:
    """The form of ``text`` every token check looks at: NFKD (full-width
    ``［profile_fact：a:x］`` -> ``[profile_fact:a:x]``, ``é`` -> ``e`` + U+0301),
    case-folded (so upper-case Cyrillic/Greek look-alikes such as ``Ѕ`` or ``К`` reach the
    lower-case `_CONFUSABLES` table), then invisible format characters (Cf) and combining
    marks (Mn/Mc/Me; ``[prof\u0301ile_fact:a]``, U+034F inside a marker) removed and the
    common Cyrillic/Greek look-alikes folded to Latin. Only ever used to *detect*; the text
    that is stored is never rewritten with it, so ordinary German (umlauts, ß, typographic
    quotes, accents in names) is unaffected apart from being checked with ``ä`` read as
    ``a``. ``casefold`` can itself emit combining characters (``İ``), hence the second
    NFKD before the filter."""
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFKD", text).casefold())
    visible = "".join(ch for ch in folded if unicodedata.category(ch) not in _IGNORED_CATEGORIES)
    return visible.translate(_CONFUSABLES)


def _short_label_alternatives() -> str:
    """Regex alternatives for the shortened block label ``[a:<id>]`` / ``[b:<id>]``
    (audit 2026-10-09). Narrow on purpose -- the person letter must be followed by a
    *known* fact id (`validator.KNOWN_FACT_IDS`, pinned to the profile indices by a
    test), so dialogue in brackets (``[A: Ich bin müde]``, ``[a: Nähe]``) and links
    or checkboxes stay ordinary prose:

    * a known id followed by ``]``, the end, or more identifier characters (a known id
      extended by ``_x`` is still a label, fail-closed);
    * any unspaced snake_case label ``[a:some_thing]`` -- an unknown or misspelled id of
      the same shape is still a token (prose never contains an underscore);
    * a response cut off inside the label: ``[a:`` and any prefix of a known id at the
      very end of the text.
    """
    ids = sorted(KNOWN_FACT_IDS, key=len, reverse=True)
    known = "|".join(re.escape(i) for i in ids)
    prefixes = sorted({i[:n] for i in ids for n in range(1, len(i) + 1)}, key=len, reverse=True)
    cut = "|".join(re.escape(p) for p in prefixes)
    return (
        rf"\[\s*[ab]\s*:\s*(?:{known})(?=\s*\]|\s*\Z|[0-9_])"
        r"|\[[ab]:[a-z][a-z0-9]*_[a-z0-9_]+\]"
        rf"|\[\s*[ab]\s*:\s*(?:{cut})?\s*\Z"
    )


#: Alternatives shared by the strict and the lenient pattern (matched on
#: `canonical_for_check` output, so written for the folded form):
#:
#: * ``[metric:`` / ``<special:`` (wrong brackets around a placeholder body);
#: * ``%(name)s`` and ``<partner_a>``;
#: * a prompt-framing label in a spelling the exact-match guard does not cover;
#: * the shortened block label, see `_short_label_alternatives`.
_COMMON_TOKEN_ALTERNATIVES = (
    r"[\[<]\s*(?:metric|special)\s*:"
    r"|%\(\w+\)s"
    r"|<\s*[a-z]+_[a-z_]+\s*>"
    r"|\[\s*(?:profile_fact|knowledge|system|instruction_supplement"
    r"|untrusted_user_content|user_instructions)\b"
    "|" + _short_label_alternatives()
)

#: Strict variant: **any** brace is template syntax (``{{metric:x}}``, a truncated
#: ``{{metric:matur``, ``{partner_a}``). Kept for relationship/shadow analyses, whose
#: leftover check always rejected every brace; their prose has no use for one.
UNRESOLVED_TOKEN_PATTERN = re.compile(r"[{}]|" + _COMMON_TOKEN_ALTERNATIVES, re.IGNORECASE)

#: Lenient variant for free-form product text (report sections, Copilot replies), where
#: an isolated brace is legitimate (``{1,2}``, a set ``{ 3 }``, code or maths in an
#: answer) and rejecting it would fail a whole report or turn: only concrete placeholder
#: shapes count -- ``{{`` / ``}}`` (also unbalanced, i.e. a cut-off ``{{metric:matur``),
#: ``{identifier}`` with optional ``:``/``.`` parts, and an opening ``{metric`` /
#: ``{special`` that was never closed.
LENIENT_UNRESOLVED_TOKEN_PATTERN = re.compile(
    r"\{\{|\}\}"
    r"|\{\s*[a-z_][a-z0-9_]*(?:\s*[:.]\s*[a-z0-9_]+)*\s*\}"
    r"|\{\s*(?:metric|special)\b"
    "|" + _COMMON_TOKEN_ALTERNATIVES,
    re.IGNORECASE,
)


def find_unresolved_template_token(text: str, *, strict_braces: bool = True) -> str | None:
    """The first unresolved internal template token in ``text`` (prompt scaffolding or
    any `UNRESOLVED_TOKEN_PATTERN` form), or ``None`` when the text is clean.

    The single check every pipeline runs over text that is about to become a result
    (relationship/shadow statements, report sections and summaries, Copilot replies), so
    "a finished text carries no internal token" is stated once. Both the raw and the
    `canonical_for_check` form are inspected; the return value is the offending
    *token*, never surrounding prose, so it is safe to put into a log line.

    ``strict_braces=True`` (default, analyses) rejects any ``{`` or ``}``;
    ``strict_braces=False`` (report, Copilot) only rejects concrete placeholder shapes,
    see `LENIENT_UNRESOLVED_TOKEN_PATTERN`. Every other form is identical."""
    checked = canonical_for_check(text)
    for marker in PROMPT_SCAFFOLDING_MARKERS:
        if marker in text or marker in checked:
            return marker
    pattern = UNRESOLVED_TOKEN_PATTERN if strict_braces else LENIENT_UNRESOLVED_TOKEN_PATTERN
    match = pattern.search(checked)
    return match.group(0) if match else None
