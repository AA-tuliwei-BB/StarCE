#!/bin/bash

# This script handles:
# 1. Verify stats.db and imdb.db exist under Benchmark/duckdb/
# 2. Copy duckdb and starce executables to running_space

set -euo pipefail

MODE="${1:-release}"
case "${MODE}" in
    debug|release)
        ;;
    *)
        echo "Error: first argument must be debug or release（current: ${MODE}）"
        echo "Usage: $0 [debug|release]"
        exit 1
        ;;
esac

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNNING_SPACE_DIR="${SCRIPT_DIR}/running_space"
if [ "${MODE}" = "debug" ]; then
    DUCKDB_SOURCE="${SCRIPT_DIR}/../duckdb/build/debug/duckdb"
    STARCE_SOURCE="${SCRIPT_DIR}/../build-debug/starce"
else
    DUCKDB_SOURCE="${SCRIPT_DIR}/../duckdb/build/release/duckdb"
    STARCE_SOURCE="${SCRIPT_DIR}/../build/starce"
fi

# 1. Check if duckdb source file exists
if [ ! -f "$DUCKDB_SOURCE" ]; then
    echo "Error: duckdb executable not found: $DUCKDB_SOURCE"
    exit 1
fi

# 1.1 Print mode and source paths
echo "Initializing experiment environment, mode: ${MODE}"
echo "duckdb source: ${DUCKDB_SOURCE}"
echo "starce source: ${STARCE_SOURCE}"

# 2. Create running_space directory (if not exists)
mkdir -p "$RUNNING_SPACE_DIR"

# 3. Copy duckdb to running_space
echo "Copying duckdb to running_space..."
cp "$DUCKDB_SOURCE" "$RUNNING_SPACE_DIR/duckdb"
chmod +x "$RUNNING_SPACE_DIR/duckdb"

# 3.1. Copy starce to running_space
echo "Copying starce to running_space..."
if [ ! -f "$STARCE_SOURCE" ]; then
    echo "Error: starce executable not found: $STARCE_SOURCE"
    exit 1
fi
cp "$STARCE_SOURCE" "$RUNNING_SPACE_DIR/starce"
chmod +x "$RUNNING_SPACE_DIR/starce"

# 4. Verify database files under Benchmark/duckdb
echo "==== Verifying database files ===="
if [ ! -f "${PROJECT_ROOT}/Benchmark/duckdb/stats.db" ]; then
    echo "Error: Benchmark/duckdb/stats.db does not exist"
    echo "Please create first: bash setup/duckdb/create_stats_db.sh"
    exit 1
fi
echo "stats.db ready: ${PROJECT_ROOT}/Benchmark/duckdb/stats.db"

if [ ! -f "${PROJECT_ROOT}/Benchmark/duckdb/imdb.db" ]; then
    echo "Error: Benchmark/duckdb/imdb.db does not exist"
    echo "Please create first: bash setup/duckdb/create_imdb_db.sh"
    exit 1
fi
echo "imdb.db ready: ${PROJECT_ROOT}/Benchmark/duckdb/imdb.db"

# 5. Create dummy files
echo "Creating dummy files..."
touch "${RUNNING_SPACE_DIR}/dummy_query.sql"
touch "${RUNNING_SPACE_DIR}/dummy_result.txt"

echo "Done! duckdb and starce executables have been copied to the running_space directory"
echo ".db files located under Benchmark/duckdb/ directory"

