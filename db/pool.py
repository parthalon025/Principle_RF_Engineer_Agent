"""One shared connection pool per process, and the bounded lock/statement
timeouts every connection checked out of it carries (issue #406).

*In plain terms: a "connection" is one open line from this program to the
Postgres database. Opening one takes real time, and the server only allows
about 100 at once across everything talking to it. This module keeps a
small number of lines open and lends them out instead of opening a fresh
one for every database call, and it stamps two deadlines on each one so a
caller that ends up waiting on a row another caller is editing gives up
with a clear error rather than waiting forever.*

Why this exists
---------------
This project's own working style pushes toward many parallel agents each
calling MCP tools that touch the database at the same time (CLAUDE.md's
meta-orchestrator pattern). Before this module, every one of the ~27 call
sites behind `designs.db.get_connection` / `knowledge.db.get_connection`
opened its own raw connection per call and threw it away on `close()`, so
rising parallelism raced Postgres's fixed connection ceiling with no
graceful degradation -- and a caller blocked on a lock held by another
agent waited indefinitely, with no way to tell "stuck" from "just slow".

Three guarantees, all of them bounded waits rather than refusals:

- **Reuse.** `close()` returns the connection to the pool instead of
  disconnecting, so a second call reuses the first call's backend.
- **A bounded lock wait.** `lock_timeout` -- how long a statement will
  wait for a row another transaction has locked before giving up. Exceeded
  -> Postgres's own `LockNotAvailable`, promptly and by name.
- **A bounded statement.** `statement_timeout` -- how long any single
  statement may run at all. A runaway query fails loudly instead of
  silently holding a connection slot forever.

Whether a caller retries after either is the caller's decision, not this
module's: issue #406 puts automatic retry-with-backoff explicitly out of
scope. This makes the failure bounded and clear; it does not paper over it.

What is deliberately NOT pooled
-------------------------------
`db/apply_schema.py` and one-off scripts keep opening direct connections.
They are not part of the many-parallel-agents pattern this addresses --
they run once, by hand, usually before anything else exists -- and
`apply_schema.py` in particular issues long DDL (index builds) that a
30-second `statement_timeout` would cut off mid-way.

Call-site contract
------------------
`checkout_connection()` hands back a genuine `psycopg.Connection`, and
`conn.close()` on it is a check-in. That is psycopg-pool's own
`close_returns=True` behaviour, not a wrapper of ours: the object is the
real thing, so `pgvector.psycopg.register_vector(conn)` and everything
else that type-checks a connection keeps working, and none of the existing
`conn = get_connection() ... conn.close()` call sites change.

Two consequences worth knowing:

- Do not call `close()` twice on one checkout. The first returns the
  connection to the pool; a second would then close it for real, out from
  under whoever holds it next. (`check` below makes that survivable -- a
  dead connection is detected and replaced at the next checkout instead of
  being handed out broken -- but it is still a bug at the call site.)
- `with conn:` does NOT check the connection back in. psycopg deliberately
  skips the close for a pooled connection, so a `with` block commits or
  rolls back and then leaks the checkout. No call site in this repo uses
  that shape; new ones should keep to `try/finally: conn.close()`.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

import psycopg
from psycopg_pool import ConnectionPool

# --- Defaults -------------------------------------------------------------
#
# Sizing. Postgres's own default `max_connections` is 100, shared by every
# agent process at once, so the number that matters is per-process. A
# maximum of 4 leaves room for roughly twenty concurrent agents at full
# stretch while being more than any single agent needs: one MCP tool call
# holds exactly one connection (issue #406 leaves per-call connection count
# alone), so 4 is headroom for overlapping calls in one process, not a
# per-agent allocation. A minimum of 0 means an idle process eventually
# gives its connections back to the server instead of sitting on one
# forever -- the same pressure, at rest, that the ceiling problem is about.
DEFAULT_MIN_SIZE = 0
DEFAULT_MAX_SIZE = 4

# Timeouts, in milliseconds because that is the unit Postgres stores these
# two settings in -- an integer here can never be a malformed interval.
#
# 5 s to wait for a locked row. Every `FOR UPDATE` in this repo
# (`designs.db.update_design_status`, `designs.requirement_targets.
# _fetch_requirements`) holds its lock across a read, a validation and one
# write -- milliseconds. 5 s is generous room for a legitimate holder and
# still far short of "indefinite".
DEFAULT_LOCK_TIMEOUT_MS = 5_000
# 30 s for any single statement. The slowest legitimate statements here are
# a pgvector nearest-neighbour search over the chunk index and the
# per-statement work inside an ingest's `executemany` -- all well under a
# second in practice. (Schema DDL is the exception, and `apply_schema.py`
# is deliberately not pooled.)
DEFAULT_STATEMENT_TIMEOUT_MS = 30_000

# How long a caller waits for a free connection before being refused.
# Matched to the statement timeout above: the worst legitimate wait is one
# full-length statement ahead of you in the queue, so a caller that waits
# longer than that is queued behind something that has already failed its
# own deadline.
DEFAULT_CHECKOUT_TIMEOUT_S = 30.0

# Bounds one *connect attempt* by the pool's background worker, so a
# black-holed host costs seconds rather than the operating system's own
# multi-minute TCP timeout. Not environment-configurable: it protects the
# pool's internals, and a caller is already bounded by the checkout
# timeout above regardless of what this is.
CONNECT_TIMEOUT_S = 10

ENV_MIN_SIZE = "RF_DB_POOL_MIN_SIZE"
ENV_MAX_SIZE = "RF_DB_POOL_MAX_SIZE"
ENV_CHECKOUT_TIMEOUT_S = "RF_DB_POOL_TIMEOUT_S"
ENV_LOCK_TIMEOUT_MS = "RF_DB_LOCK_TIMEOUT_MS"
ENV_STATEMENT_TIMEOUT_MS = "RF_DB_STATEMENT_TIMEOUT_MS"

# `set_config(name, value, is_local => false)` is `SET name = value` in
# function form: same session-level effect, but it takes its arguments as
# ordinary parameters, so nothing string-formats a value into SQL here.
# Run with autocommit on (see `_configure_at_checkout`), which is what
# makes the setting survive a caller's later `rollback()` -- a plain `SET`
# issued inside a transaction is undone when that transaction rolls back,
# and `designs.service`'s wrappers roll back on every rejected write.
_SET_TIMEOUTS_SQL = (
    "SELECT set_config('lock_timeout', %s, false), set_config('statement_timeout', %s, false)"
)


@dataclass(frozen=True)
class PoolSettings:
    """The pool's sizing and timeouts, resolved from the environment at the
    moment the pool is built. Read via `pool_settings()`."""

    min_size: int
    max_size: int
    checkout_timeout_s: float
    lock_timeout_ms: int
    statement_timeout_ms: int


def _int_from_env(name: str, default: int) -> int:
    """`os.environ[name]` as an int, or `default` if unset. A value that is
    not a number raises naming the variable -- otherwise a typo surfaces
    much later as an unexplained pool timeout, because every checkout would
    fail its configuration step and the pool would keep retrying."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None


