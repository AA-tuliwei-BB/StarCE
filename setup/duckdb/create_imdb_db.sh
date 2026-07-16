#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DUCKDB_BIN="${1:-${PROJECT_ROOT}/duckdb/build/release/duckdb}"
SCHEMA_SQL="${PROJECT_ROOT}/Benchmark/IMDB/imdb_schema.sql"
DATA_DIR="${PROJECT_ROOT}/Benchmark/IMDB"
DB_FILE="${PROJECT_ROOT}/Benchmark/duckdb/imdb.db"

if [ ! -f "${DUCKDB_BIN}" ]; then
    echo "错误: DuckDB binary 未找到: ${DUCKDB_BIN}"
    echo "请先编译: cd ${PROJECT_ROOT} && ./build.sh"
    echo "或指定路径: $0 <path/to/duckdb>"
    exit 1
fi

if [ -f "${DB_FILE}" ]; then
    echo "imdb.db 已存在 (${DB_FILE})，删除以重建:"
    echo "  rm ${DB_FILE}"
    exit 0
fi

echo "=== 创建 IMDB DuckDB 数据库 ==="
echo "Schema: ${SCHEMA_SQL}"
echo "数据: ${DATA_DIR}"
echo "输出: ${DB_FILE}"

mkdir -p "$(dirname "$DB_FILE")"

# 创建表结构
"${DUCKDB_BIN}" "${DB_FILE}" < "${SCHEMA_SQL}"
echo "表结构创建完成"

# 完整的 21 张 IMDB 表
TABLES=(aka_name aka_title cast_info char_name comp_cast_type company_name
        company_type complete_cast info_type keyword kind_type link_type
        movie_companies movie_info movie_info_idx movie_keyword movie_link
        name person_info role_type title)

success=0
skipped=0
for tbl in "${TABLES[@]}"; do
    csv="${DATA_DIR}/${tbl}.csv"
    if [ -f "${csv}" ]; then
        echo "导入 ${tbl}..."
        # IMDB CSV 无 HEADER
        "${DUCKDB_BIN}" "${DB_FILE}" -c "COPY ${tbl} FROM '${csv}' (DELIMITER ',');"
        success=$((success + 1))
    else
        echo "警告: ${csv} 不存在，跳过 ${tbl}"
        skipped=$((skipped + 1))
    fi
done

echo ""
echo "=== 完成 ==="
echo "文件: ${DB_FILE}"
echo "大小: $(du -h "${DB_FILE}" | cut -f1)"
echo "导入: ${success} 表, 跳过: ${skipped} 表"
if [ ${skipped} -gt 0 ]; then
    echo "警告: 有 ${skipped} 张表未导入，请确保 IMDB 数据已初始化:"
    echo "  bash setup/dataset/init_imdb.sh"
fi
