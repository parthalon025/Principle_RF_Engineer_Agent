-- Templated, not directly valid SQL: `${EMBEDDING_DIM_EXTERNAL}` and
-- `${EMBEDDING_DIM_LOCAL}` below are substituted from those env vars
-- (default 1536 each) before this file is applied. Apply it via
-- `uv run python db/apply_schema.py` (reads DATABASE_URL same as the rest
-- of the app) rather than `psql -f` directly. `docker compose up postgres`
-- does its own equivalent substitution at container-init time (see
-- docker-compose.yml / db/docker-init.sh) so a fresh container picks up
-- the same env vars.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    source_uri TEXT,
    source_type TEXT NOT NULL,
    author TEXT,
    revision TEXT,
    publication_date DATE,
    license TEXT,
    authority_rank INTEGER NOT NULL DEFAULT 100,
    checksum_sha256 TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS supersedes_document_id BIGINT REFERENCES documents(id);

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    section TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(${EMBEDDING_DIM_EXTERNAL}),
    UNIQUE(document_id, chunk_index)
);

-- embedding_local (ticket #9 / ADR-0004): a second, independently-dimensioned
-- vector column for chunks embedded via the self-hosted backend. Nullable,
-- same as `embedding` -- a chunk has at most one of the two populated,
-- whichever backend actually embedded it (knowledge/index.py).
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_local vector(${EMBEDDING_DIM_LOCAL});

CREATE TABLE IF NOT EXISTS components (
    id BIGSERIAL PRIMARY KEY,
    manufacturer TEXT,
    part_number TEXT NOT NULL,
    category TEXT NOT NULL,
    specifications JSONB NOT NULL DEFAULT '{}'::jsonb,
    datasheet_document_id BIGINT REFERENCES documents(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(manufacturer, part_number)
);

CREATE TABLE IF NOT EXISTS designs (
    id BIGSERIAL PRIMARY KEY,
    design_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    revision TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    architecture JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS engineering_results (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT REFERENCES designs(id) ON DELETE CASCADE,
    result_type TEXT NOT NULL,
    name TEXT NOT NULL,
    value JSONB NOT NULL,
    provenance TEXT NOT NULL,
    source_uri TEXT,
    tool_name TEXT,
    tool_version TEXT,
    model_revision TEXT,
    confidence TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verification_items (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT REFERENCES designs(id) ON DELETE CASCADE,
    requirement_id TEXT NOT NULL,
    requirement TEXT NOT NULL,
    method TEXT NOT NULL,
    expected JSONB,
    actual JSONB,
    status TEXT NOT NULL DEFAULT 'NOT VERIFIED',
    evidence_uri TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS decision_records (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT REFERENCES designs(id) ON DELETE CASCADE,
    record_key TEXT NOT NULL UNIQUE,
    decision TEXT NOT NULL,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    rationale TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    approval_required BOOLEAN NOT NULL DEFAULT TRUE,
    approval_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Issue #167: which design family (absorber, reflection-phase steering
-- surface, patch antenna, ...) an ARCHITECTURE/REDESIGN_DECISION row's
-- decision was made about (CONTEXT.md's "Design family", docs/adr/0018).
-- Nullable -- only architecture_decision/redesign_decision rows carry a
-- value; every other decision_records row (there are none yet from any
-- other source) has none. Added via ALTER TABLE ADD COLUMN IF NOT EXISTS,
-- not folded into the CREATE TABLE above, matching this file's own
-- already-established convention for extending a table that predates the
-- column (see `documents.status`/`documents.supersedes_document_id`
-- above) -- schema.sql is re-applied against a live database
-- (db/apply_schema.py), where CREATE TABLE IF NOT EXISTS is a no-op.
ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS design_family TEXT;

-- Issue #154 (ADR-0015, CONTEXT.md: Material-property library). Every
-- citation is its own row, keyed by (material, property, frequency band) --
-- deliberately no UNIQUE constraint on that triple, since two independent,
-- disagreeing citations for the same material/property/frequency are the
-- exact case this table exists to keep (designs/material_properties.py's
-- own module docstring gives the worked example: three FR4 papers
-- disagreeing on epsilon_r/tan_delta). frequency_low_hz/frequency_high_hz
-- model the validity band a real citation reports (equal for a single test
-- point); citation/note are TEXT rather than a foreign key into `documents`
-- because ADR-0015 only requires a human-readable citation trail, not a
-- second document-ingestion path for this feature.
CREATE TABLE IF NOT EXISTS material_properties (
    id BIGSERIAL PRIMARY KEY,
    material TEXT NOT NULL,
    property TEXT NOT NULL,
    frequency_low_hz DOUBLE PRECISION NOT NULL,
    frequency_high_hz DOUBLE PRECISION NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    provenance TEXT NOT NULL,
    citation TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Added after the FR4 seeds, when migrating the twelve substrates of
-- docs/xband-absorber-substrate-shortlist.md showed the schema could not
-- hold what the sources actually report. Both nullable, so every row and
-- caller written before them is unaffected.
--
-- ALTER, not columns in the CREATE above, because apply_schema.py must stay
-- safe to re-run "against an already-initialized database" -- and against
-- one, CREATE TABLE IF NOT EXISTS is a no-op that would silently skip them,
-- leaving inserts to fail on a missing column. Same pattern as the
-- documents table's status/supersedes_document_id above.
--
-- `uncertainty` is the source's OWN stated error bar on this value (Kapton
-- 500HN is published as tan_delta 0.012 +/- 0.004). It is a different
-- quantity from the spread across disagreeing citations, which
-- resolve_material_property already derives: the spread says how much two
-- labs disagree, the uncertainty says how much one lab doubts itself.
--
-- `method` is how the value was obtained (coaxial dielectric probe,
-- microstrip ring resonator, CPW de-embedding). Different methods carry
-- different systematic biases, so two values that disagree may not really
-- disagree; without it a caller cannot tell a genuine conflict from a
-- systematic offset.
ALTER TABLE material_properties ADD COLUMN IF NOT EXISTS uncertainty DOUBLE PRECISION;
ALTER TABLE material_properties ADD COLUMN IF NOT EXISTS method TEXT;

CREATE INDEX IF NOT EXISTS material_properties_material_property_idx
ON material_properties (material, property);

-- Issue #154 (ADR-0015): a Family fallback bracket is one current best
-- cited [min, max] range per (family, property) -- UNIQUE here, unlike
-- material_properties above, because a bracket narrows over time as more
-- per-material entries accumulate rather than accumulating disagreeing
-- brackets of its own (designs/material_properties.py's
-- insert_family_bracket upserts on this constraint).
CREATE TABLE IF NOT EXISTS material_family_brackets (
    id BIGSERIAL PRIMARY KEY,
    family TEXT NOT NULL,
    property TEXT NOT NULL,
    min_value DOUBLE PRECISION NOT NULL,
    min_citation TEXT NOT NULL,
    max_value DOUBLE PRECISION NOT NULL,
    max_citation TEXT NOT NULL,
    unit TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(family, property)
);

-- Issue #256 (ADR-0027, "the alphabet admits only printed letters, and a
-- letter's identity includes the process that made it"). A Process record
-- is the "stated box" ADR-0027 point 4 requires before an
-- Element/Coding-Alphabet library entry (a "letter") can be admitted as a
-- measurement rather than an assumption: machine, ink and grade, substrate
-- stack, pass count, achieved film thickness, and cure schedule -- ADR-0027's
-- own field list, transcribed exactly, not re-derived.
--
-- `ink`/`ink_grade` are two columns, not one, because ADR-0027 lists them as
-- two facts ("ink and grade") and issue #256's own field list glosses that
-- as "ink (name/grade)" -- the ink material and its grade are independently
-- meaningful and independently queryable (e.g. "every record on ACI SC1502
-- carbon, any grade").
--
-- No UNIQUE constraint across these fields, deliberately, mirroring
-- `material_properties` above rather than `material_family_brackets`: two
-- runs on nominally identical settings are still two distinct,
-- independently-referenceable Process records, since "achieved" film
-- thickness in particular can vary run to run (issue #256's own Solution
-- section).
--
-- This table is referenced by, but does not itself reference,
-- `symbol_alphabet_entries` -- that table, and the NOT NULL foreign key
-- enforcing ADR-0027's "no entry without a process reference" rule (user
-- story 4), is separate, dependent work (issue #256's ticket 2).
CREATE TABLE IF NOT EXISTS process_records (
    id BIGSERIAL PRIMARY KEY,
    machine TEXT NOT NULL,
    ink TEXT NOT NULL,
    ink_grade TEXT NOT NULL,
    substrate_stack TEXT NOT NULL,
    pass_count DOUBLE PRECISION NOT NULL,
    achieved_film_thickness_m DOUBLE PRECISION NOT NULL,
    cure_schedule TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
ON document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_local_hnsw
ON document_chunks USING hnsw (embedding_local vector_cosine_ops);

CREATE INDEX IF NOT EXISTS documents_metadata_gin
ON documents USING gin (metadata);

-- Ticket #17: lets `verify_requirement` (a future ticket) target exactly
-- one row via (design_id, requirement_id), and makes `create_design`'s
-- one-verification_items-row-per-requirement-key auto-creation safe to
-- run idempotently. ALTER TABLE has no `ADD CONSTRAINT IF NOT EXISTS`, so
-- this file's usual idempotent-ALTER style is approximated with a
-- DO block that swallows the "already exists" case. The doubled dollar
-- quoting below is written 4x over rather than 2x: db/apply_schema.py
-- runs this file through Python's string.Template first, which treats a
-- 2x run as an escaped single dollar sign, collapsing it -- the 4x run is
-- what a DO block's dollar quoting needs to survive that substitution pass.
DO $$$$ BEGIN
    ALTER TABLE verification_items
        ADD CONSTRAINT verification_items_design_id_requirement_id_key
        UNIQUE (design_id, requirement_id);
EXCEPTION
    -- A named UNIQUE constraint backs itself with a same-named index, so a
    -- second run collides on that index (duplicate_table, 42P07) rather
    -- than on the constraint name itself (duplicate_object, 42710) --
    -- both are caught so this stays idempotent regardless of which one
    -- fires.
    WHEN duplicate_table OR duplicate_object THEN NULL;
END $$$$;

-- Ticket #10: lexical full-text search over chunk content, alongside the
-- two semantic (embedding) indexes above. `search_knowledge` queries this
-- via `plainto_tsquery`/`ts_rank`.
CREATE INDEX IF NOT EXISTS document_chunks_content_fts_gin
ON document_chunks USING gin (to_tsvector('english', content));

CREATE INDEX IF NOT EXISTS designs_requirements_gin
ON designs USING gin (requirements);
