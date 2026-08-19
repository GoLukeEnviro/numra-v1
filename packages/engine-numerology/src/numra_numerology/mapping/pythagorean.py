from __future__ import annotations

SYSTEM_NAME = "pythagorean"

VOWELS: frozenset[str] = frozenset("AEIOU")

PYTHAGOREAN_TABLE: dict[str, int] = {
    "A": 1,
    "J": 1,
    "S": 1,
    "B": 2,
    "K": 2,
    "T": 2,
    "C": 3,
    "L": 3,
    "U": 3,
    "D": 4,
    "M": 4,
    "V": 4,
    "E": 5,
    "N": 5,
    "W": 5,
    "F": 6,
    "O": 6,
    "X": 6,
    "G": 7,
    "P": 7,
    "Y": 7,
    "H": 8,
    "Q": 8,
    "Z": 8,
    "I": 9,
    "R": 9,
}


def letter_value(letter: str) -> int:
    return PYTHAGOREAN_TABLE[letter]


def is_vowel(letter: str) -> bool:
    """Y is always a consonant in NUMRA V1 — no contextual exception."""
    return letter in VOWELS


def map_letters(calculation_string: str) -> tuple[int, ...]:
    return tuple(letter_value(ch) for ch in calculation_string)


def vowels_only(calculation_string: str) -> str:
    return "".join(ch for ch in calculation_string if is_vowel(ch))


def consonants_only(calculation_string: str) -> str:
    return "".join(ch for ch in calculation_string if not is_vowel(ch))
