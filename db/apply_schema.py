"""Apply `db/schema.sql` to `DATABASE_URL`.

There's no migration tool in this repo (per ticket #9's design notes) --
this is a small templating step, not one. `schema.sql` is otherwise applied
directly; the only reason this script exists is that the vector-column
dimensions are no longer literals (ticket #9 / ADR-0004): they're
substituted from `EMBEDDING_DIM_EXTERNAL` / `EMBEDDING_DIM_LOCAL` (each
defaulting to 1536) before the file is executed. Every statement in
schema.sql is already idempotent (`IF NOT EXISTS` / `ADD COLUMN IF NOT
EXISTS`), so re-running this against an already-initialized database is
safe.

Usage: `uv run python db/apply_schema.py`
"""

from __future__ import annotations

import os
import zlib
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

import psycopg
from dotenv import load_dotenv

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Fixed key naming this critical section in Postgres's session-level
# advisory-lock namespace (issue #399). `pg_advisory_lock`/`_unlock` share
# one global int8 keyspace per database -- any value works as long as it
# doesn't collide with another advisory lock use against the same
# database, so this is a crc32 of a descriptive string rather than a bare
# arbitrary integer: deterministic, fits comfortably in bigint range, and
# says what it's for if anyone greps for it later.
SCHEMA_APPLY_LOCK_KEY = zlib.crc32(b"principle_rf_engineer_agent:apply_schema")


def _redact(database_url: str) -> str:
    """Drop the credentials from a connection string, keeping only what's
    safe to print (scheme/host/port/dbname) -- issue #367: the full URL,
    password included, was landing in stdout here."""
    parts = urlsplit(database_url)
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname or ''}{port}{parts.path}"


def render_schema() -> str:
    """Read schema.sql and substitute its `${EMBEDDING_DIM_*}` placeholders."""
    template = Template(SCHEMA_PATH.read_text(encoding="utf-8"))
    return template.substitute(
        EMBEDDING_DIM_EXTERNAL=os.environ.get("EMBEDDING_DIM_EXTERNAL", "1536"),
        EMBEDDING_DIM_LOCAL=os.environ.get("EMBEDDING_DIM_LOCAL", "1536"),
    )


def apply_schema(database_url: str) -> None:
    """Render schema.sql and execute it against `database_url`.

    Wrapped in a `pg_advisory_lock`/`pg_advisory_unlock` pair keyed on
    `SCHEMA_APPLY_LOCK_KEY` (issue #399): without it, two concurrent
    invocations -- e.g. two worktrees each applying their own copy of
    schema.sql around the same time -- can interleave their DDL against the
    same database instead of one finishing before the other starts. That's
    not hypothetical: it's the exact failure mode behind a real
    schema-drift incident this session, caught only later via a git merge.
    The lock makes a second concurrent call wait for the first to finish
    rather than race it. `pg_advisory_lock` is session-scoped, not
    transaction-scoped -- it outlives autocommit's per-statement
    transactions -- so the `finally` unlock is what actually releases it;
    without it, a failed apply would leave the lock held until the
    connection closes instead of releasing it immediately.
    """
    sql = render_schema()
    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_APPLY_LOCK_KEY,))
        try:
            cur.execute(sql)
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_APPLY_LOCK_KEY,))


if __name__ == "__main__":
    load_dotenv()
    apply_schema(os.environ["DATABASE_URL"])
    print(f"Applied {SCHEMA_PATH} to {_redact(os.environ['DATABASE_URL'])}")
