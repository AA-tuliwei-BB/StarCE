#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DUCKDB_BIN="${1:-${PROJECT_ROOT}/duckdb/build/release/duckdb}"
SCHEMA_SQL="${PROJECT_ROOT}/Benchmark/IMDB/imdb_schema.sql"
DATA_DIR="${PROJECT_ROOT}/Benchmark/IMDB"
DB_FILE="${PROJECT_ROOT}/Benchmark/duckdb/imdb.db"

if [ ! -f "${DUCKDB_BIN}" ]; then
    echo "Error: DuckDB binary not found: ${DUCKDB_BIN}"
    echo "Please build first: cd ${PROJECT_ROOT} && ./build.sh"
    echo "Or specify path: $0 <path/to/duckdb>"
    exit 1
fi

if [ -f "${DB_FILE}" ]; then
    echo "imdb.db already exists (${DB_FILE}), delete to rebuild:"
    echo "  rm ${DB_FILE}"
    exit 0
fi

echo "=== Create IMDB DuckDB database ==="
echo "Schema: ${SCHEMA_SQL}"
echo "Data: ${DATA_DIR}"
echo "Output: ${DB_FILE}"

mkdir -p "$(dirname "$DB_FILE")"

# Create table structure
"${DUCKDB_BIN}" "${DB_FILE}" < "${SCHEMA_SQL}"
echo "Table structure created"

# Complete 21 IMDB tables
TABLES=(aka_name aka_title cast_info char_name comp_cast_type company_name
        company_type complete_cast info_type keyword kind_type link_type
        movie_companies movie_info movie_info_idx movie_keyword movie_link
        name person_info role_type title)

success=0
skipped=0
for tbl in "${TABLES[@]}"; do
    csv="${DATA_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        echo "Importing ${tbl}..."
        # IMDB CSV has no HEADER
        "${DUCKDB_BIN}" "${DB_FILE}" -c "COPY ${tbl} FROM '${csv}' (DELIMITER ',');"
        success=$((success + 1))
    else
        echo "Warning: ${csv} not found, skipping ${tbl}"
        skipped=$((skipped + 1))
    fi
done

echo ""
echo "=== Done ==="
echo "File: ${DB_FILE}"
echo "Size: $(du -h "${DB_FILE}" | cut -f1)"
echo "Imported: ${success} tables, Skipped: ${skipped} tables"
if [ ${skipped} -gt 0 ]; then
    echo "Warning: ${skipped} tables were not imported, please ensure IMDB data is initialized:"
    echo "  bash setup/dataset/init_imdb.sh"
fi
