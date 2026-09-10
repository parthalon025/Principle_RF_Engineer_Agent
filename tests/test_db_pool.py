"""Tests for db/pool.py -- the shared connection pool and the bounded
lock/statement timeouts behind `designs.db.get_connection` and
`knowledge.db.get_connection` (issue #406).

*In plain terms: a "connection" is one open line from this program to the
Postgres database. Opening one is slow and Postgres only allows about 100
at once, so this project's many-parallel-agents working style can run the
server out of them. A "pool" keeps a small number of lines open and lends
them out, and a "timeout" is a promise that a caller waiting for a busy
row gives up with a clear error instead of waiting forever.*

Almost everything here needs a real Postgres: what issue #406 asks to be
proved -- that a second checkout reuses the first one's backend, that a
lock wait is actually bounded, that an exhausted pool refuses instead of
hanging -- are all behaviours of a real server under real concurrency,
which no mock can produce. Issue #389's own `TestFetchRequirementsRowLock`
(tests/test_requirement_targets.py) is the direct precedent, and this
module reuses its `DATABASE_URL` connectivity probe verbatim so the suite
skips with a stated reason where no database is reachable rather than
failing.

The one exception is `TestPoolConfiguration` below, which reads the
defaults out of the module and needs no server at all.
"""

from __future__ import annotations

import os
import threading
import uuid

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg_pool import PoolTimeout

from db import pool as db_pool
from designs import db as designs_db
from knowledge import db as knowledge_db

load_dotenv()


# ---------------------------------------------------------------------------
# No database needed: the pool's own configuration surface.
# ---------------------------------------------------------------------------


class TestPoolConfiguration:
    def test_default_timeouts_are_bounded_and_nonzero(self):
        """A `0` timeout means "wait forever" to Postgres -- exactly the
        indefinite hang issue #406 exists to remove -- so neither default
        may be 0, and neither may be so large that "stuck" is
        indistinguishable from "slow"."""
        assert 0 < db_pool.DEFAULT_LOCK_TIMEOUT_MS <= 60_000
        assert 0 < db_pool.DEFAULT_STATEMENT_TIMEOUT_MS <= 300_000

    def test_default_pool_size_stays_well_under_postgres_default_ceiling(self):
        """Postgres's own default `max_connections` is 100, shared by every
        agent process at once. A per-process pool of a handful of
        connections leaves room for dozens of concurrent agents; one sized
        in the tens would not."""
        assert 0 <= db_pool.DEFAULT_MIN_SIZE <= db_pool.DEFAULT_MAX_SIZE
        assert db_pool.DEFAULT_MAX_SIZE <= 10

    def test_pool_settings_read_the_environment_at_pool_creation_time(self, monkeypatch):
        """The knobs are read when the pool is built, not imported once at
        module import -- otherwise a test (or an operator) could never
        change them without reloading the module."""
        monkeypatch.setenv("RF_DB_POOL_MAX_SIZE", "7")
        monkeypatch.setenv("RF_DB_LOCK_TIMEOUT_MS", "250")
        monkeypatch.setenv("RF_DB_STATEMENT_TIMEOUT_MS", "1500")
        monkeypatch.setenv("RF_DB_POOL_TIMEOUT_S", "2.5")

        settings = db_pool.pool_settings()

        assert settings.max_size == 7
        assert settings.lock_timeout_ms == 250
        assert settings.statement_timeout_ms == 1500
        assert settings.checkout_timeout_s == 2.5

    def test_a_non_numeric_override_is_refused_by_name(self, monkeypatch):
        """A typo in the environment must name itself and say what a good
        value looks like, not surface later as an unexplained pool timeout
        when every checkout fails its configuration step."""
        monkeypatch.setenv("RF_DB_LOCK_TIMEOUT_MS", "five seconds")
        with pytest.raises(ValueError, match="RF_DB_LOCK_TIMEOUT_MS.*milliseconds"):
            db_pool.pool_settings()

    def test_a_non_numeric_seconds_override_is_refused_in_its_own_units(self, monkeypatch):
        """The whole-number knobs and the seconds-valued one share one
        parsing helper, so this proves that helper still tells them apart:
        a bad `RF_DB_POOL_TIMEOUT_S` must be described in seconds, not
        rejected as "a whole number" it was never meant to be. `"2.5"` is a
        *valid* value for this knob and an invalid one for the others,
        which is exactly the distinction that would rot if the two ever
        drifted apart."""
        monkeypatch.setenv("RF_DB_POOL_TIMEOUT_S", "half a minute")
        with pytest.raises(ValueError, match="RF_DB_POOL_TIMEOUT_S.*seconds"):
            db_pool.pool_settings()


# ---------------------------------------------------------------------------
# DB-backed: everything issue #406 asks to be proved with real concurrency.
# Same probe as tests/test_requirement_targets.py's own #389 lock test.
# ---------------------------------------------------------------------------

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://rf:rf_dev_password@localhost:5432/rfengineer"
)


