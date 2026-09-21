"""Bridge between the engine's explicit errors and the API's typed application errors.

The engine must keep raising its own errors — it is a pure library and its codes are
part of its contract. The API boundary, however, may not let an input condition escape
as an HTTP 500 (#176): a birth name containing digits is user input, not a server
fault. `map_engine_error` performs that translation in exactly one place so both engine
entry points in the calculations router (`/calculations` and `/timing`) behave alike.
"""

from __future__ import annotations

from numra_api.services.errors import NormalizationFailed
from numra_numerology.models.errors import NormalizationUnsupportedScript


def map_engine_error(exc: NormalizationUnsupportedScript) -> NormalizationFailed:
    """Translate a normalisation refusal into a 4xx domain error with the engine's code."""
    return NormalizationFailed(code=exc.code, message=str(exc))
