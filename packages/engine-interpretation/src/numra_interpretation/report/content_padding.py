"""Deterministic content-length shaping for grounding context passed to an
`LLMProvider`.

This is NOT a substitute for real generation quality — it exists so the report
pipeline can be exercised end-to-end (including hitting realistic ULTIMATE-scale word
counts) against the network-free `MockLLMProvider` in tests and CI, without ever
touching that provider's own code. A real provider (Ollama Cloud) does its own
generation and ignores this helper's output length; this only shapes the *grounding
context* handed to whichever provider is configured.
"""

from __future__ import annotations

__all__ = ["deterministic_elaboration"]


def deterministic_elaboration(seed_phrases: tuple[str, ...], target_word_count: int) -> str:
    """Deterministically cycle through ``seed_phrases`` to build grounding text of
    approximately ``target_word_count`` words. No randomness — same inputs always
    produce the same output, so callers relying on this for reproducible tests are
    safe."""
    if not seed_phrases or target_word_count <= 0:
        return ""

    words: list[str] = []
    index = 0
    while len(words) < target_word_count:
        phrase = seed_phrases[index % len(seed_phrases)]
        words.extend(phrase.split())
        index += 1

    return " ".join(words[:target_word_count])
