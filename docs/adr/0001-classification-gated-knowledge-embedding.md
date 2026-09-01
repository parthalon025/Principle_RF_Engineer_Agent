---
status: accepted
---

# Classification-gated knowledge embedding

Knowledge ingestion sends chunk text to an external embedding API to
populate `document_chunks.embedding`, but `docs/SECURITY.md` requires
applying an outbound-model policy before transmitting data to an external
provider, and `docs/LICENSE_MATRIX.md` flags manufacturer data and
standards as rights-restricted. We resolved the conflict by requiring an
explicit `PUBLIC`/`INTERNAL`/`SENSITIVE`/`RESTRICTED` classification on
every ingested document (mandatory `ingest_document` argument, no default)
and only sending `PUBLIC`/`INTERNAL` chunks to the external embedding API
via `index_document`. `SENSITIVE`/`RESTRICTED` documents are still parsed,
stored, and chunked — they just never get an embedding, and remain
searchable only through Postgres full-text search over
`document_chunks.content`.

## Considered options

A local embedding model (e.g. `sentence-transformers`) instead of skipping
embedding entirely for restricted material — deferred, because
`document_chunks.embedding` is fixed at `vector(1536)` to match the
external provider's dimension, and no equal-dimension local model is wired
up yet. Revisit once a local-embedding phase exists.
