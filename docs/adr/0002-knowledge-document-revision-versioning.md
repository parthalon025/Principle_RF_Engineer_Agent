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

The link is set by the human uploading the document, not inferred: `ingest_document`
takes an optional `supersedes_document_id` argument, and an upload without
it is always a plain new, independent document, regardless of what it's
titled. The first implementation of this ADR (ticket #8) shipped an
automatic version instead — matching a new upload against an `ACTIVE`
document with the same `(source_type, title)` — which reintroduced, at
ingest time, exactly the title-matching inference this ADR already
rejected below at query time. That was a bug, not a second decision:
fixed directly rather than opened as a new ticket.

## Considered options

Inferring the "current" revision (whether at query time, by grouping on
`(title, manufacturer)` and taking the max `publication_date`, or at
ingest time, by matching a new upload against an existing document's
title) — rejected as fragile: title strings get reformatted, typo'd, or
coincidentally shared between unrelated documents, and the failure mode is
silent (wrong revision superseded or surfaced, not an error). An explicit
link, declared once by the human who already knows what they're uploading
a revision of, is cheap by comparison — the same explicit-over-inferred
pattern already used for `classification`/`license` (ADR-0001).
