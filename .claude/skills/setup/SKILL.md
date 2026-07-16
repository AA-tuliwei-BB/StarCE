---
name: setup
description: StarCE 项目统一环境搭建指南：conda 环境、数据集获取（STATS/IMDB）、PostgreSQL 配置、DuckDB 编译与数据库创建。当用户提到环境搭建、初始化项目、从零配置、setup、安装环境、创建数据库时使用。
---

# StarCE 项目统一环境搭建

## 快速开始

```bash
# 1. Conda 环境
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. 数据集
bash setup/dataset/init_stats.sh
bash setup/dataset/init_imdb.sh

# 3. 编译 StarCE (DuckDB + StarCE)
./build.sh

# 4. 创建 DuckDB 数据库
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh
```

## 子指南

| 指南 | 路径 | 说明 |
|------|------|------|
| Conda 环境 | `setup/conda/README.md` | Python 3.10.4, TestEnv 环境配置 |
| 数据集 | `setup/dataset/README.md` | STATS-CEB 和 IMDB 数据获取 |
| PostgreSQL | `setup/postgresql/README.md` | PG 13.1 安装、配置、数据库创建 |
| DuckDB | `setup/duckdb/README.md` | 编译、.db 文件创建、CSV 导入 |

## 数据集概览

| 数据集 | 表数 | 大小 | 获取方式 |
|--------|------|------|----------|
| STATS-CEB | 8 | ~39 MB | 仓库内已有，`init_stats.sh` 验证 |
| IMDB | 21 | ~4.8 GB | `init_imdb.sh` 下载 |

数据统一存放在 `Benchmark/STATS/` 和 `Benchmark/IMDB/`。

## PostgreSQL 数据库

| 数据库 | 表数 | 说明 |
|--------|------|------|
| stats | 8 | STATS-CEB |
| imdb | 21 | 完整 IMDB |
| imdblight | 6 | JOBLight 子集 |
| imdblightranges | 6 | JOBLightRanges 子集 |
| imdbm | 17 | JOBM 子集 |

## 编译

始终使用 `./build.sh`（release）或 `./build.sh debug`。release 模式更小更快（~560KB），debug 模式可调试（~11MB）。

## Running Space 初始化

```bash
RUNNING_SPACE=experiment/running_space
mkdir -p $RUNNING_SPACE

# 复制编译产物
cp build/starce $RUNNING_SPACE/
cp duckdb/build/release/duckdb $RUNNING_SPACE/

# 创建 starce 需要的占位文件（即使仅做统计收集也必须存在）
touch $RUNNING_SPACE/dummy_query.sql $RUNNING_SPACE/dummy_result.txt
```

> ⚠️ starce 启动时会读取 `SQL_PATH` 指向的文件（默认 `dummy_query.sql`）并写入 `REAL_CARD_PATH`（默认 `dummy_result.txt`），这两个文件必须存在，否则 starce 会崩溃退出（`Failed to open file`）。

## LpBound 环境

> 详见 [`setup/lpbound/SKILL.md`](lpbound/SKILL.md) — 独立复现指南，含 conda 环境快照。

## 相关 Skills

- [postgresql-env](../postgresql-env/SKILL.md) - PG 连接配置
- [benchmark-datasets](../benchmark-datasets/SKILL.md) - 数据集详情
- [starce-usage](../starce-usage/SKILL.md) - StarCE 运行方法
- [experiment-workflow](../experiment-workflow/SKILL.md) - 实验流程
