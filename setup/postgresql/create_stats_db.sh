#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
export PGHOST PGPORT PGUSER

SCHEMA_SQL="${PROJECT_ROOT}/Benchmark/STATS/stats.sql"
DATA_DIR="${PROJECT_ROOT}/Benchmark/STATS"
PSQL="psql"

echo "=== Create stats database (STATS-CEB) ==="

if ! ${PSQL} -c "SELECT 1;" postgres > /dev/null 2>&1; then
    echo "Error: Cannot connect to PostgreSQL (host=${PGHOST} port=${PGPORT} user=${PGUSER})"
    exit 1
fi

if ${PSQL} -lqt | cut -d \| -f 1 | grep -qw stats; then
    table_count=$(${PSQL} -d stats -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
    echo "stats database already exists (${table_count} tables), skipping"
    exit 0
fi

echo "Creating stats database..."
createdb stats

echo "Creating table structure..."
${PSQL} -d stats -f "${SCHEMA_SQL}"

# STATS 8 tables, CSV has HEADER
TABLES=(badges comments postHistory postLinks posts tags users votes)

for tbl in "${TABLES[@]}"; do
    csv="${DATA_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        echo "Importing ${tbl}..."
        ${PSQL} -d stats -c "\copy ${tbl} FROM '${csv}' WITH CSV HEADER DELIMITER ',';"
    else
        echo "Warning: ${csv} not found, skipping"
    fi
done

echo "Creating indexes..."
${PSQL} -d stats <<'SQL'
CREATE INDEX IF NOT EXISTS badges_userid_idx ON badges(userid);
CREATE INDEX IF NOT EXISTS comments_userid_idx ON comments(userid);
CREATE INDEX IF NOT EXISTS comments_postid_idx ON comments(postid);
CREATE INDEX IF NOT EXISTS posthistory_userid_idx ON posthistory(userid);
CREATE INDEX IF NOT EXISTS posthistory_postid_idx ON posthistory(postid);
CREATE INDEX IF NOT EXISTS postlinks_postid_idx ON postlinks(postid);
CREATE INDEX IF NOT EXISTS postlinks_relatedpostid_idx ON postlinks(relatedpostid);
CREATE INDEX IF NOT EXISTS posts_owneruserid_idx ON posts(owneruserid);
CREATE INDEX IF NOT EXISTS votes_userid_idx ON votes(userid);
CREATE INDEX IF NOT EXISTS votes_postid_idx ON votes(postid);
CREATE INDEX IF NOT EXISTS tags_id_idx ON tags(id);
SQL

echo "ANALYZE..."
${PSQL} -d stats -c "ANALYZE;"

echo ""
echo "=== stats database created ==="
${PSQL} -d stats -c "\dt"
