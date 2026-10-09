"""The check that runs on a complete result right before it is persisted as COMPLETE.

The pipelines gate the fields they render. This gate is independent of them: it walks every
string of the finished payload (values and keys, any depth), so a field no pipeline gate
remembered -- a reference list, a title, a version string -- cannot carry an internal
template token into a stored COMPLETE result either. It raises the caller's own error type,
which each service already maps to its retry/fail path; the message names the token only,
never the surrounding prose (the message is logged).
"""

from __future__ import annotations

from numra_interpretation.llm.rendering_guard import find_unresolved_token_in_payload

__all__ = ["assert_no_unresolved_tokens"]


def assert_no_unresolved_tokens(
    payload: object, *, strict_braces: bool, error: type[Exception], code: str
) -> None:
    token = find_unresolved_token_in_payload(payload, strict_braces=strict_braces)
    if token is not None:
        raise error(f"{code}: result to be stored carries the unresolved template token {token!r}")
