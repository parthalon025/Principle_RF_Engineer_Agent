"""Database infrastructure shared by every package that talks to Postgres.

`schema.sql` (the tables), `apply_schema.py` (applying them) and
`docker-init.sh` already lived here; `pool.py` (issue #406) joins them as
the one process-wide connection pool that `designs/db.py` and
`knowledge/db.py` both check connections out of.

It lives here rather than inside either of those packages because neither
can own a module the other imports without inventing a dependency between
two peers -- `designs` and `knowledge` are siblings, and this is the piece
underneath both of them.
"""
