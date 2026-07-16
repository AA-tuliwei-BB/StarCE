#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMDB_DIR="${PROJECT_ROOT}/Benchmark/IMDB"
IMDB_URL="https://event.cwi.nl/da/job/imdb.tgz"
TARBALL="${IMDB_DIR}/imdb.tgz"

mkdir -p "${IMDB_DIR}"

# Complete 21 tables
TABLES=(aka_name aka_title cast_info char_name comp_cast_type company_name
        company_type complete_cast info_type keyword kind_type link_type
        movie_companies movie_info movie_info_idx movie_keyword movie_link
        name person_info role_type title)

# Check if already exists
existing=$(find "${IMDB_DIR}" -maxdepth 1 -name '*.csv' 2>/dev/null | wc -l)
if [ "${existing}" -ge 20 ]; then
    echo "IMDB data already exists (${existing} CSV). Delete ${IMDB_DIR} to re-download:"
    echo "  rm -rf ${IMDB_DIR}/*.csv ${IMDB_DIR}/*.tgz"
    exit 0
fi

echo "=== Download IMDB dataset (~3.5 GB) ==="
echo "URL: ${IMDB_URL}"
echo "Target: ${IMDB_DIR}"
echo ""

wget -O "${TARBALL}" "${IMDB_URL}"

echo ""
echo "Extracting..."
tar zxvf "${TARBALL}" -C "${IMDB_DIR}"

echo ""
echo "Cleaning up tarball..."
rm -f "${TARBALL}"

# Verify
echo ""
echo "=== Verify IMDB dataset ==="
all_ok=true
for tbl in "${TABLES[@]}"; do
    csv="${IMDB_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        size=$(du -h "${csv}" | cut -f1)
        echo "  ✓ ${tbl}.csv (${size})"
    else
        echo "  ✗ ${tbl}.csv missing!"
        all_ok=false
    fi
done

if [ "${all_ok}" = true ]; then
    echo ""
    echo "IMDB dataset complete (21/21 files)"
else
    echo ""
    echo "Error: IMDB dataset incomplete"
    exit 1
fi

# Create symlink for SafeBound: methods/SafeBound/Data/IMDB -> ../../../Benchmark/IMDB
SAFEBOUND_IMDB_LINK="${PROJECT_ROOT}/methods/SafeBound/Data/IMDB"
if [ -L "${SAFEBOUND_IMDB_LINK}" ]; then
    echo "SafeBound IMDB symlink already exists, skipping"
elif [ -d "${SAFEBOUND_IMDB_LINK}" ]; then
    echo "Replacing SafeBound/Data/IMDB directory with symlink..."
    mv "${SAFEBOUND_IMDB_LINK}" "${SAFEBOUND_IMDB_LINK}_backup"
    ln -s "../../../Benchmark/IMDB" "${SAFEBOUND_IMDB_LINK}"
    echo "  symlink created, original directory backed up as IMDB_backup"
else
    mkdir -p "$(dirname "${SAFEBOUND_IMDB_LINK}")"
    ln -s "../../../Benchmark/IMDB" "${SAFEBOUND_IMDB_LINK}"
    echo "  symlink created: ${SAFEBOUND_IMDB_LINK} -> ../../../Benchmark/IMDB"
fi
