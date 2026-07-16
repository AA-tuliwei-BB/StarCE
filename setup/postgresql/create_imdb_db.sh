#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
export PGHOST PGPORT PGUSER

SCHEMA_SQL="${PROJECT_ROOT}/Benchmark/IMDB/imdb_schema.sql"
DATA_DIR="${PROJECT_ROOT}/Benchmark/IMDB"
PSQL="psql"

# IMDB 21 tables, CSV has no HEADER
TABLES=(aka_name aka_title cast_info char_name comp_cast_type company_name
        company_type complete_cast info_type keyword kind_type link_type
        movie_companies movie_info movie_info_idx movie_keyword movie_link
        name person_info role_type title)

echo "=== Create IMDB series databases ==="

if ! ${PSQL} -c "SELECT 1;" postgres > /dev/null 2>&1; then
    echo "Error: Cannot connect to PostgreSQL (host=${PGHOST} port=${PGPORT} user=${PGUSER})"
    exit 1
fi

# -----------------------------------
# 1/4: imdb full database
# -----------------------------------
if ${PSQL} -lqt | cut -d \| -f 1 | grep -qw imdb; then
    echo "imdb already exists, skipping"
else
    echo ""
    echo "--- 1/4 Creating imdb (full, 21 tables) ---"
    createdb imdb
    ${PSQL} -d imdb -f "${SCHEMA_SQL}"

    for tbl in "${TABLES[@]}"; do
        csv="${DATA_DIR}/${tbl}.csv"
        if [ -f "${csv}" ]; then
            echo "  Importing ${tbl}..."
            ${PSQL} -d imdb -c "\copy ${tbl} FROM '${csv}' WITH CSV DELIMITER ',' ESCAPE '\';"
        else
            echo "  Warning: ${csv} not found, skipping"
        fi
    done

    echo "  Creating indexes..."
    ${PSQL} -d imdb <<'SQL'
CREATE INDEX IF NOT EXISTS aka_name_person_id_idx ON aka_name(person_id);
CREATE INDEX IF NOT EXISTS aka_title_movie_id_idx ON aka_title(movie_id);
CREATE INDEX IF NOT EXISTS cast_info_person_id_idx ON cast_info(person_id);
CREATE INDEX IF NOT EXISTS cast_info_movie_id_idx ON cast_info(movie_id);
CREATE INDEX IF NOT EXISTS complete_cast_movie_id_idx ON complete_cast(movie_id);
CREATE INDEX IF NOT EXISTS movie_companies_movie_id_idx ON movie_companies(movie_id);
CREATE INDEX IF NOT EXISTS movie_companies_company_id_idx ON movie_companies(company_id);
CREATE INDEX IF NOT EXISTS movie_info_movie_id_idx ON movie_info(movie_id);
CREATE INDEX IF NOT EXISTS movie_info_idx_movie_id_idx ON movie_info_idx(movie_id);
CREATE INDEX IF NOT EXISTS movie_keyword_movie_id_idx ON movie_keyword(movie_id);
CREATE INDEX IF NOT EXISTS movie_keyword_keyword_id_idx ON movie_keyword(keyword_id);
CREATE INDEX IF NOT EXISTS movie_link_movie_id_idx ON movie_link(movie_id);
CREATE INDEX IF NOT EXISTS movie_link_linked_movie_id_idx ON movie_link(linked_movie_id);
CREATE INDEX IF NOT EXISTS person_info_person_id_idx ON person_info(person_id);
SQL
    ${PSQL} -d imdb -c "ANALYZE;"
    echo "  imdb creation complete"
fi

# -----------------------------------
# 2/4: imdblight (JOBLight)
# -----------------------------------
if ${PSQL} -lqt | cut -d \| -f 1 | grep -qw imdblight; then
    echo "imdblight already exists, skipping"
else
    echo ""
    echo "--- 2/4 Creating imdblight (JOBLight, 6 tables) ---"
    ${PSQL} -d postgres -f "${PROJECT_ROOT}/methods/SafeBound/Data/IMDB/CreateJOBLightDB.sql"
    ${PSQL} -d imdblight -c "ANALYZE;"
    echo "  imdblight creation complete"
fi

# -----------------------------------
# 3/4: imdblightranges (JOBLightRanges)
# -----------------------------------
if ${PSQL} -lqt | cut -d \| -f 1 | grep -qw imdblightranges; then
    echo "imdblightranges already exists, skipping"
else
    echo ""
    echo "--- 3/4 Creating imdblightranges (JOBLightRanges, 6 tables) ---"
    ${PSQL} -d postgres -f "${PROJECT_ROOT}/methods/SafeBound/Data/IMDB/CreateJOBLightRangesDB.sql"
    ${PSQL} -d imdblightranges -c "ANALYZE;"
    echo "  imdblightranges creation complete"
fi

# -----------------------------------
# 4/4: imdbm (JOBM)
# -----------------------------------
if ${PSQL} -lqt | cut -d \| -f 1 | grep -qw imdbm; then
    echo "imdbm already exists, skipping"
else
    echo ""
    echo "--- 4/4 Creating imdbm (JOBM, 17 tables) ---"
    ${PSQL} -d postgres -f "${PROJECT_ROOT}/methods/SafeBound/Data/IMDB/CreateJOBMDB.sql"
    ${PSQL} -d imdbm -c "ANALYZE;"
    echo "  imdbm creation complete"
fi

echo ""
echo "=== IMDB series databases created ==="
${PSQL} -c "SELECT datname FROM pg_database WHERE datname LIKE 'imdb%' ORDER BY datname;"
