"""Universal/Personal Year/Month/Day. See canon-spec.md §27-§29. Never calls
date.today() — every function here requires an explicit as_of_date."""

from __future__ import annotations
