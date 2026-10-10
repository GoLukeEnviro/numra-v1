#!/usr/bin/env python3
"""Zaehlt, welche gespeicherten Texte der Token-Detektor beanstandet -- ohne je einen Text
oder eine ID auszugeben (Betriebsskript, schreibfrei).

Eingabe (stdin): ein JSON-Objekt je Zeile::

    {"kind": "report|report_section|relationship|shadow|chat", "bucket": "<prompt_version>",
     "payload": <beliebiges JSON: Text, Liste, Objekt>}

Ausgabe (stdout): ein JSON-Objekt nur mit Zaehlern je ``kind``: Dokumente, Dokumente mit
Treffer des Detektors, Treffer je Kategorie, Treffer des groben Alt-Musters
``\\[[a-z]:[a-z_]+\\]|\\{\\{[^}]*\\}\\}``, und die Form (nicht der Inhalt) der Alt-Treffer, die
der Detektor als Prosa laesst. Der Detektor laeuft im Modus der jeweiligen Pipeline
(Analyse/Schatten streng, Report/Chat locker).

Aufruf auf dem Host, ohne dass Inhalte das Terminal erreichen::

    docker exec numra-prod-postgres-1 psql -U numra -d numra -tAc "SELECT json_build_object(
        'kind','report','bucket',prompt_version,'payload',content_json)::text FROM reports
        WHERE status='COMPLETE'" | uv run python scripts/ops/audit_stored_tokens.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping

from numra_interpretation.llm import rendering_guard
from numra_interpretation.llm.rendering_guard import (
    PROMPT_SCAFFOLDING_MARKERS,
    find_unresolved_template_token,
)
from numra_interpretation.llm.validator import KNOWN_FACT_IDS

#: Die Pipelines, deren Gate jede Klammer ablehnt.
STRICT_KINDS = frozenset({"relationship", "shadow"})

_LEGACY = re.compile(r"\[([a-z]):([a-z_]+)\]|\{\{([^}]*)\}\}")
_ROLE_MARKER = re.compile(
    r"\[\s*(?:profile_fact|knowledge|system|instruction_supplement"
    r"|untrusted_user_content|user_instructions)"
)


#: Feldnamen des Ergebnisschemas, die einzeln ausgewiesen werden; jeder andere Schluessel
#: (auch ein unerwarteter) zaehlt als "other", damit nie ein Inhalt als Feldname erscheint.
_REPORTED_FIELDS = frozenset(
    {"text", "summary", "title", "canonical_refs", "knowledge_refs", "recommended_micro_tasks"}
)


#: ``prompt_version/status`` as the queries build it; anything else is reported as "other" so
#: that a bucket value from the input can never carry content into the output.
_BUCKET = re.compile(r"numra-[a-z]+-v[0-9]+/(?:COMPLETE|FAILED|PENDING|GENERATING)")


def _safe_bucket(value: object) -> str:
    return value if isinstance(value, str) and _BUCKET.fullmatch(value) else "other"


def iter_fields(payload: object) -> Iterator[tuple[str, str]]:
    """``(Feld, Zeichenkette)`` fuer jede Zeichenkette (Werte und Schluessel) eines
    JSON-Dokuments, ohne Rekursion. Das Feld ist der naechste Objektschluessel ueber dem
    Wert, soweit er in `_REPORTED_FIELDS` steht, sonst ``other``."""
    pending: list[tuple[str, object]] = [("other", payload)]
    while pending:
        field, node = pending.pop()
        if isinstance(node, str):
            yield field, node
        elif isinstance(node, Mapping):
            for key, value in node.items():
                pending.append(("other", key))
                pending.append((key if key in _REPORTED_FIELDS else "other", value))
        elif isinstance(node, list | tuple):
            pending.extend((field, item) for item in node)


def classify_token(token: str) -> str:
    """Grobe Kategorie eines vom Detektor gemeldeten Tokens (nie der Text selbst)."""
    if token == "<oversize>":
        return "oversize"
    if token in PROMPT_SCAFFOLDING_MARKERS or _ROLE_MARKER.match(token):
        return "scaffolding_marker"
    if token == "[a:":
        return "cut_off_label"
    if "{{" in token or "}}" in token or re.match(r"[\[{<]\s*(?:metric|special)\b", token):
        return "placeholder"
    if re.match(r"\[\s*[ab]\s*:", token):
        return "short_label"
    if re.fullmatch(r"\{[^{}]*\}", token):
        return "brace_field"
    if token in ("{", "}"):
        return "single_brace"
    if token.startswith("<"):
        return "angle_placeholder"
    if token.startswith("%"):
        return "printf_placeholder"
    return "other"


def _legacy_shape(match: re.Match[str]) -> str:
    """Form eines Alt-Treffers, ohne den Inhalt preiszugeben."""
    if match.group(3) is not None:
        body = match.group(3).strip().lower()
        if body.startswith(("metric:", "special:")):
            return "double_brace_placeholder"
        return "double_brace_other"
    person = "ab" if match.group(1) in "ab" else "other_letter"
    identifier = match.group(2)
    if identifier in KNOWN_FACT_IDS:
        kind = "known_id"
    elif "_" in identifier:
        kind = "snake_case"
    else:
        kind = "plain_word"
    return f"bracket_{person}_{kind}"


def audit(lines: Iterable[str]) -> dict[str, object]:
    documents: Counter[str] = Counter()
    with_hit: Counter[str] = Counter()
    strings: Counter[str] = Counter()
    strings_with_hit: Counter[str] = Counter()
    legacy_documents: Counter[str] = Counter()
    legacy_but_clean: Counter[str] = Counter()
    categories: Counter[tuple[str, str]] = Counter()
    clean_shapes: Counter[tuple[str, str]] = Counter()
    fields: Counter[tuple[str, str]] = Counter()
    buckets: Counter[tuple[str, str, str]] = Counter()
    invalid = 0

    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            kind = str(record["kind"])
            bucket = _safe_bucket(record.get("bucket"))
            payload = record["payload"]
        except (ValueError, KeyError, TypeError):
            invalid += 1
            continue
        strict = kind in STRICT_KINDS
        found: set[str] = set()
        legacy_shapes: set[str] = set()
        clean_legacy_shapes: set[str] = set()
        documents[kind] += 1
        buckets[(kind, bucket, "documents")] += 1
        for field, text in iter_fields(payload):
            strings[kind] += 1
            token = find_unresolved_template_token(text, strict_braces=strict)
            matches = list(_LEGACY.finditer(text))
            if token is not None:
                strings_with_hit[kind] += 1
                fields[(kind, field)] += 1
                found.add(classify_token(token))
            for match in matches:
                shape = _legacy_shape(match)
                legacy_shapes.add(shape)
                if token is None:
                    clean_legacy_shapes.add(shape)
        if found:
            with_hit[kind] += 1
            buckets[(kind, bucket, "with_hit")] += 1
            for category in found:
                categories[(kind, category)] += 1
        if legacy_shapes:
            legacy_documents[kind] += 1
        if clean_legacy_shapes:
            legacy_but_clean[kind] += 1
            for shape in clean_legacy_shapes:
                clean_shapes[(kind, shape)] += 1

    summary: dict[str, object] = {
        "detector": "hardened" if hasattr(rendering_guard, "OVERSIZE_TOKEN") else "base",
        "invalid_lines": invalid,
        "kinds": {},
    }
    kinds: dict[str, object] = {}
    for kind in sorted(documents):
        kinds[kind] = {
            "mode": "strict" if kind in STRICT_KINDS else "lenient",
            "documents": documents[kind],
            "documents_with_hit": with_hit[kind],
            "strings": strings[kind],
            "strings_with_hit": strings_with_hit[kind],
            "legacy_regex_documents": legacy_documents[kind],
            "legacy_regex_documents_detector_clean": legacy_but_clean[kind],
            "hit_categories": {c: n for (k, c), n in sorted(categories.items()) if k == kind},
            "hit_strings_by_field": {c: n for (k, c), n in sorted(fields.items()) if k == kind},
            "legacy_clean_shapes": {
                c: n for (k, c), n in sorted(clean_shapes.items()) if k == kind
            },
            "by_bucket": {
                b: {
                    "documents": buckets[(kind, b, "documents")],
                    "with_hit": buckets[(kind, b, "with_hit")],
                }
                for (k, b, what) in sorted(buckets)
                if k == kind and what == "documents"
            },
        }
    summary["kinds"] = kinds
    return summary


def main() -> int:
    json.dump(audit(sys.stdin), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
