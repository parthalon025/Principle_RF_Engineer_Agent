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
