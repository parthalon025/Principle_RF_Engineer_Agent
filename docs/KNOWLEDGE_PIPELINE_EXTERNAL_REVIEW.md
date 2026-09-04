# External review: Notion "Database Engineering & Pipelines" hub vs. this repo's knowledge pipeline

Research findings from reading a Notion knowledge-base hub and its linked
sub-pages end to end, evaluated against this repo's actual pgvector
knowledge-base ingestion pipeline: `db/schema.sql`, `knowledge/*.py`,
`CONTEXT.md`'s Source type / Authority rank / Provenance vocabulary, and
`docs/BUILD_PLAN.md` / `docs/ROADMAP.md`.

**A note on scope before the findings**: this repo's knowledge-base
ingestion pipeline is *not* the unbuilt "schema exists, no ingestion code
yet" state that `CONTEXT.md`'s "What's still open" section and this task's
brief described. As of this session, `knowledge/` contains a working
extraction → chunking → provenance → embedding → indexing → search
pipeline (`extraction.py`, `ingest.py`, `provenance.py`, `embedding.py`,
`index.py`, `search.py`, `db.py`, four accepted ADRs). `CONTEXT.md` was
last edited about an hour before that code landed and hasn't caught up.
The findings below are evaluated against the real, current code — they are
extensions to an existing implementation, not a from-scratch design.

> **Editorial note (added later).** The "What's still open" section quoted
> above no longer exists. `CONTEXT.md` has since been reduced to a glossary,
> precisely because that section went stale three times over — this review
> caught the first instance. Implementation status now lives in `README.md`,
> and open work in GitHub Issues. The sentence above is preserved as an
> accurate record of what the file said at the time, not as a live pointer.

## What the Notion hub covers

Hub page: **"Database Engineering & Pipelines — Tool-Agnostic Deep Dive"**
(workspace: AI & Technical Knowledge Hub). It's a single long encyclopedia
page (~70K characters), not a page with child pages — its "sub-pages" are
inline `mention-page` cross-references scattered through the text and
collected under "Cross-domain connections" and "Sources" at the end. All
were fetched and read:

- **§0–1** Agent protocol and the "universal spine" (ingest as-is → promote
  through trust layers → tests as gates → semantic layer → governed writes
  → close the loop).
- **§2** Layer architecture (Bronze/Silver/Gold as a *pattern*, not
  infrastructure).
- **§3** Six pipeline disciplines: ingestion, transformation, quality
  gates, entity resolution, semantic layer, orchestration/lineage.
- **§3.7** Time & history (SCD types, bitemporal, read-surface naming).
- **§3.8** CI/CD and environment promotion for pipelines.
- **§4** Platform translations (Databricks / Palantir Foundry / general
  Postgres-dbt stack, side by side).
- **§5** "FDE as a method" — Forward Deployed Engineering delivery doctrine.
- **§6** LLMs over structured data: grounding in a semantic layer, tools
  over tokens, evals as gates.
- **§7** Secondary disciplines: data contracts, cost engineering, privacy/
  retention, streaming doctrine, serving-layer performance, **durability &
  recovery (§7.6)**.
- **§8–9** Failure modes and a "definition of done" checklist.
- **§10** Full database taxonomy (OLTP/OLAP/specialized engines), the
  five-axis selection framework, and an explicit exit-trigger table for
  leaving Postgres.
- **§11** Engine internals (B-tree/LSM/columnar/WAL/MVCC/ANN index
  mechanics) that explain *why* the §10 tradeoffs exist.
- **§12** Polyglot persistence laws for running multiple engines as one
  system.

Linked sub-pages fetched and read in full:

1. **"Workflow Template — Raw Data → Ontology → Operational Use Case"** —
   a 13-stage, fill-in-the-blanks template for standing up a *multi-person*
   Palantir/Foundry-style operational build (roles, projects-as-security-
   boundary, weekly demos, adoption metrics, kill criteria). Mostly
   organizational process for a team shipping an operational app, not
   pipeline/schema mechanics.
