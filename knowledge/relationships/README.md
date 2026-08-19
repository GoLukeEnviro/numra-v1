# Relationships

There is no separate, duplicated "relationship" knowledge store in NUMRA V1.
Relationship-flavored content lives exclusively inside each number's file under
`knowledge/numbers/*.yaml` and `knowledge/master-numbers/*.yaml`, as the
`relationships` field.

The interpretation engine composes relationship text for a given metric at
interpretation time by resolving the applicable number from the
`CanonicalProfile` (see `knowledge/shadows/README.md` for the same resolution
mechanism) and reading that number's `relationships` list — combined with the
metric's own semantic context from `knowledge/metrics/*.yaml`.

V1 does not implement pairwise relationship-compatibility content (see
`specs/canon-spec.md` §33, `RESERVED_UNFROZEN`); this directory covers only the
"how this number tends to show up in relationships" angle for a single profile,
sourced from `knowledge/numbers/*.yaml`, not a separate content set.

This directory intentionally holds no YAML content files of its own, to avoid the
same German phrases drifting out of sync across two directories.
