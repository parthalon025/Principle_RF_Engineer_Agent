#!/bin/sh
# Runs once, at first container init (docker-entrypoint-initdb.d), against a
# fresh Postgres data volume. Templates schema.sql.template's
# ${EMBEDDING_DIM_EXTERNAL} / ${EMBEDDING_DIM_LOCAL} placeholders from this
# container's environment (docker-compose.yml passes them through, defaulting
# to 1536 each -- see db/apply_schema.py for the equivalent step used against
# an already-running Postgres instead of a fresh container).
set -e

EMBEDDING_DIM_EXTERNAL="${EMBEDDING_DIM_EXTERNAL:-1536}"
EMBEDDING_DIM_LOCAL="${EMBEDDING_DIM_LOCAL:-1536}"

sed \
  -e "s/\${EMBEDDING_DIM_EXTERNAL}/${EMBEDDING_DIM_EXTERNAL}/g" \
  -e "s/\${EMBEDDING_DIM_LOCAL}/${EMBEDDING_DIM_LOCAL}/g" \
  /docker-entrypoint-initdb.d/schema.sql.template \
  | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