def _database_reachable() -> bool:
    try:
        with psycopg.connect(_TEST_DATABASE_URL, connect_timeout=3):
            return True
    except psycopg.OperationalError:
        return False


_DB_REACHABLE = _database_reachable()

_needs_db = pytest.mark.skipif(
    not _DB_REACHABLE,
    reason=f"no reachable Postgres at {_TEST_DATABASE_URL.split('@')[-1]!r} in this sandbox",
)


@pytest.fixture
def fresh_pool(monkeypatch):
    """Drop any pool this process already built, so the test's own
    environment overrides take effect, and drop it again afterwards so the
    next test does not inherit this one's sizing or timeouts."""
    monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
    db_pool.reset_pool()
    yield
    db_pool.reset_pool()


def _backend_pid(conn: psycopg.Connection) -> int:
    """The server-side process id serving this connection -- the one thing
    that says "same physical connection" rather than "same Python
    object"."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_backend_pid()")
        row = cur.fetchone()
    assert row is not None
    return row[0]


@_needs_db
@pytest.mark.usefixtures("fresh_pool")
class TestPoolReuse:
    def test_two_sequential_checkouts_reuse_one_backend_connection(self):
        """The headline of issue #406's user story 1. Before the pool, each
        `get_connection()` opened a brand-new backend and each `close()`
        threw it away; two calls meant two connects against Postgres's
        fixed ceiling. Proved two ways at once, because either alone could
        be a coincidence: the same server-side backend pid serves both, and
        the pool reports having opened exactly one connection in total."""
        first = designs_db.get_connection()
        first_pid = _backend_pid(first)
        first.close()

        second = designs_db.get_connection()
        second_pid = _backend_pid(second)
        second.close()

        assert second_pid == first_pid
        assert db_pool.get_pool().get_stats()["connections_num"] == 1

    def test_designs_and_knowledge_share_one_pool(self):
        """Issue #406 asks for *a single* shared connection pool -- exactly
        one, across both low-level modules, not one each. Two pools would
        double this process's share of the connection ceiling while
        reporting healthy stats in both."""
        conn = designs_db.get_connection()
        pid = _backend_pid(conn)
        conn.close()

        other = knowledge_db.get_connection()
        other_pid = _backend_pid(other)
        other.close()

        assert other_pid == pid
        assert db_pool.get_pool().get_stats()["connections_num"] == 1

    def test_close_is_a_checkin_not_a_disconnect(self):
        """Issue #406's user story 4: the ~27 existing call sites keep
        their `conn = get_connection() ... conn.close()` shape, and that
        `close()` must return the connection to the pool rather than drop
        it. If it really disconnected, the connection would be unusable
        afterwards AND the pool would have to open a second one."""
        conn = designs_db.get_connection()
        conn.close()

        assert not conn.closed
        assert db_pool.get_pool().get_stats()["pool_available"] == 1

    def test_a_checked_in_connection_carries_no_open_transaction(self):
        """`designs.service.read_design` closes without committing or
        rolling back -- harmless when `close()` really disconnected, but a
        pooled connection handed on with an open transaction would leak
        that transaction's locks and snapshot into the next caller."""
        conn = designs_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()  # deliberately no commit/rollback, matching read_design

        reused = designs_db.get_connection()
        try:
            assert reused.pgconn.transaction_status == psycopg.pq.TransactionStatus.IDLE
        finally:
            reused.close()


@_needs_db
class TestCheckoutTimeouts:
    def test_a_checked_out_connection_carries_the_configured_timeouts(self, monkeypatch):
        """Issue #406's user stories 2 and 3: every caller gets the bounded
        wait automatically, without setting it itself. Read back from the
        server, not from our own configuration, so this fails if the
        setting never actually reaches Postgres."""
        monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
        monkeypatch.setenv("RF_DB_LOCK_TIMEOUT_MS", "1500")
        monkeypatch.setenv("RF_DB_STATEMENT_TIMEOUT_MS", "4000")
        db_pool.reset_pool()
        try:
            conn = designs_db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SHOW lock_timeout")
                    lock_timeout = cur.fetchone()[0]
                    cur.execute("SHOW statement_timeout")
                    statement_timeout = cur.fetchone()[0]
            finally:
                conn.close()
        finally:
            db_pool.reset_pool()

        assert lock_timeout == "1500ms"
        assert statement_timeout == "4s"

    def test_the_timeouts_survive_a_callers_rollback(self, monkeypatch):
        """A plain `SET` issued inside a transaction is undone when that
        transaction rolls back -- and `designs.service`'s wrappers roll
        back on every rejected write. A timeout that quietly reverted to
        "wait forever" on the first rollback would leave the very callers
        that hit contention unprotected."""
        monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
        monkeypatch.setenv("RF_DB_LOCK_TIMEOUT_MS", "1500")
        db_pool.reset_pool()
        try:
            conn = designs_db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute("SHOW lock_timeout")
                    lock_timeout = cur.fetchone()[0]
            finally:
                conn.close()
        finally:
            db_pool.reset_pool()

        assert lock_timeout == "1500ms"

    def test_a_runaway_statement_is_cancelled_rather_than_left_running(self, monkeypatch):
        """Issue #406's user story 3, proved with teeth rather than with
        `SHOW`: a statement that outstays the deadline must actually be
        cancelled by the server. `pg_sleep` is the cheapest honest stand-in
        for a runaway query -- it holds the connection slot and returns
        nothing, which is exactly the failure mode."""
        monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
        monkeypatch.setenv("RF_DB_STATEMENT_TIMEOUT_MS", "300")
        db_pool.reset_pool()
        try:
            conn = designs_db.get_connection()
            try:
                with pytest.raises(psycopg.errors.QueryCanceled):
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_sleep(30)")
                conn.rollback()
            finally:
                conn.close()
        finally:
            db_pool.reset_pool()