def _float_from_env(name: str, default: float) -> float:
    """`_int_from_env`'s counterpart for a seconds-valued setting."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number of seconds, got {raw!r}") from None


def pool_settings() -> PoolSettings:
    """Resolve the pool's configuration from the environment.

    Called when the pool is built, not once at import, so an operator (or a
    test) can change a setting and rebuild via `reset_pool()` without
    reloading this module.
    """
    return PoolSettings(
        min_size=_int_from_env(ENV_MIN_SIZE, DEFAULT_MIN_SIZE),
        max_size=_int_from_env(ENV_MAX_SIZE, DEFAULT_MAX_SIZE),
        checkout_timeout_s=_float_from_env(ENV_CHECKOUT_TIMEOUT_S, DEFAULT_CHECKOUT_TIMEOUT_S),
        lock_timeout_ms=_int_from_env(ENV_LOCK_TIMEOUT_MS, DEFAULT_LOCK_TIMEOUT_MS),
        statement_timeout_ms=_int_from_env(ENV_STATEMENT_TIMEOUT_MS, DEFAULT_STATEMENT_TIMEOUT_MS),
    )


def _make_checkout_configurer(settings: PoolSettings) -> Callable[[psycopg.Connection], None]:
    """Build the pool's `check` callback: the one round trip that runs on
    every checkout.

    It does two jobs at once, deliberately. It stamps this checkout's
    timeouts on the session -- issue #406's "applied when a connection is
    checked out", so no caller has to remember to -- and, because it is a
    real query, it doubles as the liveness probe psycopg-pool's `check`
    hook exists for: a connection that died while sitting idle (a server
    restart, an idle-session reaper) raises here, inside the pool's own
    retry loop, so the pool discards it and hands out a working one instead
    of handing out a corpse.
    """

    def _configure_at_checkout(conn: psycopg.Connection) -> None:
        conn.autocommit = True
        try:
            conn.execute(
                _SET_TIMEOUTS_SQL,
                (str(settings.lock_timeout_ms), str(settings.statement_timeout_ms)),
            )
        finally:
            conn.autocommit = False

    return _configure_at_checkout


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _create_pool() -> ConnectionPool:
    """Build the pool against `DATABASE_URL`.

    `os.environ["DATABASE_URL"]` is read here, per pool, rather than at
    import: a missing `DATABASE_URL` still raises `KeyError` at the moment
    a caller first asks for a connection, exactly as the direct
    `psycopg.connect(os.environ["DATABASE_URL"])` this replaces did.
    """
    settings = pool_settings()
    return ConnectionPool(
        os.environ["DATABASE_URL"],
        kwargs={"connect_timeout": CONNECT_TIMEOUT_S},
        min_size=settings.min_size,
        max_size=settings.max_size,
        timeout=settings.checkout_timeout_s,
        # The whole point: `conn.close()` at a call site becomes a check-in
        # rather than a disconnect, so none of the ~27 existing call sites
        # change (issue #406, user story 4).
        close_returns=True,
        check=_make_checkout_configurer(settings),
        name="rf-engineer",
        # Stated explicitly: psycopg-pool warns that the default flips to
        # False in a future release.
        open=True,
    )


def get_pool() -> ConnectionPool:
    """The one pool for this process, built on first use.

    Lazy rather than built at import so that importing `designs.db` or
    `knowledge.db` -- which happens in tests and tools that never touch
    Postgres -- neither requires `DATABASE_URL` nor opens a socket.
    """
    global _pool
    pool = _pool
    if pool is not None:
        return pool
    with _pool_lock:
        if _pool is None:
            _pool = _create_pool()
        return _pool


def checkout_connection() -> psycopg.Connection:
    """Check a connection out of the shared pool.

    The returned connection already carries this pool's `lock_timeout` and
    `statement_timeout`. `conn.close()` returns it; see this module's
    docstring for the two things not to do with it.

    Raises `psycopg_pool.PoolTimeout` if every pooled connection is in use
    and none frees up within the checkout timeout -- the graceful
    degradation issue #406 asks for, in place of queueing indefinitely.
    """
    return get_pool().getconn()


def reset_pool() -> None:
    """Close the current pool and forget it, so the next checkout builds a
    fresh one from the current environment.

    Support for tests and fixtures that need a differently-sized or
    differently-timed pool; nothing in production calls it. Any connection
    still checked out when this runs is closed for real when its holder
    returns it, not yanked away mid-statement.
    """
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.close()
