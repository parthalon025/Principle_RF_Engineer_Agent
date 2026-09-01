---
status: accepted
supersedes: ADR-0001
---

# Self-hosted LLM backend for restricted-data processing

ADR-0001 skipped embedding entirely for `SENSITIVE`/`RESTRICTED`
documents because `document_chunks.embedding` sends full chunk text to an
external embedding API, and deferred local embeddings because no
equal-dimension local model was wired up. Component extraction
(ADR-0003) has the same problem one level up: turning a datasheet table
into structured fields requires an LLM call, which is the same category
of outbound data transmission `docs/SECURITY.md` gates for external
providers. A self-hosted backend closes both gaps at once, so we're
recording the trust model and superseding ADR-0001's deferral.

**Trust boundary**: what matters is who controls the model instance and
its data-retention terms, not whose physical hardware it runs on. A
model self-deployed by the org — whether on company-owned hardware or on
rented GPU infrastructure (e.g. RunPod) — is trusted for
`SENSITIVE`/`RESTRICTED` data, because the org controls the deployed
instance directly. OpenAI's hosted API remains the gated "external
provider": it's a shared managed service the org doesn't control the
data handling of. Both self-hosted variants and OpenAI are accessed
through the same OpenAI-compatible API interface (base URL + key,
configured via env) — one code path, backend selected by config, no
per-deployment branching.

**Backend is a floor, not a lock**: `SENSITIVE`/`RESTRICTED` documents
may only use the self-hosted backend, with no exceptions. `PUBLIC`/
`INTERNAL` documents may use either backend, with a config default
(`DEFAULT_LLM_BACKEND`) picking which one absent an override — so
self-hosted isn't limited to being a fallback for restricted content
only.

**No shared fallback path**: if the self-hosted endpoint is unreachable,
`SENSITIVE`/`RESTRICTED` operations fail loudly and the document stays
unprocessed — they never fall back to OpenAI. `PUBLIC`/`INTERNAL`
operations have their own separate fallback-to-OpenAI logic. Two
independent code paths, rather than one shared path with a conditional
guard, because a bug in a shared guard fails open into a data leak,
while a bug in a hard-separated path at worst fails closed into a stuck
document — recoverable, not a leak.

**Embedding dimensions**: `document_chunks.embedding` (external) and a
new nullable `document_chunks.embedding_local` column both get their
vector dimension from config/env (`EMBEDDING_DIM_EXTERNAL`,
`EMBEDDING_DIM_LOCAL`) rather than a hardcoded literal, so swapping
which model backs either backend is a config and migration change, not
a code edit.

## Considered options

A single fallback-capable code path with a runtime classification check
gating whether OpenAI is a legal fallback target — rejected in favor of
two structurally separate paths, per the no-shared-fallback reasoning
above.

Padding or projecting a local model's embedding to the external
provider's 1536 dimension to reuse one column — rejected as unnecessary
lossy indirection now that a second nullable column is cheap.
