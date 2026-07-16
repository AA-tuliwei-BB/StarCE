#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STATS_DIR="${PROJECT_ROOT}/Benchmark/STATS"

echo "=== 验证 STATS-CEB 数据集 ==="
echo "路径: ${STATS_DIR}"

# 8 张表
TABLES=(badges comments postHistory postLinks posts tags users votes)

all_ok=true
for tbl in "${TABLES[@]}"; do
    csv="${STATS_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        size=$(du -h "${csv}" | cut -f1)
        echo "  ✓ ${tbl}.csv (${size})"
    else
        echo "  ✗ ${tbl}.csv 缺失!"
        all_ok=false
    fi
done

if [ "${all_ok}" = true ]; then
    echo ""
    echo "STATS-CEB 数据集完整 (8/8 文件)"
else
    echo ""
    echo "错误: STATS-CEB 数据集不完整，请检查 ${STATS_DIR}"
    exit 1
fi

# 为 SafeBound 创建 symlink: methods/SafeBound/Data/Stats -> ../../../Benchmark/STATS
SAFEBOUND_STATS_LINK="${PROJECT_ROOT}/methods/SafeBound/Data/Stats"
if [ -L "${SAFEBOUND_STATS_LINK}" ]; then
    echo "SafeBound Stats symlink 已存在，跳过"
elif [ -d "${SAFEBOUND_STATS_LINK}" ]; then
    echo "替换 SafeBound/Data/Stats 目录为 symlink..."
    mv "${SAFEBOUND_STATS_LINK}" "${SAFEBOUND_STATS_LINK}_backup"
    ln -s "../../../Benchmark/STATS" "${SAFEBOUND_STATS_LINK}"
    echo "  symlink 已创建，原目录备份为 Stats_backup"
else
    mkdir -p "$(dirname "${SAFEBOUND_STATS_LINK}")"
    ln -s "../../../Benchmark/STATS" "${SAFEBOUND_STATS_LINK}"
    echo "  symlink 已创建: ${SAFEBOUND_STATS_LINK} -> ../../../Benchmark/STATS"
fi
