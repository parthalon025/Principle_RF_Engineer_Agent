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