@_needs_db
class TestLockTimeoutFires:
    """Issue #406's user story 2, proved the way issue #389 proved its own
    row lock: two real connections, one holding a `FOR UPDATE` lock, and a
    bounded wait on the other. A mock cannot produce a Postgres lock."""

    @pytest.fixture
    def design_id(self):
        """A real `designs` row to contend over. Written and cleaned up on
        a direct connection, deliberately not a pooled one -- the pool this
        test configures has a deliberately tiny lock timeout, and the
        fixture must not be subject to it."""
        conn = psycopg.connect(_TEST_DATABASE_URL, autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO designs (design_key, name, revision, status,
                                         requirements, architecture)
                    VALUES (%s, %s, %s, %s, '{}'::jsonb, '{}'::jsonb)
                    RETURNING id
                    """,
                    (
                        f"POOL-LOCK-{uuid.uuid4().hex[:8]}",
                        "Pool Lock Timeout Fixture Design",
                        "A",
                        "DRAFT",
                    ),
                )
                design_id = cur.fetchone()[0]
        finally:
            conn.close()

        yield design_id

        conn = psycopg.connect(_TEST_DATABASE_URL, autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM designs WHERE id = %s", (design_id,))
        finally:
            conn.close()

    def test_a_pooled_connection_gives_up_on_a_held_row_lock(self, design_id, monkeypatch):
        """The holder never releases inside the test's window. Before issue
        #406 the waiter blocked for as long as the holder held on -- with
        no way to tell "stuck" from "just slow". Now it must come back with
        Postgres's own `lock_timeout` error, well inside a window far
        shorter than any indefinite wait."""
        monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
        monkeypatch.setenv("RF_DB_LOCK_TIMEOUT_MS", "300")
        db_pool.reset_pool()

        holder = psycopg.connect(_TEST_DATABASE_URL)
        finished = threading.Event()
        raised: list[BaseException] = []
        try:
            with holder.cursor() as cur:
                cur.execute("SELECT id FROM designs WHERE id = %s FOR UPDATE", (design_id,))

            def _blocked_update():
                conn = designs_db.get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM designs WHERE id = %s FOR UPDATE", (design_id,))
                except BaseException as exc:  # noqa: BLE001 -- recorded, re-asserted below
                    raised.append(exc)
                finally:
                    conn.rollback()
                    conn.close()
                    finished.set()

            thread = threading.Thread(target=_blocked_update)
            thread.start()
            # 300 ms configured timeout; 5 s is generous room for the round
            # trip while still proving this is not an indefinite wait.
            assert finished.wait(timeout=5.0), "the pooled caller never gave up on the lock"
            thread.join()
        finally:
            holder.rollback()
            holder.close()
            db_pool.reset_pool()

        assert raised, "the pooled caller acquired a lock another connection was holding"
        assert isinstance(raised[0], psycopg.errors.LockNotAvailable)


@_needs_db
class TestPoolExhaustion:
    def test_a_caller_that_cannot_get_a_connection_fails_instead_of_hanging(self, monkeypatch):
        """Issue #406's user story 1, at the other end: when every pooled
        connection is already out, the next caller must be refused within a
        bounded wait -- graceful degradation -- rather than queueing
        forever behind whatever is holding them."""
        monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
        monkeypatch.setenv("RF_DB_POOL_MIN_SIZE", "0")
        monkeypatch.setenv("RF_DB_POOL_MAX_SIZE", "1")
        monkeypatch.setenv("RF_DB_POOL_TIMEOUT_S", "0.5")
        db_pool.reset_pool()

        held = designs_db.get_connection()
        try:
            with pytest.raises(PoolTimeout):
                designs_db.get_connection()
        finally:
            held.close()
            db_pool.reset_pool()
