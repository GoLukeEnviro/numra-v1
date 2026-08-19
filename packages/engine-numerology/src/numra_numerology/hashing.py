from __future__ import annotations

import hashlib

from numra_numerology.models.profile import CanonicalProfile


def compute_deterministic_hash(profile: CanonicalProfile) -> str:
    """SHA-256 over the profile's canonical (sort_keys) JSON serialization. Call this with
    ``deterministic_hash`` still unset (None) on the input profile — the hash covers
    everything else: schema/calculation version, normalized inputs, results, and trace."""
    canonical_json = profile.to_canonical_json()
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
