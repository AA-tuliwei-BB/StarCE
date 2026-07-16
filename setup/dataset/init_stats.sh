#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STATS_DIR="${PROJECT_ROOT}/Benchmark/STATS"

echo "=== Verify STATS-CEB dataset ==="
echo "Path: ${STATS_DIR}"

# 8 tables
TABLES=(badges comments postHistory postLinks posts tags users votes)

all_ok=true
for tbl in "${TABLES[@]}"; do
    csv="${STATS_DIR}/${tbl}.csv"
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
    echo "STATS-CEB dataset complete (8/8 files)"
else
    echo ""
    echo "Error: STATS-CEB dataset incomplete, please check ${STATS_DIR}"
    exit 1
fi

# Create symlink for SafeBound: methods/SafeBound/Data/Stats -> ../../../Benchmark/STATS
SAFEBOUND_STATS_LINK="${PROJECT_ROOT}/methods/SafeBound/Data/Stats"
if [ -L "${SAFEBOUND_STATS_LINK}" ]; then
    echo "SafeBound Stats symlink already exists, skipping"
elif [ -d "${SAFEBOUND_STATS_LINK}" ]; then
    echo "Replacing SafeBound/Data/Stats directory with symlink..."
    mv "${SAFEBOUND_STATS_LINK}" "${SAFEBOUND_STATS_LINK}_backup"
    ln -s "../../../Benchmark/STATS" "${SAFEBOUND_STATS_LINK}"
    echo "  symlink created, original directory backed up as Stats_backup"
else
    mkdir -p "$(dirname "${SAFEBOUND_STATS_LINK}")"
    ln -s "../../../Benchmark/STATS" "${SAFEBOUND_STATS_LINK}"
    echo "  symlink created: ${SAFEBOUND_STATS_LINK} -> ../../../Benchmark/STATS"
fi
