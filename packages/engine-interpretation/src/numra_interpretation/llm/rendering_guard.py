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

Template grammar
----------------
What this module treats as an internal token is derived from what the repository's
prompts, `MockLLMProvider` and the pipelines actually emit -- not from a general idea of
"template syntax" (documented for operators in
``docs/engineering/template-token-grammar.md``):

* **block label** ``[ROLE:LABEL]`` with ROLE one of ``profile_fact``, ``knowledge``,
  ``instruction_supplement``, ``untrusted_user_content``, plus ``[system]`` and
  ``[user_instructions]`` (`PROMPT_SCAFFOLDING_MARKERS`); LABEL is ``a:<id>``/``b:<id>`` in
  relationship prompts, ``<id>`` in report prompts;
* **short label** ``[PERSON:ID]`` (PERSON ``a``/``b``, ID a snake_case fact id): the block
  label with its role dropped, as a generative model abbreviates it;
* **placeholder** ``{{metric|special:[PERSON:]ID}}``;
* **format field** ``{...}`` of ``str.format`` (``{title}`` in the report refrains,
  ``{0}``, ``{name!r}``, ``{:>10}``);
* **other leftovers** ``<partner_a>`` and ``%(name)s``.

Two modes share every form except braces and the unknown compact label:

* ``strict_braces=True`` (relationship analysis, shadow dynamics): their prompts forbid
  square brackets and their prose has no use for a brace, so **any** brace and a closed
  ``[a|b:identifier]`` of any identifier are tokens;
* ``strict_braces=False`` (report sections, Copilot replies): free-form product text where
  an isolated brace or a bracketed remark is legitimate -- only concrete placeholder shapes
  count, and the compact label only with a *known* fact id or an underscore.

Detection runs on `canonical_for_check` only. The text that is stored or returned to the
user is never normalised, case-folded or stripped; Unicode folding exists solely so that a
look-alike spelling of a token cannot hide it. Input above `MAX_CHECKED_TEXT_CHARS` is
rejected without being scanned (`OVERSIZE_TOKEN`); within the limit every step is linear.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from numra_interpretation.llm.validator import KNOWN_FACT_IDS

