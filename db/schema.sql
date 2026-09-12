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

-- Issue #407 (ADR-0001, ADR-0004). classification used to live only as a
-- key inside the free-form `metadata` JSONB blob, with nothing at the
-- schema level requiring it to be present, correct, or immutable -- the
-- "mandatory, no default" guarantee ADR-0001 describes was enforced only by
-- one function's parameter signature (`knowledge.ingest.ingest_document`),
-- not by the database: any write path that bypassed that one function
-- could insert a document with no classification, or a wrong one, with
-- nothing to catch it. Promoted to a real column here, added the exact
-- same idempotent-ALTER way as `documents.status`/
-- `documents.supersedes_document_id` immediately above -- the two direct
-- precedents this ticket's Implementation Decisions name.
--
-- No DEFAULT, deliberately, matching ADR-0001's "mandatory, no default"
-- intent -- unlike `documents.status` above, which does carry one. This
-- means `ADD COLUMN ... NOT NULL` only succeeds against a `documents` table
-- with zero existing rows: Postgres has no value to backfill an existing
-- row with otherwise. Verified against this project's one live database
-- (0 rows) before this line was written -- `knowledge/db.py`'s
-- `insert_document` is the only production write path today
-- (`knowledge/ingest.py`'s module docstring), and it already requires
-- `DocumentDraft.classification`, so no pre-existing row could have been
-- written without one. If a future environment ever DOES have pre-existing
-- rows when this file is (re-)applied, this line fails loudly (`ERROR:
-- column "classification" contains null values`) rather than silently
-- leaving some rows unclassified -- exactly the failure mode ADR-0001
-- wants, not a bug in this migration.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS classification TEXT NOT NULL;

-- CHECK against the exact closed vocabulary `knowledge/models.py`'s
-- `Classification` enum already defines -- no new vocabulary, just
-- enforcing the one that already exists in Python. Drop-then-add under the
-- same constraint name, matching this file's `components_manufacturer_
-- part_number_key`/`designs_design_key_revision_key` precedent below for a
-- named constraint that isn't a CREATE-TABLE-time PRIMARY KEY/UNIQUE, so
-- this is safe to re-run against both a fresh container and an
-- already-initialized database.
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_classification_check;
ALTER TABLE documents
    ADD CONSTRAINT documents_classification_check
    CHECK (classification IN ('PUBLIC', 'INTERNAL', 'SENSITIVE', 'RESTRICTED'));

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

-- Issue #402: allow deleting a document referenced by a component,
-- clearing the component's datasheet_document_id instead of blocking deletion.
ALTER TABLE components DROP CONSTRAINT IF EXISTS components_datasheet_document_id_fkey;
ALTER TABLE components
    ADD CONSTRAINT components_datasheet_document_id_fkey
    FOREIGN KEY (datasheet_document_id) REFERENCES documents(id) ON DELETE SET NULL;

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

-- Issue #408 (ADR-0037: "Design family keeps both the caller's spelling and
-- the registry's canonical name"). `design_family` immediately above is
-- never rewritten -- it stays whatever string the caller (a human, via the
-- ARCHITECTURE/REDESIGN_DECISION step) actually typed, e.g. "patch_antenna"
-- or "PATCH". `orchestration/design_loop.py`'s ARCHITECTURE step already
-- resolves that string against `designs/design_families.py`'s registry and
-- computes a canonical payload (`recorded["design_family_registry"]
-- ["canonical_name"]`) so two runs spelling the same family differently
-- still group together for #150/#151 -- this column is where that
-- already-computed value lands, alongside the raw one, rather than merging
-- the two into one field (which would silently rewrite what the caller
-- wrote) or re-deriving the canonical name a second time on read. Nullable,
-- same "ALTER TABLE ADD COLUMN IF NOT EXISTS" pattern as design_family
-- immediately above, for the same reason: only architecture_decision/
-- redesign_decision rows ever carry a value.
ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS design_family_canonical TEXT;

-- Issue #322 (ADR-0025's Considered-and-dropped ledger; CONTEXT.md's entry
-- of the same name). Per entry: the family weighed, whether it was kept or
-- dropped, a free-text reason, and a reason kind
-- (human-decision/capability-verdict/engineering-judgment) -- structured,
-- not prose, so a later run can look an entry up deterministically
-- (ADR-0026's rejection memory) rather than parsing free text. Nullable
-- default '[]'::jsonb, same "ALTER TABLE ADD COLUMN IF NOT EXISTS" pattern
-- as design_family immediately above: only architecture_decision/
-- redesign_decision rows ever carry entries (orchestration/tooling.py's
-- ADR-0011 flush), and recording this ledger is never required (ADR-0025's
-- "No gate") -- an empty array is the honest default for a decision that
-- states none.
--
-- SUPERSEDED BY issue #396: the entries themselves moved into their own
-- `considered_and_dropped_entries` table further down this file (a real,
-- indexed, queryable row per entry instead of a scan over this unindexed
-- JSONB array). This column is left in place -- dropping a column is not
-- this file's idempotent-ALTER convention, only adding one is -- but
-- `designs.db.record_decision` no longer writes into it: every row
-- recorded from #396 onward carries this column at its own schema default
-- (`'[]'::jsonb`) regardless of what `considered_and_dropped` the caller
-- actually stated.
ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS considered_and_dropped JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Issue #324 (ADR-0025's 2026-09-09 correction; CONTEXT.md's "Capability
-- warning"). A WHOLLY SEPARATE mechanism from considered_and_dropped above,
-- deliberately its own column: a candidate the currently configured
-- Fabrication capability / Ink-property library / Material-property
-- library selection cannot meet stays `kept` and never appears in
-- considered_and_dropped at all -- it carries an entry here instead (the
-- family, which capability source fell short, which of its properties, the
-- stated need in value/comparator/unit shape, and a free-text reason),
-- re-evaluated every run against the current configuration rather than
-- ever carried forward as settled. Same nullable "ALTER TABLE ADD COLUMN IF
-- NOT EXISTS" / '[]'::jsonb default pattern as considered_and_dropped
-- immediately above, for the same reason: recording a Capability warning is
-- never required (no gate), and an empty array is the honest default for a
-- decision that states none.
ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS capability_warnings JSONB NOT NULL DEFAULT '[]'::jsonb;

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

-- Issue #256 ticket 2 (ADR-0027). A symbol-alphabet entry is a "letter":
-- one printed-and-measured Symbol, keyed by the five-part key ADR-0027
-- point 4 settled -- `(element family, symbol, band, incidence-angle
-- range, process)`. `process_id` is `NOT NULL REFERENCES
-- process_records(id)` because ADR-0027 is explicit that "an entry
-- carrying no process reference is an assumption, not a measurement"
-- (issue #256 user story 4) -- enforced here at the schema level as well
-- as by `designs.element_alphabet.add_symbol_entry`'s own pure-function
-- check, so an insert against a process id that doesn't exist fails
-- loudly (FK violation) rather than creating a dangling reference (user
-- story 16).
--
-- `frequency_low_hz`/`frequency_high_hz` and `incidence_angle_low_deg`/
-- `incidence_angle_high_deg` are both stored as ranges, never a single
-- point -- the same "a band, not a point" discipline `material_properties`
-- already applies to frequency (issue #256 user story 14).
--
-- `geometry` (JSONB) holds the same primitive-dict shape
-- `geometry/unit_cell.py` already produces/consumes -- a single "box"/
-- "polygon" primitive dict, or a list of them -- so a fetched entry can be
-- handed straight into `generate_unit_cell_array`/
-- `generate_coded_unit_cell_array`'s `unit_cell`/`symbol_library` argument
-- with no reshaping (user story 10). `response` (JSONB) holds the
-- characterised `|Gamma|`/`angle Gamma` vs. frequency curve as an array of
-- `{frequency_hz, magnitude, phase_deg}` points (user story 13) -- not a
-- single test point.
--
-- No UNIQUE constraint on the five key fields, deliberately, the same
-- reasoning as `process_records` above: two entries that agree on
-- family/symbol/band/incidence-angle range but differ only in
-- `process_id` (e.g. the same outline printed in carbon ink vs. MXene) are
-- two separate letters, never merged (ADR-0027 point 4's own worked
-- example; issue #256 user story 17). Nothing here expires or
-- invalidates a row on a process change either (ADR-0027 point 3): a
-- lookup against a process id that no longer matches simply returns
-- nothing, which is a query-time behaviour (`designs/element_alphabet.py`),
-- not a schema-level status column -- ADR-0027 explicitly rejected a
-- library with a status field.
--
-- `provenance` is stored on the row (for consistency with how every other
-- provenance-carrying table in this codebase names its own evidence class
-- explicitly -- issue #256's Implementation Decisions) even though its
-- value is never a caller choice: every row this program writes here is
-- `MEASURED` (`knowledge.provenance.MEASURED`), enforced at the pure
-- function layer, not by a CHECK constraint -- mirroring how
-- `material_properties.provenance` is TEXT NOT NULL with the closed vocabulary
-- enforced in Python, not SQL.
CREATE TABLE IF NOT EXISTS symbol_alphabet_entries (
    id BIGSERIAL PRIMARY KEY,
    element_family TEXT NOT NULL,
    symbol TEXT NOT NULL,
    frequency_low_hz DOUBLE PRECISION NOT NULL,
    frequency_high_hz DOUBLE PRECISION NOT NULL,
    incidence_angle_low_deg DOUBLE PRECISION NOT NULL,
    incidence_angle_high_deg DOUBLE PRECISION NOT NULL,
    process_id BIGINT NOT NULL REFERENCES process_records(id),
    geometry JSONB NOT NULL,
    response JSONB NOT NULL,
    provenance TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS symbol_alphabet_entries_family_symbol_idx
ON symbol_alphabet_entries (element_family, symbol);

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

-- Issue #258 ticket 1 (orchestration/approval_audit.py): the durable,
-- independent audit trail for every human approval/refusal decision made
-- against the design-loop gate (orchestration/approval.py) or the
-- design-release gate (designs/release_approval.py). Both of those gates'
-- signing keys are process-local and deliberately non-persistent -- a
-- receipt does not survive a restart, by design -- so this table is the
-- only record of "who decided what, when" that outlives one process.
--
-- `fingerprint_fields` is the exact decision content a human was shown
-- (the same dict `request_loop_step_approval`/`request_design_release_
-- approval` fingerprint their receipt to), stored in full -- never a
-- summary -- so the record answers "what exactly did they approve", not
-- just "did they approve something". `decision_fingerprint` is that same
-- content's canonical SHA-256 hash (the identical algorithm both approval
-- modules already use for their own receipts), stored alongside it so a
-- caller holding a still-live receipt can confirm this audit row is for
-- the same decision without re-deriving the hash.
--
-- `loop_id` is nullable: only a loop-step gate decision has one (a
-- design-release decision's fingerprint has no loop_id at all) -- see
-- orchestration/approval_audit.py's module docstring.
--
-- No UPDATE or DELETE statement is ever issued against this table by
-- orchestration/approval_audit.py -- that module structurally provides no
-- function that could (tests/test_approval_audit.py's structural test
-- holds this at the Python-API level). This table has no trigger
-- enforcing that at the SQL level; the guarantee is that nothing in this
-- codebase's own I/O layer ever asks for one.
CREATE TABLE IF NOT EXISTS approval_audit_log (
    id BIGSERIAL PRIMARY KEY,
    gate TEXT NOT NULL,
    loop_id TEXT,
    fingerprint_fields JSONB NOT NULL,
    decision_fingerprint TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    outcome TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS approval_audit_log_loop_id_idx
ON approval_audit_log (loop_id);

-- Issue #258 ticket 2 (orchestration/approval_cli.py): the working queue
-- behind the local, human-only loop-step approval surface.
--
-- WHY THIS TABLE EXISTS. orchestration/design_loop.py's own module
-- docstring ("STATE DESIGN") is explicit that a `DesignLoopState` is a
-- plain, caller-held dict -- "this project has no long-running server
-- process ... DesignLoopState is a plain, JSON-serializable dataclass the
-- CALLER holds and passes back in on each step-advancing call (like a
-- session token), not server-side persisted state." orchestration/tooling.py
-- only ever writes to Postgres at a REDESIGN_DECISION flush -- i.e. AFTER
-- that same iteration's ARCHITECTURE/MEASUREMENT/REDESIGN_DECISION gates
-- have ALL already been satisfied. The direct consequence: at the moment a
-- loop is actually sitting at a gated step waiting on a human (the state
-- the approval surface exists to unblock), NOTHING about that loop has ever
-- been written to Postgres yet -- `designs.status`, `decision_records`, and
-- `engineering_results` all stay exactly as they were before this
-- iteration started. There is no query over the tables above that can ever
-- find "a loop currently sitting at a gated step" -- there is nothing there
-- to find.
--
-- This table is what closes that gap: a human who hits a gate (from the
-- agent conversation, or a script) writes ONE row here, up front, carrying
-- everything orchestration.tooling.advance_design_loop_step will need to
-- actually complete the step later -- the full state snapshot AND the
-- step_input being proposed -- plus the exact fingerprint_fields
-- (`orchestration.design_loop._decision_fingerprint_fields`'s
-- `{loop_id, iteration, step, content}`) that `request_loop_step_approval`
-- will bind the resulting receipt to. `orchestration/approval_cli.py`'s
-- `list_pending_approvals` reads this table directly (no join needed to
-- express "not yet resolved"): a request row is deleted the moment it is
-- resolved, approved or refused (see that module's docstring) -- so
-- "currently pending" is simply "a row still here". The durable record of
-- WHAT was decided lives in `approval_audit_log` (ticket 1) instead, which
-- this table is never a substitute for: this table is a mutable, short-lived
-- work queue, not an audit trail, and rows are deleted once resolved.
--
-- `loop_state` is the FULL state dict a caller of start_new_design_loop /
-- advance_design_loop_step already holds (design_loop.py's DesignLoopState.
-- to_dict(), extended with design_id/design_key/persisted_decision_count) --
-- stored whole, not reconstructed, because that dict is the ONLY copy of
-- this loop's history that exists anywhere outside the process that is
-- currently holding it in memory.
CREATE TABLE IF NOT EXISTS pending_loop_step_approvals (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT REFERENCES designs(id) ON DELETE CASCADE,
    loop_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    step TEXT NOT NULL,
    fingerprint_fields JSONB NOT NULL,
    loop_state JSONB NOT NULL,
    step_input JSONB NOT NULL,
    submitted_by TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pending_loop_step_approvals_design_id_idx
ON pending_loop_step_approvals (design_id);

CREATE INDEX IF NOT EXISTS pending_loop_step_approvals_loop_id_idx
ON pending_loop_step_approvals (loop_id);

-- The design-release gate's own version of the table above (issue #258
-- ticket 3): one row per pending "may this design revision move to
-- RELEASED" decision, holding exactly what
-- `designs.release_approval.release_fingerprint_fields` needs
-- (design_id/design_key/revision/target) plus who submitted it. A release
-- decision has no mid-loop state to snapshot (no loop_state/step_input
-- columns here, unlike the table above) -- the fingerprint fields ARE the
-- whole decision. A row is deleted the moment it is resolved (approved or
-- refused), same convention as `pending_loop_step_approvals`; the durable
-- record of what was decided lives in `approval_audit_log`
-- (gate='design_release') instead.
CREATE TABLE IF NOT EXISTS pending_design_release_approvals (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT REFERENCES designs(id) ON DELETE CASCADE,
    design_key TEXT NOT NULL,
    revision TEXT NOT NULL,
    target TEXT NOT NULL,
    fingerprint_fields JSONB NOT NULL,
    submitted_by TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pending_design_release_approvals_design_id_idx
ON pending_design_release_approvals (design_id);

-- Issue #321 (ADR-0031, CONTEXT.md: Requirements document). One row per
-- REVISION of a design's Requirements document, never updated in place --
-- "every revision is kept, never overwritten" (ADR-0031), the same instinct
-- that keeps an ADR's own corrections dated and appended rather than
-- silently rewriting the claim they correct. A document's current
-- status/narrative/requirement_targets is simply its highest
-- revision_number row for that design_id; the full review history is every
-- row for that design_id, ordered by revision_number.
--
-- One Requirements document per Design (ADR-0031: "one document per Design,
-- not one per Customer requirement") -- enforced by
-- designs.requirements_document.create_requirements_document refusing a
-- second document for a design_id that already has one, not by a schema
-- constraint here (a second document would simply be a second, distinct
-- revision_number=1 row, which the application layer never writes).
--
-- `narrative` is the single capability-description/intended-effect prose
-- for the whole design; `requirement_targets` is a dict keyed by
-- requirement_id, one entry per Customer requirement row already recorded
-- on the design, each entry shaped like designs.requirement_targets.
-- propose_target/mark_unscoreable's own output -- the same structured
-- fields ADR-0031 says get extracted into requirements[requirement_id]
-- once this document reaches CONFIRMED (a later ticket's job, not this
-- one's).
CREATE TABLE IF NOT EXISTS requirements_documents (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT NOT NULL REFERENCES designs(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    narrative TEXT NOT NULL,
    requirement_targets JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(design_id, revision_number)
);

CREATE INDEX IF NOT EXISTS requirements_documents_design_id_idx
ON requirements_documents (design_id);

-- Issue #367 (DB standards cleanup). Four fixes below, each an idempotent
-- ALTER so it lands the same way on a fresh container and on an
-- already-initialized database -- CREATE TABLE IF NOT EXISTS alone cannot
-- retrofit any of these onto a table that already exists.

-- `read_design` (designs/db.py) filters both of these by design_id on
-- every single design read, and `read_engineering_results_for_scoring`
-- (called from orchestration/solver.py on every scored candidate search)
-- filters engineering_results the same way -- both were missing the index
-- `pending_loop_step_approvals`/`pending_design_release_approvals` already
-- carry for the identical access pattern.
CREATE INDEX IF NOT EXISTS engineering_results_design_id_idx
ON engineering_results (design_id);

CREATE INDEX IF NOT EXISTS decision_records_design_id_idx
ON decision_records (design_id);

-- Every real write path (record_decision/record_engineering_result/
-- create_design's verification_items insert/approval_cli.py's two
-- pending-approval inserts) already guarantees a real design_id -- this
-- backs that guarantee at the schema layer too, matching the convention
-- already used for document_chunks.document_id and
-- symbol_alphabet_entries.process_id (and, correctly, requirements_documents.
-- design_id above). SET NOT NULL is a no-op if a column is already NOT
-- NULL, so this is safe to re-run.
ALTER TABLE engineering_results ALTER COLUMN design_id SET NOT NULL;
ALTER TABLE verification_items ALTER COLUMN design_id SET NOT NULL;
ALTER TABLE decision_records ALTER COLUMN design_id SET NOT NULL;
ALTER TABLE pending_loop_step_approvals ALTER COLUMN design_id SET NOT NULL;
ALTER TABLE pending_design_release_approvals ALTER COLUMN design_id SET NOT NULL;

-- ADR-0002's dedup guarantee ("a document with this checksum already
-- exists") was enforced only by knowledge/db.py's check-then-insert, with
-- the check running before the INSERT's own transaction even opens -- two
-- concurrent ingests of the same file could both pass the check before
-- either committed. A partial index (checksum_sha256 is nullable) backs
-- the guarantee at the database level; knowledge/db.py's insert_document
-- catches the resulting UniqueViolation and raises the same
-- DuplicateDocumentError the sequential path already raises.
CREATE UNIQUE INDEX IF NOT EXISTS documents_checksum_sha256_key
ON documents (checksum_sha256) WHERE checksum_sha256 IS NOT NULL;

-- UNIQUE(manufacturer, part_number) does not dedupe two NULL-manufacturer
-- rows against each other (Postgres treats NULLs as distinct by default),
-- so knowledge/db.py's upsert_component silently inserted a second row
-- instead of updating the first whenever a supplier feed omitted the
-- manufacturer field -- verified live against this database. Drop-then-add
-- under the same constraint name so this is safe to re-run.
--
-- Issue #418: the ADD is additionally wrapped in the same
-- DO-block-with-exception-handling idiom the verification_items constraint
-- above uses (rather than relying on the DROP alone). A plain unconditional
-- ADD right after the DROP is already idempotent on its own here -- the
-- name never changes, so the DROP above always clears the way -- but
-- wrapping it too costs nothing and matches the designs fix immediately
-- below, which genuinely needs the DO block because its constraint gets
-- renamed.
ALTER TABLE components DROP CONSTRAINT IF EXISTS components_manufacturer_part_number_key;
DO $$$$ BEGIN
    ALTER TABLE components
        ADD CONSTRAINT components_manufacturer_part_number_key
        UNIQUE NULLS NOT DISTINCT (manufacturer, part_number);
EXCEPTION
    WHEN duplicate_table OR duplicate_object THEN NULL;
END $$$$;

-- Issue #369. CONTEXT.md documents, as an already-holding rule, that a
-- released design gets a new revision rather than being edited back into
-- engineering -- but `design_key` alone was UNIQUE, so the database could
-- never actually hold two revisions of the same design_key. Drop the old
-- (pre-rename) constraint name, then add the new one -- matching issue
-- #367's identical fix to components' constraint above -- safe to re-run
-- against both a fresh container and an already-initialized database.
--
-- Unlike the components fix immediately above, this one RENAMES the
-- constraint (`designs_design_key_key` -> `designs_design_key_revision_key`),
-- so a first run leaves ONLY the new name behind. A plain unconditional ADD
-- under the new name would then fail on every run after that: `DROP ...
-- designs_design_key_key` is a no-op once already renamed away, but the
-- unqualified `ADD CONSTRAINT designs_design_key_revision_key` collides
-- with itself (`DuplicateTable`) -- exactly what happened applying this
-- file a second time, first against issue #407's sandbox database and
-- again (against a long-lived, already-migrated database) in issue #418.
-- The ADD is wrapped in the DO-block-with-exception-handling idiom the
-- verification_items constraint above uses, so a second (or Nth) run that
-- finds the new name already in place swallows the resulting exception
-- instead of aborting the rest of this file.
ALTER TABLE designs DROP CONSTRAINT IF EXISTS designs_design_key_key;
DO $$$$ BEGIN
    ALTER TABLE designs
        ADD CONSTRAINT designs_design_key_revision_key
        UNIQUE (design_key, revision);
EXCEPTION
    WHEN duplicate_table OR duplicate_object THEN NULL;
END $$$$;

-- Issue #398: a design's revision history should be traceable through the
-- database via a real link (supersedes_design_id), mirroring the pattern
-- `documents.supersedes_document_id` already uses for the same "what did this
-- follow" question. Nullable -- a design with no predecessor (the first in a
-- family, or an independent design) has none. Added via ALTER TABLE ADD COLUMN
-- IF NOT EXISTS, matching the convention already used in this file for
-- extending tables that predate the column (see `documents.status` /
-- `documents.supersedes_document_id` above).
ALTER TABLE designs ADD COLUMN IF NOT EXISTS supersedes_design_id BIGINT REFERENCES designs(id);

-- Issue #395 (duplicate of #392's identical deliverable; both closed by
-- this table). A 9-reviewer DB architecture-soundness review found the
-- same gap from five independent angles: `designs.architecture` names
-- which real, orderable `components` row backs each functional block
-- (`designs.validation.extract_component_refs`'s walk), but that link was
-- only ever checked once, at `create_design` time, and never again --
-- `architecture` is a JSON blob, so Postgres itself had no way to see or
-- protect the link. Nothing stopped a referenced component from being
-- deleted out from under a live design, and "which designs use component
-- X" had no answer short of scanning every design's JSON by hand.
--
-- `component_id` deliberately carries no `ON DELETE` action -- default
-- `RESTRICT` -- so a `components` row a live design still references
-- cannot be deleted out from under it; a caller that genuinely needs to
-- remove a component must first remove or repoint every design that
-- references it (proven live in tests/test_designs_db.py against the real
-- constraint, not mocked -- the same discipline
-- tests/test_element_alphabet.py already applies to
-- symbol_alphabet_entries.process_id). `design_id` is `ON DELETE CASCADE`,
-- matching every other design-scoped child table in this file
-- (`engineering_results`, `verification_items`, `decision_records`, ...):
-- once the `designs` row itself is gone, its component references go
-- with it.
--
-- `UNIQUE(design_id, block)` -- `block` is the architecture block name
-- (`designs.validation._iter_component_refs`'s nearest-enclosing-dict-key
-- label, e.g. "lna"/"mixer"); today's architecture shape never repeats a
-- block name within one design's own JSON (each is a distinct dict key),
-- so this also catches a future write path silently double-inserting the
-- same block.
--
-- Populated by `designs.db.create_design` in the same transaction as the
-- `designs`/`architecture` write it describes, reusing the already-
-- validated `component_id` list `_find_dangling_component_refs` computes
-- today -- no second validation pass, no new seam. No path exists yet for
-- updating an existing design's `architecture` after creation (every
-- design-loop-created design is created with `architecture={}` and
-- nothing ever updates it afterward), so `create_design` is this table's
-- only writer for now; a future architecture-update path must keep this
-- table in step the same way, not just write `architecture`'s JSON.
CREATE TABLE IF NOT EXISTS design_component_refs (
    id BIGSERIAL PRIMARY KEY,
    design_id BIGINT NOT NULL REFERENCES designs(id) ON DELETE CASCADE,
    component_id BIGINT NOT NULL REFERENCES components(id),
    block TEXT NOT NULL,
    UNIQUE(design_id, block)
);

-- The new "which designs use component X" query direction
-- (`designs.db.find_designs_referencing_component`) -- the primary key
-- above indexes `id`, and `UNIQUE(design_id, block)` indexes `design_id`
-- as its leftmost column, but neither covers a `component_id`-first
-- lookup, which is the one this table exists to make fast and indexed
-- instead of a full-table JSON scan.
CREATE INDEX IF NOT EXISTS design_component_refs_component_id_idx
ON design_component_refs (component_id);

-- Issue #401: knowledge/db.py's insert_document enforced "can't supersede
-- an already-superseded document" purely with a SELECT-then-check inside
-- its own transaction -- the exact check-then-insert race that
-- documents_checksum_sha256_key above was already added to close for
-- checksums, left open here. Two concurrent ingests both declaring
-- `supersedes_document_id` for the same target could each pass the SELECT
-- (neither sees the other's not-yet-committed UPDATE) and both insert,
-- leaving that target claimed as superseded by two different rows and
-- breaking ADR-0002's linear revision chain. Partial index (the column is
-- nullable) backs the guarantee at the database level; insert_document
-- catches the resulting UniqueViolation and raises InvalidSupersessionError.
CREATE UNIQUE INDEX IF NOT EXISTS documents_supersedes_document_id_key
ON documents (supersedes_document_id) WHERE supersedes_document_id IS NOT NULL;

-- Issue #396 (parent #393; ADR-0025's Considered-and-dropped ledger). Moves
-- the ledger's ENTRIES (not the ledger concept itself, which stays exactly
-- what ADR-0025/CONTEXT.md describe) out of the unindexed
-- `decision_records.considered_and_dropped` JSONB array above into their
-- own table, one row per entry, so "has this option already been refused
-- for this reason" and ADR-0025's own named payoff query -- "every entry
-- ever dropped as a capability-verdict is exactly what relaxing that
-- requirement unlocks" -- are real, deterministic database queries
-- (`designs.db.find_capability_verdict_entries`) instead of a Python-level
-- scan over `read_design`'s aggregated JSON, which is all issue #322's
-- original, deliberately simple, first cut could offer.
--
-- Columns mirror `orchestration.design_loop`'s own closed entry shape
-- (`_validate_considered_and_dropped`/`_validate_capability_verdict_entry`)
-- exactly: `family`/`verdict`/`reason`/`reason_kind` are stated on every
-- entry; `requirement_id`/`validity_box_property` are stated only on a
-- `reason_kind='capability-verdict'` entry (that reason kind's own issue
-- #322 narrowing -- never on `human-decision`/`engineering-judgment`);
-- `theta_max_deg` only when that entry's `validity_box_property='curvature'`
-- (the one closed-form validity box this codebase currently characterises,
-- `capability_verdict_holds`'s own only branch). All three are nullable for
-- exactly that reason, and `designs.db` omits a NULL one from a
-- reconstructed entry dict entirely rather than carrying it as an explicit
-- None, so a plain human-decision/engineering-judgment entry round-trips
-- through this table byte-for-byte identical to what it was recorded with.
--
-- `entry_index` preserves each entry's position within the original
-- step_input list it arrived in -- `designs.db`'s reconstruction orders on
-- it, not on `id` -- the same "position, not insertion accident" discipline
-- `document_chunks.chunk_index` already applies to a document's chunks.
--
-- FK'd to `decision_records` `ON DELETE CASCADE`, matching every other
-- decision/design-scoped child table in this file: an entry cannot outlive
-- the decision record it was weighed against.
CREATE TABLE IF NOT EXISTS considered_and_dropped_entries (
    id BIGSERIAL PRIMARY KEY,
    decision_record_id BIGINT NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
    entry_index INTEGER NOT NULL,
    family TEXT NOT NULL,
    verdict TEXT NOT NULL,
    reason TEXT NOT NULL,
    reason_kind TEXT NOT NULL,
    requirement_id TEXT,
    validity_box_property TEXT,
    theta_max_deg DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- `designs.db.record_decision`/`read_design` filter this table by
-- decision_record_id on every read (one design's decision_records, or one
-- freshly-inserted row) -- the same "index the column read_design filters
-- by" convention issue #367 already established for engineering_results/
-- decision_records above.
CREATE INDEX IF NOT EXISTS considered_and_dropped_entries_decision_record_id_idx
ON considered_and_dropped_entries (decision_record_id);

-- Backs ADR-0025's own named payoff query directly:
-- `find_capability_verdict_entries`'s cross-design `WHERE reason_kind =
-- 'capability-verdict'` scan (with no decision_record_id/design_id
-- predicate at all) is a real index scan, not a sequential scan over every
-- entry this database has ever recorded across every design, as this table
-- grows.
CREATE INDEX IF NOT EXISTS considered_and_dropped_entries_reason_kind_idx
ON considered_and_dropped_entries (reason_kind);

-- Issue #397 (#393's Capability warning half; ADR-0025's 2026-09-09
-- correction). `decision_records.capability_warnings` (added above, issue
-- #324) is a JSONB array with no index -- "list every entry ever warned
-- for lacking fabrication capability" can only be answered today by
-- unpacking that JSON on every decision_records row in application code.
-- This table gives each entry its own row instead, one per entry, so that
-- query becomes ordinary indexed SQL. `designs/db.py::record_decision`
-- writes here now, in the same transaction as the decision_records insert
-- that owns it; `decision_records.capability_warnings` itself is retired
-- as a source of truth (record_decision no longer writes real content into
-- it -- issue #393's "nothing should read them as authoritative after this
-- ships") but is left in place rather than dropped, per that issue's own
-- "either way" allowance, since dropping it is a separate migration this
-- ticket doesn't need.
--
-- Columns mirror the entry shape `orchestration.design_loop.
-- _validate_capability_warnings` already enforces at write time: `family`
-- (which design family the warning is attached to), `capability_kind` (one
-- of "fabrication"/"ink"/"material" -- which of the three capability
-- sources fell short), `capability_property` (e.g.
-- "min_feature_size_mm"), the stated need in the same `value`/`comparator`/
-- `unit` shape a Requirement target uses, and a free-text `reason`. No
-- CHECK constraint on `capability_kind`'s closed vocabulary here -- same
-- discipline as `material_properties.provenance` elsewhere in this file:
-- the closed set is enforced in Python
-- (`orchestration.design_loop._CAPABILITY_KINDS`), not duplicated in SQL.
--
-- `ON DELETE CASCADE` matches every other decision_records-owned child
-- row in this schema (there are none yet, but this is the same pattern
-- `document_chunks.document_id`/`symbol_alphabet_entries.process_id`
-- already use for their own parent tables) -- an entry cannot outlive the
-- decision record that carries it.
--
-- Two indexes, both named in issue #393's own Implementation Decisions:
-- `decision_record_id` for the per-design join `designs.db.
-- read_capability_warning_entries` runs (the FK alone constrains the
-- column but does not itself create an index on it, unlike a PRIMARY KEY),
-- and `capability_kind` for the cross-design worklist query issue #393
-- names as the actual payoff ("list every entry ever warned for lacking a
-- given capability kind").
CREATE TABLE IF NOT EXISTS capability_warning_entries (
    id BIGSERIAL PRIMARY KEY,
    decision_record_id BIGINT NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
    family TEXT NOT NULL,
    capability_kind TEXT NOT NULL,
    capability_property TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    comparator TEXT NOT NULL,
    unit TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS capability_warning_entries_decision_record_id_idx
ON capability_warning_entries (decision_record_id);

CREATE INDEX IF NOT EXISTS capability_warning_entries_capability_kind_idx
ON capability_warning_entries (capability_kind);
