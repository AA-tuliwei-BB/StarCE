#!/usr/bin/env bash
set -euo pipefail

# postgres -D $PSQL_DATA_DIRECTORY &

# ===== Configuration: modify as needed =====
# Postgres connection info
PG_HOST="127.0.0.1"
PG_PORT="5432"
PG_USER="postgres"
PG_PASSWORD=""

# Target database name
PG_DB_STATS="stats"
PG_DB_IMDB="imdb"

# SafeBound script path
SAFEBOUND_DIR="../methods/SafeBound"
STATS_SCRIPT="CreateStatsBenchmark.bash"
IMDB_SCRIPT="CreateJOBBenchmark.bash"
# ===== Configuration end =====

export PGHOST="${PG_HOST}"
export PGPORT="${PG_PORT}"
export PGUSER="${PG_USER}"
export PGPASSWORD="${PG_PASSWORD}"

ensure_db() {
  local db_name="$1"
  if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | grep -q 1; then
    createdb "${db_name}"
  fi
}

echo "==> Import STATS database"
ensure_db "${PG_DB_STATS}"
(
  cd "${SAFEBOUND_DIR}"
  bash "${STATS_SCRIPT}"
)

echo "==> Import IMDB database"
ensure_db "${PG_DB_IMDB}"
(
  cd "${SAFEBOUND_DIR}"
  bash "${IMDB_SCRIPT}"
)