__all__ = [
    "MAX_CHECKED_TEXT_CHARS",
    "OVERSIZE_TOKEN",
    "PROMPT_SCAFFOLDING_MARKERS",
    "LENIENT_UNRESOLVED_TOKEN_PATTERN",
    "UNRESOLVED_TOKEN_PATTERN",
    "canonical_for_check",
    "contains_prompt_scaffolding",
    "find_unresolved_template_token",
    "find_unresolved_token_in_payload",
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


#: Longest text `find_unresolved_template_token` looks at. A report section or a Copilot reply
#: is a few thousand characters; the limit only exists so that an unbounded provider answer
#: is rejected instead of being NFKD-expanded (up to 18x) and scanned.
MAX_CHECKED_TEXT_CHARS = 200_000

#: What `find_unresolved_template_token` returns for a text above the limit.
OVERSIZE_TOKEN = "<oversize>"

_MAX_TOKEN_CHARS = 64


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
    if any(marker in text for marker in PROMPT_SCAFFOLDING_MARKERS):
        return True
    if len(text) > MAX_CHECKED_TEXT_CHARS:
        return False  # not scanned; `find_unresolved_template_token` rejects it as oversize
    checked = canonical_for_check(text)
    return any(marker in checked for marker in PROMPT_SCAFFOLDING_MARKERS)


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


#: Characters that look like a Latin letter or a token punctuation mark but that NFKD does
#: not fold. Used for *checking* only, see `canonical_for_check`. Latin letter variants that
#: carry a systematic Unicode name (stroke, hook, small capital, script g, dotless i/j) are
#: derived in `_latin_variant_confusables` instead of being listed here.
_VISUAL_CONFUSABLES: dict[str, str] = {
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
    "ѕ": "s", "ј": "j", "ԁ": "d", "ӏ": "l", "к": "k", "т": "t", "м": "m", "ԝ": "w",
    "һ": "h", "ԛ": "q", "ԍ": "g", "ѵ": "v", "ү": "y", "ѡ": "w",
    # Greek
    "ο": "o", "ν": "v", "ι": "i", "α": "a", "ε": "e", "ρ": "p", "κ": "k", "τ": "t",
    "υ": "u", "ϲ": "c", "ϳ": "j", "χ": "x",
    # Armenian
    "օ": "o", "ս": "u", "ո": "n", "հ": "h",
    # Latin letters without a systematic name
    "ɑ": "a", "ɩ": "i", "ɛ": "e", "ĸ": "k", "ɵ": "o",
    # brackets, colon, underscore
    "❴": "{", "❵": "}", "⦃": "{", "⦄": "}",
    "❲": "[", "❳": "]", "⁅": "[", "⁆": "]", "〔": "[", "〕": "]", "【": "[", "】": "]",
    "⟦": "[", "⟧": "]", "〚": "[", "〛": "]",
    "⟨": "<", "⟩": ">", "〈": "<", "〉": ">", "‹": "<", "›": ">", "❮": "<", "❯": ">",
    "꞉": ":", "ː": ":", "˸": ":", "∶": ":", "։": ":",
    "ˍ": "_",
}  # fmt: skip

#: Look-alikes that NFKD and ``casefold`` would collapse into another letter (both lunate
#: sigmas become ``σ``) and therefore have to be folded before either.
_PRE_CASEFOLD = {0x03F2: "c", 0x03F9: "c"}

#: Unicode ranges that hold the systematically named Latin letter variants (Latin-1 to IPA,
#: phonetic extensions, Latin Extended Additional/C/D/E/G). Pinned to the whole of Unicode by
#: a test that scans every named character.
_LATIN_VARIANT_RANGES = (
    range(0x00C0, 0x02B0),
    range(0x1D00, 0x1DC0),
    range(0x1E00, 0x1F00),
    range(0x2C60, 0x2C80),
    range(0xA720, 0xA800),
    range(0xAB30, 0xAB70),
    range(0x1DF00, 0x1E000),
)

#: ``LATIN SMALL LETTER O WITH STROKE``, ``LATIN SMALL LETTER SCRIPT G``, ``LATIN LETTER
#: SMALL CAPITAL A``, ``LATIN SMALL LETTER DOTLESS I``. Digraphs (``WITH SMALL LETTER``) and
#: ``WITH MIDDLE DOT`` do not name one letter and decompose under NFKD anyway.
_LATIN_VARIANT_NAME = re.compile(
    r"LATIN (?:SMALL|CAPITAL) LETTER ([A-Z]) WITH (?!SMALL LETTER|MIDDLE DOT)"
    r"|LATIN SMALL LETTER SCRIPT ([A-Z])$"
    r"|LATIN LETTER SMALL CAPITAL ([A-Z])$"
    r"|LATIN SMALL LETTER DOTLESS ([IJ])$"
)


def _latin_variant_confusables() -> dict[int, str]:
    table: dict[int, str] = {}
    for block in _LATIN_VARIANT_RANGES:
        for codepoint in block:
            match = _LATIN_VARIANT_NAME.match(unicodedata.name(chr(codepoint), ""))
            if match:
                letter = next(group for group in match.groups() if group)
                table[codepoint] = letter.lower()
    return table


_CONFUSABLES: dict[int, str] = {
    **_latin_variant_confusables(),
    **{ord(char): folded for char, folded in _VISUAL_CONFUSABLES.items()},
}

#: Categories dropped from the check form: format characters (zero-width, BiDi, tags, soft
#: hyphen), combining marks, and private-use/surrogate/unassigned code points.
_IGNORED_CATEGORIES = frozenset({"Cf", "Mn", "Mc", "Me", "Co", "Cs", "Cn"})

#: Control characters that stay (they are whitespace to the patterns); every other ``Cc``
#: is dropped.
_KEPT_CONTROLS = frozenset("\t\n\v\f\r")

#: Letters and symbols that render as nothing (Hangul fillers, Braille blank).
_BLANK_LOOKING = frozenset("ᅟᅠㅤﾠ⠀")


def canonical_for_check(text: str) -> str:
    """The form of ``text`` every token check looks at: NFKD (full-width
    ``［profile_fact：a:x］`` -> ``[profile_fact:a:x]``, ``é`` -> ``e`` + U+0301),
    case-folded (so upper-case Cyrillic/Greek look-alikes such as ``Ѕ`` or ``К`` reach the
    lower-case look-alike table), then everything that renders as nothing removed (format
    characters, combining marks, C0/C1 controls except tab/newline, private-use code
    points, Hangul fillers, Braille blank), non-ASCII decimal digits turned into ASCII
    digits, and look-alikes folded to Latin (``ɡ``, small capitals, stroked/hooked letters,
    Cyrillic/Greek/Armenian look-alikes, exotic brackets, colons and underscores).

    Only ever used to *detect*; the text that is stored is never rewritten with it, so
    ordinary German (umlauts, ß, typographic quotes, accents in names) and every other
    script is unaffected apart from being checked with ``ä`` read as ``a``. ``casefold``
    can itself emit combining characters (``İ``), hence the second NFKD before the
    filter."""
    folded = unicodedata.normalize(
        "NFKD", unicodedata.normalize("NFKD", text.translate(_PRE_CASEFOLD)).casefold()
    )
    visible: list[str] = []
    for char in folded:
        category = unicodedata.category(char)
        if category in _IGNORED_CATEGORIES or char in _BLANK_LOOKING:
            continue
        if category == "Cc":
            if char in _KEPT_CONTROLS:
                visible.append(char)
        elif category == "Nd" and char > "\x7f":
            visible.append(str(unicodedata.decimal(char)))
        else:
            visible.append(char)
    return "".join(visible).translate(_CONFUSABLES)


def _short_label_alternatives() -> str:
    """Regex alternatives for the shortened block label ``[a:<id>]`` / ``[b:<id>]``
    (audit 2026-10-09). Narrow on purpose -- the person letter must be followed by a
    *known* fact id (`validator.KNOWN_FACT_IDS`, pinned to the profile indices by a
    test), so dialogue in brackets (``[A: Ich bin müde]``, ``[a: Nähe]``) and links
    or checkboxes stay ordinary prose:

    * a known id that is not the start of a longer word (``(?![a-z])``): with or without
      the closing bracket, so ``[a:life_path und``, ``[a:life_path,`` and
      ``[a:life_path_extra]`` are labels while ``[a:life_pathology]`` is not. Known
      trade-off: bracketed dialogue that *starts with* an id word (``[a: Balance ...``)
      is read as a label;
    * any unspaced snake_case label ``[a:some_thing]`` -- an unknown or misspelled id of
      the same shape is still a token (prose never contains an underscore).

    An unknown id *without* an underscore (``[a:foo]``) is not matched here; the strict
    pattern adds it (`UNRESOLVED_TOKEN_PATTERN`).

    A response cut off inside the label is not a regex (see `_ends_in_cut_off_label`):
    every `\\s*` here is followed by a character class it cannot overlap, so no
    alternative can backtrack quadratically.
    """
    ids = sorted(KNOWN_FACT_IDS, key=len, reverse=True)
    known = "|".join(re.escape(i) for i in ids)
    return rf"\[\s*[ab]\s*:\s*(?:{known})(?![a-z])|\[[ab]:[a-z][a-z0-9]*_[a-z0-9_]+\]"


_CUT_OFF_LABEL = re.compile(r"\[\s*[ab]\s*:\s*(\S*)\s*")
_MAX_FACT_ID_LENGTH = max(len(i) for i in KNOWN_FACT_IDS)


def _ends_in_cut_off_label(checked: str) -> bool:
    """True when the text ends inside a shortened label: the last ``[`` is followed by
    ``a``/``b``, a colon, blanks and nothing but a (possibly empty) prefix of a known
    fact id -- ``... [a:``, ``... [b:soul_u``, ``... [a: ``.

    Deliberately not part of the regex: the end-of-text anchor made the former pattern
    ``\\s*(?:prefix|...)?\\s*\\Z`` quadratic in the blanks after ``[a:``. Only the last
    ``[`` can start such a label and the tail is matched once with disjoint classes
    (``\\s*`` / ``\\S*``), so the check is linear."""
    start = checked.rfind("[")
    if start < 0:
        return False
    match = _CUT_OFF_LABEL.fullmatch(checked, start)
    if match is None:
        return False
    fragment = match.group(1)
    if len(fragment) > _MAX_FACT_ID_LENGTH:
        return False
    return any(fact_id.startswith(fragment) for fact_id in KNOWN_FACT_IDS)


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
#: ``{{metric:matur``, ``{partner_a}``), and so is a closed compact label of any identifier
#: (``[a:foo]``, ``[b:lifepath]``): the analysis prompts forbid square brackets, so a
#: ``[a|b:identifier]`` is a label the model copied or misspelled. A single-letter
#: identifier (``[a:b]``, a ratio) and anything with a blank after the colon stay prose.
UNRESOLVED_TOKEN_PATTERN = re.compile(
    r"[{}]|\[[ab]:[a-z][a-z0-9_]+\]|" + _COMMON_TOKEN_ALTERNATIVES, re.IGNORECASE
)

# ``str.format`` replacement field: ``{`` [field_name] [``!``conversion] [``:``format_spec] ``}``.
# Every part is bounded or made of disjoint character classes, so a search stays linear.
_FORMAT_ATTRIBUTE = r"\.[a-z_][a-z0-9_]*|\[[^\[\]{}\s]{0,32}\]"
_FORMAT_CONVERSION = r"![rsa]"
#: Mini-language of the spec: ``[[fill]align][sign][z][#][0][width][grouping][.precision][type]``.
#: Deliberately the real grammar and not "anything after a colon": ``{x: x>0}`` (set-builder
#: notation) does not parse as a spec and stays prose.
_FORMAT_SPEC = r"(?:[^{}\n]?[<>=^])?[-+ ]?z?#?0?[0-9]*[,_]?(?:\.[0-9]+)?[a-z%]?"
_FORMAT_TAIL = rf"(?:{_FORMAT_CONVERSION})?(?::{_FORMAT_SPEC})?\}}"
_FORMAT_FIELD_ALTERNATIVES = (
    # named field: {name}, {name!r}, {name:>10}, {a.b[0]!s:^5}
    rf"\{{[a-z_][a-z0-9_]*(?:{_FORMAT_ATTRIBUTE})*{_FORMAT_TAIL}"
    # positional field {0}, {12:>3}, {0.attr}: not after a word, ^, _, backslash or a
    # closing bracket, so the quantifier a{3} and LaTeX x^{2}, \frac{1}{2} stay prose
    rf"|(?<![\w^_\\}}\])])\{{[0-9]+(?:{_FORMAT_ATTRIBUTE})*{_FORMAT_TAIL}"
    # unnamed field with conversion and/or spec: {!r}, {:>10}, {:.2f}
    rf"|\{{{_FORMAT_CONVERSION}(?::{_FORMAT_SPEC})?\}}"
    rf"|\{{:{_FORMAT_SPEC}\}}"
)

#: Lenient variant for free-form product text (report sections, Copilot replies), where
#: an isolated brace is legitimate (``{1,2}``, a set ``{ 3 }``, code or maths in an
#: answer) and rejecting it would fail a whole report or turn: only concrete placeholder
#: shapes count -- ``{{`` / ``}}`` (also unbalanced, i.e. a cut-off ``{{metric:matur``),
#: ``{identifier}`` with optional ``:``/``.`` parts, an opening ``{metric`` /
#: ``{special`` that was never closed, and every ``str.format`` replacement field
#: (``{0}``, ``{name!r}``, ``{:>10}``).
LENIENT_UNRESOLVED_TOKEN_PATTERN = re.compile(
    r"\{\{|\}\}"
    r"|\{\s*[a-z_][a-z0-9_]*(?:\s*[:.]\s*[a-z0-9_]+)*\s*\}"
    r"|\{\s*(?:metric|special)\b"
    "|" + _FORMAT_FIELD_ALTERNATIVES + "|" + _COMMON_TOKEN_ALTERNATIVES,
    re.IGNORECASE,
)


def _find_in_canonical_form(checked: str, *, strict_braces: bool) -> str | None:
    """Scans the `canonical_for_check` view. Linear in ``len(checked)``; no length limit
    of its own (the limit lives in `find_unresolved_template_token`)."""
    for marker in PROMPT_SCAFFOLDING_MARKERS:
        if marker in checked:
            return marker
    pattern = UNRESOLVED_TOKEN_PATTERN if strict_braces else LENIENT_UNRESOLVED_TOKEN_PATTERN
    match = pattern.search(checked)
    if match:
        return match.group(0)
    return "[a:" if _ends_in_cut_off_label(checked) else None


def find_unresolved_template_token(text: str, *, strict_braces: bool = True) -> str | None:
    """The first unresolved internal template token in ``text`` (prompt scaffolding or
    any `UNRESOLVED_TOKEN_PATTERN` form), or ``None`` when the text is clean.

    The single check every pipeline runs over text that is about to become a result
    (relationship/shadow statements, report sections and summaries, Copilot replies), so
    "a finished text carries no internal token" is stated once. The `canonical_for_check`
    form is inspected; the return value is the offending *token* (at most
    `_MAX_TOKEN_CHARS` characters), never surrounding prose, so it is safe to put into a
    log line.

    ``strict_braces=True`` (default, analyses) rejects any ``{`` or ``}``;
    ``strict_braces=False`` (report, Copilot) only rejects concrete placeholder shapes,
    see `LENIENT_UNRESOLVED_TOKEN_PATTERN`. Every other form is identical.

    A text longer than `MAX_CHECKED_TEXT_CHARS` is not scanned at all and yields
    `OVERSIZE_TOKEN`: no product text of this application comes anywhere near the limit,
    and failing closed is cheaper than normalising an unbounded input."""
    if len(text) > MAX_CHECKED_TEXT_CHARS:
        return OVERSIZE_TOKEN
    token = _find_in_canonical_form(canonical_for_check(text), strict_braces=strict_braces)
    return None if token is None else token[:_MAX_TOKEN_CHARS]


def find_unresolved_token_in_payload(payload: object, *, strict_braces: bool = True) -> str | None:
    """`find_unresolved_template_token` over every string (values and mapping keys) of a
    JSON-like payload -- the check a service runs on the complete result right before it
    is persisted, independent of which field a pipeline remembered to check. Iterative, so
    neither depth nor width of the payload can exhaust the stack."""
    pending: list[object] = [payload]
    while pending:
        node = pending.pop()
        if isinstance(node, str):
            token = find_unresolved_template_token(node, strict_braces=strict_braces)
            if token is not None:
                return token
        elif isinstance(node, Mapping):
            for key, value in node.items():
                pending.append(key)
                pending.append(value)
        elif isinstance(node, list | tuple | set | frozenset):
            pending.extend(node)
    return None
