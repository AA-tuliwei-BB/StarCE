# StarCE 统一环境搭建

本目录提供完整的项目环境搭建指南和脚本。

## 快速开始

```bash
# 1. Conda 环境
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. 数据集初始化
bash setup/dataset/init_stats.sh      # 验证 STATS-CEB
bash setup/dataset/init_imdb.sh       # 下载 IMDB (~3.5GB)

# 3. 编译 StarCE (DuckDB + StarCE)
./build.sh

# 4. 创建 DuckDB 数据库
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh

# 5. PostgreSQL 环境（见 setup/postgresql/README.md）
```

## 目录结构

| 目录 | 说明 |
|------|------|
| `conda/` | Conda 环境导出文件，Python 3.10.4 / TestEnv |
| `dataset/` | 数据集初始化脚本（数据落地到 Benchmark/） |
| `postgresql/` | PostgreSQL 13.1 安装、配置、建库全流程 |
| `duckdb/` | DuckDB 编译、.db 文件创建、CSV 导入 |

## 数据集

| 数据集 | 表数 | 大小 | 位置 |
|--------|------|------|------|
| STATS-CEB | 8 | ~39 MB | `Benchmark/STATS/`（仓库已有）|
| IMDB | 21 | ~4.8 GB | `Benchmark/IMDB/`（需下载）|

## 构建产物

| 产物 | 位置 | 说明 |
|------|------|------|
| stats.db | `Benchmark/duckdb/stats.db` | STATS DuckDB 数据库 |
| imdb.db | `Benchmark/duckdb/imdb.db` | IMDB 全量 DuckDB 数据库 |
| stats (PG) | PostgreSQL | STATS-CEB 数据库 |
| imdb (PG) | PostgreSQL | 完整 IMDB 数据库 |
| imdblight (PG) | PostgreSQL | JOBLight 子集（6 表）|
| imdblightranges (PG) | PostgreSQL | JOBLightRanges 子集（6 表）|
| imdbm (PG) | PostgreSQL | JOBM 子集（17 表）|

## 后续

环境搭建完成后，参考以下 skill 进行实验：

- [starce-usage](../.claude/skills/starce-usage/SKILL.md) — StarCE 运行方法
- [pg-end2end](../.claude/skills/pg-end2end/SKILL.md) — PG 端对端测试
- [experiment-workflow](../.claude/skills/experiment-workflow/SKILL.md) — 实验流程总览
