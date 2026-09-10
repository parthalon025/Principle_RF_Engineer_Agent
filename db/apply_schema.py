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
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

import psycopg
from dotenv import load_dotenv

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


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
    sql = render_schema()
    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)


if __name__ == "__main__":
    load_dotenv()
    apply_schema(os.environ["DATABASE_URL"])
    print(f"Applied {SCHEMA_PATH} to {_redact(os.environ['DATABASE_URL'])}")
