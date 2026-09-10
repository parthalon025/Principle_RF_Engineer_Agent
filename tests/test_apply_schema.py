"""Tests for `db/apply_schema.py`.

`render_schema`/`_redact` are pure string manipulation and would be cheap to
test directly, but the one behaviour that actually matters here --
`apply_schema` serializing concurrent invocations via a `pg_advisory_lock`
(issue #399) -- can only be proven against a real Postgres: a pure-function
test cannot reproduce a database-level lock blocking a second session. So,
mirroring issue #390's `TestFetchRequirementsRowLock` (`tests/
test_requirement_targets.py`) and test_element_alphabet.py's identical
`pytest.mark.skipif` pattern, this file is guarded by a module-level
`DATABASE_URL` connectivity probe and skips cleanly when no Postgres is
reachable rather than mocking what the acceptance criteria explicitly asks
to prove against a real database.
"""

from __future__ import annotations

import os
import threading
from urllib.parse import urlsplit

import psycopg
import pytest
from dotenv import load_dotenv

from db.apply_schema import SCHEMA_APPLY_LOCK_KEY, apply_schema

load_dotenv()

_TEST_DATABASE_URL = os.environ.get(
    # 127.0.0.1, not localhost (99d6744): on Windows+Docker Desktop,
    # `localhost` resolves to `::1` first and psycopg's connect() has no
    # default timeout, so a dead IPv6 attempt can stall for seconds. This
    # test opens multiple concurrent connections across threads with
    # 0.5s/10s wait windows to prove lock-blocking behavior -- exactly the
    # concurrent-load scenario that stall would masquerade as a hang in.
    "DATABASE_URL",
    "postgresql://rf:rf_dev_password@127.0.0.1:5432/rfengineer",
)


def _redacted(database_url: str) -> str:
    """Host/port/dbname only, for a skip-reason message -- issue #367:
    the full URL, password included, was landing in test output."""
    parts = urlsplit(database_url)
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname or ''}{port}{parts.path}"


def _database_reachable() -> bool:
    try:
        with psycopg.connect(_TEST_DATABASE_URL, connect_timeout=3):
            return True
    except psycopg.OperationalError:
        return False


_DB_REACHABLE = _database_reachable()


@pytest.mark.skipif(
    not _DB_REACHABLE,
    reason=f"no reachable Postgres at {_redacted(_TEST_DATABASE_URL)!r} in this sandbox",
)
class TestApplySchemaAdvisoryLock:
    """The core issue #399 regression test. Without the advisory lock,
    two concurrent `apply_schema` calls have nothing forcing one to finish
    before the other starts -- they'd race their DDL against the same
    database instead of serializing. Proving that needs two real,
    concurrent connections: one to hold the lock, one to attempt
    `apply_schema` and observe whether it blocks."""

    def test_apply_schema_blocks_while_the_lock_is_held_elsewhere(self):
        holder = psycopg.connect(_TEST_DATABASE_URL, autocommit=True)
        unblocked = threading.Event()
        try:
            with holder.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_APPLY_LOCK_KEY,))

            def _blocked_apply():
                apply_schema(_TEST_DATABASE_URL)
                unblocked.set()

            thread = threading.Thread(target=_blocked_apply)
            thread.start()
            # apply_schema's own pg_advisory_lock call must block while
            # `holder` holds the same key -- a generous window to prove it
            # does NOT complete.
            assert not unblocked.wait(timeout=0.5)

            with holder.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_APPLY_LOCK_KEY,))

            # Released -- the blocked apply_schema call should now acquire
            # the lock, apply the (idempotent) schema, and finish quickly.
            assert unblocked.wait(timeout=10.0)
            thread.join()
        finally:
            holder.close()

    def test_apply_schema_releases_the_lock_on_success(self):
        """A well-behaved apply_schema must not leave the lock held after
        it returns -- otherwise every call after the first would hang."""
        apply_schema(_TEST_DATABASE_URL)

        probe = psycopg.connect(_TEST_DATABASE_URL, autocommit=True)
        try:
            with probe.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (SCHEMA_APPLY_LOCK_KEY,))
                (acquired,) = cur.fetchone()
                assert acquired is True, "apply_schema left its advisory lock held"
                cur.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_APPLY_LOCK_KEY,))
        finally:
            probe.close()