2. **"How we built our knowledge base"** (Cerebras engineering blog,
   reproduced in Notion) — a concrete internal RAG system: hybrid
   retrieval (lexical + embedding + IDF + recency), Slack-thread
   distillation and "bursting," reciprocal-rank-fusion (RRF) reranking,
   chunk-neighbor context expansion, a single shared `embeddings` table
   across heterogeneous sources.
3. **"Pensiv Backend Completion Blueprint — PostgreSQL v85 × Palantir
   Operating Model"** — a very detailed Postgres + pgvector backend audit
   for an "agent memory" product: vector lifecycle rules, hybrid retrieval
   SQL, embedding-generation/model-version tracking, a retrieval quality
   contract (recall@k/nDCG/MRR), retrieval-feedback tables, source-artifact
   /extraction/normalization tables with content-hash dedup. The most
   directly applicable sub-page to this repo's `db/schema.sql`.
4. **"Medallion Architecture — Deep Research & Fit with the Foundry Dev
   Toolchain"** and **"05 · Data Engineering Playbook"** (from the
   "Palantir Foundry — Developer Reference & Playbook" hub) — Databricks/
   Foundry tool-specific documentation (Lakeflow, Unity Catalog, Pipeline
   Builder, Data Connection). Checked for applicability; none found — see
   "Not applicable" below.
5. **"🏗️ Foundry Pipeline Architect Skill"** and **"Palantir Foundry —
   Developer Reference & Playbook"** (hub page) — same as above, Foundry-
   tool-specific, not applicable to a Postgres-only repo.
6. **"🧠 Cognitive Memory Program — Architecture, Applications &
   Solutions"** — this mention-page resolved to an empty wiki *database*
   index (just a schema/view listing, no page content to read), not a
   page with content. Nothing to extract.

## Concrete, applicable recommendations

Each item cites the specific Notion source and names the repo location it
would change.

### 1. Track which embedding model produced each vector

**Source**: Pensiv Blueprint §6.2 "Vector lifecycle" — *"Never mix
embeddings from different models in one generation. Store model,
dimension, normalization, distance metric, chunk/corpus version, created
time, and status."* Its `memory_embedding_generations` table carries
`model_version`, `normalization_method`, `distance_metric`, `status`
(`active`/`stale`/`retired`), `chunk_seq`, `corpus_version`.

**Repo gap**: `db/schema.sql`'s `document_chunks.embedding` /
`embedding_local` are bare `vector(...)` columns with no metadata.
`knowledge/embedding.py` hardcodes `EXTERNAL_EMBEDDING_MODEL =
"text-embedding-3-small"` as a fixed default, and `LOCAL_EMBEDDING_MODEL`
is read from env at call time — neither is recorded per-chunk. If either
model is ever changed (OpenAI ships a new embedding model, or the
self-hosted deployment swaps models), old and new vectors would sit in the
same column with no way to tell them apart, and `knowledge/db.py`'s
`search_semantic` cosine-distance comparison would silently compare
vectors from different models as if they were comparable — nothing today
would catch this.

**Change**: add `embedding_model` and `embedding_created_at` (minimum) to
`document_chunks`, or follow Pensiv's fuller pattern with a small
`chunk_embedding_generations` side table if per-chunk embedding history
needs to be kept during a migration. This gives a future re-embedding
migration (a model upgrade) the same explicit, non-inferred discipline
ADR-0002 already established for document supersession.

### 2. Add a recall/quality gate before an embedding-model or ranking change ships

**Source**: hub §6 *"Evals gate every change... golden sets of 20–50
representative questions with expected SQL/answers... pinned model +
prompt + tool versions"*; §9 Definition of Done, *"Model-backed steps have
green eval suites at pinned versions."* Pensiv Blueprint §6.3 "Quality
contract": *"No ANN or fusion release is complete without: exact-search
baseline... recall@k, nDCG@k, MRR, zero-result rate, citation precision,
and p50/p95/p99... golden queries plus production feedback with drift
alerts."*

