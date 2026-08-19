# Shadows

There is no separate, duplicated "shadow" knowledge store in NUMRA V1. Shadow
content (and its counterpart, strength content) lives exclusively inside each
number's file under `knowledge/numbers/*.yaml` and `knowledge/master-numbers/*.yaml`,
as the `shadows` / `strengths` fields.

The interpretation engine (`packages/engine-interpretation`) composes shadow text
for a given metric at interpretation time by:

1. Resolving which number (`1`-`9`, or a preserved master `11`/`22`/`33`) applies to
   a metric from the `CanonicalProfile` (via `root_value` / `effective_value` /
   `master_number`).
2. Loading that number's knowledge file and reading its `shadows` list.
3. Combining it with the metric's own semantic context from
   `knowledge/metrics/*.yaml` (e.g. "Seelendrangzahl" vs. "Ausdruckszahl") so the
   same number reads differently depending on which metric it shows up on.

This directory intentionally holds no YAML content files of its own — it exists so
the knowledge tree has a clearly named place documenting where shadow content
actually lives, without duplicating the same German phrases across two directories
(which would risk them drifting out of sync).
