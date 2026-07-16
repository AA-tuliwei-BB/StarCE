#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMDB_DIR="${PROJECT_ROOT}/Benchmark/IMDB"
IMDB_URL="https://event.cwi.nl/da/job/imdb.tgz"
TARBALL="${IMDB_DIR}/imdb.tgz"

mkdir -p "${IMDB_DIR}"

# 完整的 21 张表
TABLES=(aka_name aka_title cast_info char_name comp_cast_type company_name
        company_type complete_cast info_type keyword kind_type link_type
        movie_companies movie_info movie_info_idx movie_keyword movie_link
        name person_info role_type title)

# 检查是否已存在
existing=$(find "${IMDB_DIR}" -maxdepth 1 -name '*.csv' 2>/dev/null | wc -l)
if [ "${existing}" -ge 20 ]; then
    echo "IMDB 数据已存在 (${existing} CSV)。删除 ${IMDB_DIR} 重新下载:"
    echo "  rm -rf ${IMDB_DIR}/*.csv ${IMDB_DIR}/*.tgz"
    exit 0
fi

echo "=== 下载 IMDB 数据集 (~3.5 GB) ==="
echo "URL: ${IMDB_URL}"
echo "目标: ${IMDB_DIR}"
echo ""

wget -O "${TARBALL}" "${IMDB_URL}"

echo ""
echo "解压中..."
tar zxvf "${TARBALL}" -C "${IMDB_DIR}"

echo ""
echo "清理 tarball..."
rm -f "${TARBALL}"

# 验证
echo ""
echo "=== 验证 IMDB 数据集 ==="
all_ok=true
for tbl in "${TABLES[@]}"; do
    csv="${IMDB_DIR}/${tbl}.csv"
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
    echo "IMDB 数据集完整 (21/21 文件)"
else
    echo ""
    echo "错误: IMDB 数据集不完整"
    exit 1
fi

# 为 SafeBound 创建 symlink: methods/SafeBound/Data/IMDB -> ../../../Benchmark/IMDB
SAFEBOUND_IMDB_LINK="${PROJECT_ROOT}/methods/SafeBound/Data/IMDB"
if [ -L "${SAFEBOUND_IMDB_LINK}" ]; then
    echo "SafeBound IMDB symlink 已存在，跳过"
elif [ -d "${SAFEBOUND_IMDB_LINK}" ]; then
    echo "替换 SafeBound/Data/IMDB 目录为 symlink..."
    mv "${SAFEBOUND_IMDB_LINK}" "${SAFEBOUND_IMDB_LINK}_backup"
    ln -s "../../../Benchmark/IMDB" "${SAFEBOUND_IMDB_LINK}"
    echo "  symlink 已创建，原目录备份为 IMDB_backup"
else
    mkdir -p "$(dirname "${SAFEBOUND_IMDB_LINK}")"
    ln -s "../../../Benchmark/IMDB" "${SAFEBOUND_IMDB_LINK}"
    echo "  symlink 已创建: ${SAFEBOUND_IMDB_LINK} -> ../../../Benchmark/IMDB"
fi
