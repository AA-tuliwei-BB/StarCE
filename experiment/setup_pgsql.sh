#!/usr/bin/env bash
set -euo pipefail

# postgres -D $PSQL_DATA_DIRECTORY &

# ===== 配置区：按需修改 =====
# Postgres 连接信息
PG_HOST="127.0.0.1"
PG_PORT="5432"
PG_USER="postgres"
PG_PASSWORD=""

# 目标数据库名
PG_DB_STATS="stats"
PG_DB_IMDB="imdb"

# SafeBound 脚本路径
SAFEBOUND_DIR="../methods/SafeBound"
STATS_SCRIPT="CreateStatsBenchmark.bash"
IMDB_SCRIPT="CreateJOBBenchmark.bash"
# ===== 配置区结束 =====

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

echo "==> 导入 STATS 数据库"
ensure_db "${PG_DB_STATS}"
(
  cd "${SAFEBOUND_DIR}"
  bash "${STATS_SCRIPT}"
)

echo "==> 导入 IMDB 数据库"
ensure_db "${PG_DB_IMDB}"
(
  cd "${SAFEBOUND_DIR}"
  bash "${IMDB_SCRIPT}"
)
