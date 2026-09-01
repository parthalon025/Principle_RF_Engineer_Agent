---
status: accepted
---

# Knowledge document revision versioning

Datasheets and standards get superseded by newer revisions, but
`engineering_results` and `decision_records` may already cite a specific
`documents` row, and provenance must stay historically accurate — a past
result citing revision B of a datasheet must not silently start pointing
at revision C's numbers. We chose to insert each new revision as a new
`documents` row rather than overwriting the old one. `documents` gains a
`status` column (`ACTIVE` by default) and a `supersedes_document_id`
self-reference; ingesting a newer revision flips the prior row's status to
`SUPERSEDED` and links it. `search_knowledge` defaults to `status =
'ACTIVE'` documents unless a query pins a specific document/revision id.

## Considered options

Inferring the "current" revision at query time by grouping on
`(title, manufacturer)` and taking the max `publication_date` — rejected
as fragile: title strings get reformatted or typo'd between revisions, and
the failure mode is silent (wrong revision surfaced, not an error). An
explicit link set once at ingest time is cheap by comparison.
