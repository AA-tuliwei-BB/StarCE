#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DUCKDB_BIN="${1:-${PROJECT_ROOT}/duckdb/build/release/duckdb}"
SCHEMA_SQL="${PROJECT_ROOT}/Benchmark/STATS/stats_duckDB.sql"
DATA_DIR="${PROJECT_ROOT}/Benchmark/STATS"
DB_FILE="${PROJECT_ROOT}/Benchmark/duckdb/stats.db"

if [ ! -f "${DUCKDB_BIN}" ]; then
    echo "Error: DuckDB binary not found: ${DUCKDB_BIN}"
    echo "Please build first: cd ${PROJECT_ROOT} && ./build.sh"
    echo "Or specify path: $0 <path/to/duckdb>"
    exit 1
fi

if [ -f "${DB_FILE}" ]; then
    echo "stats.db already exists (${DB_FILE}), delete to rebuild:"
    echo "  rm ${DB_FILE}"
    exit 0
fi

echo "=== Create STATS DuckDB database ==="
echo "Schema: ${SCHEMA_SQL}"
echo "Data: ${DATA_DIR}"
echo "Output: ${DB_FILE}"

mkdir -p "$(dirname "$DB_FILE")"

# Create table structure
"${DUCKDB_BIN}" "${DB_FILE}" < "${SCHEMA_SQL}"
echo "Table structure created"

# STATS table name list (aligned with benchmark/stats-ceb/starce.db)
TABLES=(badges comments postHistory postLinks posts tags users votes)

# Import CSV (STATS CSV has HEADER)
for tbl in "${TABLES[@]}"; do
    csv="${DATA_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        echo "Importing ${tbl}..."
        "${DUCKDB_BIN}" "${DB_FILE}" -c "COPY ${tbl} FROM '${csv}' (HEADER, DELIMITER ',');"
    else
        echo "Warning: ${csv} not found, skipping"
    fi
done

echo ""
echo "=== Done ==="
echo "File: ${DB_FILE}"
echo "Size: $(du -h "${DB_FILE}" | cut -f1)"