**Repo gap**: `knowledge/search.py` has no golden-query fixture or recall
measurement. `docs/ROADMAP.md` places "evaluation benchmark" at v1.0, with
nothing gating the `EXTERNAL_EMBEDDING_MODEL` choice, the chunking
strategy in `knowledge/extraction.py`, or the `authority_rank`-then-
match-type ordering `search_knowledge` already implements between now and
then.

**Change**: this doesn't need to wait for v1.0. A small fixture of RF-
specific golden queries (e.g. "what's the OIP3 test condition for
&lt;a stored datasheet&gt;") with expected chunk hits, plus a scripted
recall@k check, is cheap to build now while the corpus and code are small
— and expensive to retrofit once ingestion volume grows and any change to
the embedding model or ranking becomes hard to evaluate blind. Worth
pulling into `docs/BUILD_PLAN.md` Phase 3 rather than deferring.

### 3. Consider a retrieval-feedback / citation log for the "audited provenance" goal

**Source**: Pensiv Blueprint §12.10 `retrieval_feedback` table
(`feedback_type`: `relevant`/`not_relevant`/`citation_used`/
`citation_ignored`) — *"closed-loop signal for FSRS, reranker training,
and quality drift."* Hub §1 rule 6, the decision-trace spec: *"Every
governed write emits one trace row containing... the inputs the decider
saw... a slot for the measured outcome when it arrives... action logs
become eval sets, training data, and the... evidence base."*

**Repo gap**: `search_knowledge` returns a ranked list and nothing is
recorded about which chunks the agent actually cited in a final answer.
`docs/ROADMAP.md` v1.0 names "audited provenance" as a goal, but there's
no substrate for it yet in `db/schema.sql`.

**Change**: a lightweight `retrieval_log` (or reuse `engineering_results`'
existing provenance pattern) recording the query, the returned chunk ids,
and which ones the agent's answer cited, would give the audited-provenance
goal a concrete implementation path and double as the eval data recommendation
#2 needs — worth designing once, not twice.

### 4. Content-hash dedup at the chunk level, not just the document level

**Source**: Pensiv Blueprint §12.10 `artifact_normalization_log`:
`content_hash` column with the comment *"Dedup check: content_hash match
within same org → link via derived_from, skip re-embed."*

**Repo state**: document-level dedup is already well handled
(`documents.checksum_sha256`, `find_document_by_checksum`,
`DuplicateDocumentError` in `knowledge/db.py`) — this is not a gap, it's
already good. What's missing is the same idea one level down: a corrected
datasheet revision that changes one table but not the rest currently has
no way to skip re-embedding unchanged chunks cheaply on re-ingest, because
`document_chunks` carries no content hash of its own.

**Change**: minor at current scale — a `content_hash` column on
`document_chunks` is worth adding before ingestion volume or re-ingestion
frequency grows, not urgent today.

### 5. Chunk-neighbor context expansion — a specific, low-effort technique for a known failure mode

**Source**: Cerebras "How we built our knowledge base": *"if we match a
wiki section we pull in the two neighboring sections so the heading,
preconditions, and caveats that chunking split apart aren't lost... a
complete snippet instead of a lonely paragraph that's missing important
context."*

**Repo state**: `document_chunks` already carries `chunk_index` and
`section`, so this is purely a `knowledge/search.py` change (fetch
`chunk_index ± 1` for top results before returning), no schema change
needed. Flagging as a specific, cheap technique worth keeping in mind for
when a real query shows the "table without its section heading" failure
mode `knowledge/extraction.py`'s docstring is already trying to prevent
at ingest time (tables are kept in their own chunk, tagged with the
current section — but a retrieved table chunk alone still loses the
prose around it).

## What's generic or not applicable — evaluated, not force-fit

- **§0/Stages −1 through 9 of the Workflow Template** (roles, projects-as-
  security-boundary, weekly demos, adoption metrics, kill criteria): this
  is FDE/Palantir organizational process for a multi-person team shipping
  an operational app to named users. Nothing here is specific to a
  pgvector schema or an ingestion pipeline; it doesn't map onto a
  single-developer RF engineering tool.
- **§4 platform translations, "Medallion Architecture" deep-dive, "05 ·
  Data Engineering Playbook," "Foundry Pipeline Architect Skill"**: all
  Databricks/Palantir Foundry tool-specific (Lakeflow, Unity Catalog, Data
  Connection, Pipeline Builder). This repo uses Postgres only; nothing in
  these translates into an actionable schema or pipeline change.
- **§10 database taxonomy and selection algorithm**: genuinely well-
  written, but it *validates* a decision this repo already made rather
  than suggesting a new one — the hub's own default ("boring relational —
  Postgres... JSONB, PostGIS, pgvector, and TimescaleDB cover document,
  spatial, vector, and time-series work at moderate scale... most systems
  never need [to leave it]") is exactly what `db/schema.sql` already does.
  No named exit trigger in §10.5 fires for this repo's scale or workload.
- **§12 polyglot persistence laws**: about running multiple database
  engines as one system (cache, search index, warehouse as projections of
  one system of record). This repo has one engine. Not applicable until
  that changes.
- **§7.1 data contracts between teams, §5 "FDE as a method"**: both
  presuppose multiple teams/producers handing data to each other. Not
  applicable to a single-repo ingestion pipeline with one producer.
- **Cerebras "age decay" for staleness**: deliberately not recommended
  here. Cerebras decays Slack answers because infrastructure changes
  underneath them; RF datasheets need the opposite discipline —
  explicit, human-declared supersession (already implemented via
  ADR-0002's `supersedes_document_id`/`status`), because a superseded-but-
  still-correct spec should never silently outrank a wrong newer one by a
  decay heuristic, and a correct old spec should never silently decay
  below a wrong one either.
- **Cerebras "Projects and scoped search"** (multi-team workspace
  scoping): this repo has one corpus and no team/project silos to scope
  by. Not applicable.
- **Hub §7.6 durability & recovery / Pensiv's PITR and restore-drill
  doctrine**: this is real, currently-missing guidance (`docs/OPERATIONS.md`
  has no backup/RPO/RTO content at all), but it's an operations-doc gap,
  not a schema or ingestion-pipeline gap — outside this task's specific
  brief. Flagging it here only so it isn't silently dropped, not counted
  among the "concrete" recommendations above.
- **Cerebras's hybrid-retrieval RRF fusion**: genuinely relevant prior art
  (see recommendation discussion below), but not filed as an actionable
  change — `knowledge/search.py`'s docstring already documents "no score
  fusion" as *ticket #10's explicit non-goal*, a considered decision, not
  a gap the author missed. Recorded here as the specific technique
  (reciprocal rank fusion, weight/(60+rank)) to reach for *if* that
  decision is ever revisited, e.g. if authority-rank-first ordering turns
  out to bury a strong semantic match under a weak lexical one from a
  higher-authority document — not a recommendation to change it now.

## Bottom line

The hub is stack-agnostic doctrine written for general operational data
platforms and, in its Foundry-specific sections, for a tool this repo
doesn't use — most of it validates decisions already made
(Postgres-as-default, semantic chunking, explicit document supersession)
rather than surfacing new ones. The one sub-page with genuinely new,
concrete, and cheap-to-apply content for this specific pipeline is the
**Pensiv Backend Blueprint**'s Postgres + pgvector operating patterns
(§6.2 vector lifecycle, §12.9–12.10 ingest/retrieval-feedback tables,
§16 retrieval quality gates) — recommendations 1–4 above come from it. The
**Cerebras** post contributes one specific, low-effort retrieval technique
(recommendation 5) and one useful piece of prior art to have on file
(RRF fusion) without forcing a change to an already-considered decision.
