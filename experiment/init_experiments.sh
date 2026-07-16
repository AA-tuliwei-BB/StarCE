#!/bin/bash

# 这个脚本负责：
# 1. 验证 Benchmark/duckdb/ 下的 stats.db 和 imdb.db 存在
# 2. 复制duckdb和starce可执行文件到running_space

set -euo pipefail

MODE="${1:-release}"
case "${MODE}" in
    debug|release)
        ;;
    *)
        echo "错误: 第一个参数必须是 debug 或 release（当前: ${MODE}）"
        echo "用法: $0 [debug|release]"
        exit 1
        ;;
esac

# 获取脚本所在目录
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

# 1. 检查duckdb源文件是否存在
if [ ! -f "$DUCKDB_SOURCE" ]; then
    echo "错误: 找不到duckdb可执行文件: $DUCKDB_SOURCE"
    exit 1
fi

# 1.1 打印模式和来源路径
echo "初始化实验环境，模式: ${MODE}"
echo "duckdb 来源: ${DUCKDB_SOURCE}"
echo "starce 来源: ${STARCE_SOURCE}"

# 2. 创建running_space目录（如果不存在）
mkdir -p "$RUNNING_SPACE_DIR"

# 3. 复制duckdb到running_space
echo "正在复制duckdb到running_space..."
cp "$DUCKDB_SOURCE" "$RUNNING_SPACE_DIR/duckdb"
chmod +x "$RUNNING_SPACE_DIR/duckdb"

# 3.1. 复制starce到running_space
echo "正在复制starce到running_space..."
if [ ! -f "$STARCE_SOURCE" ]; then
    echo "错误: 找不到starce可执行文件: $STARCE_SOURCE"
    exit 1
fi
cp "$STARCE_SOURCE" "$RUNNING_SPACE_DIR/starce"
chmod +x "$RUNNING_SPACE_DIR/starce"

# 4. 验证 Benchmark/duckdb 下的数据库文件
echo "==== 验证数据库文件 ===="
if [ ! -f "${PROJECT_ROOT}/Benchmark/duckdb/stats.db" ]; then
    echo "错误: Benchmark/duckdb/stats.db 不存在"
    echo "请先创建: bash setup/duckdb/create_stats_db.sh"
    exit 1
fi
echo "stats.db 已就绪: ${PROJECT_ROOT}/Benchmark/duckdb/stats.db"

if [ ! -f "${PROJECT_ROOT}/Benchmark/duckdb/imdb.db" ]; then
    echo "错误: Benchmark/duckdb/imdb.db 不存在"
    echo "请先创建: bash setup/duckdb/create_imdb_db.sh"
    exit 1
fi
echo "imdb.db 已就绪: ${PROJECT_ROOT}/Benchmark/duckdb/imdb.db"

# 5. 创建dummy文件
echo "创建dummy files..."
touch "${RUNNING_SPACE_DIR}/dummy_query.sql"
touch "${RUNNING_SPACE_DIR}/dummy_result.txt"

echo "完成！duckdb 和 starce 可执行文件已复制到 running_space 目录中"
echo ".db 文件位于 Benchmark/duckdb/ 目录中"

