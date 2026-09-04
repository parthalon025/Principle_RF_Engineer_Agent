import os

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def db_conn():
    """A real connection to the local Postgres, wrapped in a transaction
    that's rolled back on teardown so tests never leave data behind.

    Matches tests/test_touchstone.py's real-I/O-not-mocked philosophy,
    applied to the database instead of the filesystem.
    """
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def cleanup_documents():
    """Tracks document ids created via ingest_document (which commits its
    own connection, so db_conn's rollback-on-teardown doesn't apply) and
    deletes them afterward. Shared by tests/test_literature_corpus.py and
    tests/test_verification_corpus.py, both of which ingest real
    knowledge/corpus/ files end to end."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()
