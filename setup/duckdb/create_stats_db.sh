#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DUCKDB_BIN="${1:-${PROJECT_ROOT}/duckdb/build/release/duckdb}"
SCHEMA_SQL="${PROJECT_ROOT}/Benchmark/STATS/stats_duckDB.sql"
DATA_DIR="${PROJECT_ROOT}/Benchmark/STATS"
DB_FILE="${PROJECT_ROOT}/Benchmark/duckdb/stats.db"

if [ ! -f "${DUCKDB_BIN}" ]; then
    echo "错误: DuckDB binary 未找到: ${DUCKDB_BIN}"
    echo "请先编译: cd ${PROJECT_ROOT} && ./build.sh"
    echo "或指定路径: $0 <path/to/duckdb>"
    exit 1
fi

if [ -f "${DB_FILE}" ]; then
    echo "stats.db 已存在 (${DB_FILE})，删除以重建:"
    echo "  rm ${DB_FILE}"
    exit 0
fi

echo "=== 创建 STATS DuckDB 数据库 ==="
echo "Schema: ${SCHEMA_SQL}"
echo "数据: ${DATA_DIR}"
echo "输出: ${DB_FILE}"

mkdir -p "$(dirname "$DB_FILE")"

# 创建表结构
"${DUCKDB_BIN}" "${DB_FILE}" < "${SCHEMA_SQL}"
echo "表结构创建完成"

# STATS 的表名列表（与 benchmark/stats-ceb/starce.db 对齐）
TABLES=(badges comments postHistory postLinks posts tags users votes)

# 导入 CSV (STATS CSV 有 HEADER)
for tbl in "${TABLES[@]}"; do
    csv="${DATA_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        echo "导入 ${tbl}..."
        "${DUCKDB_BIN}" "${DB_FILE}" -c "COPY ${tbl} FROM '${csv}' (HEADER, DELIMITER ',');"
    else
        echo "警告: ${csv} 不存在，跳过"
    fi
done

echo ""
echo "=== 完成 ==="
echo "文件: ${DB_FILE}"
echo "大小: $(du -h "${DB_FILE}" | cut -f1)"
