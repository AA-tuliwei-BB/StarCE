# DuckDB 环境搭建

## 前置条件

- gcc / cmake 等编译工具链
- DuckDB 构建依赖（详见项目根目录 `build.sh`）
- TestEnv conda 环境（Python duckdb 包 v1.5.2）

## 编译 DuckDB + StarCE

在项目根目录执行：

```bash
./build.sh          # release 模式
./build.sh debug    # debug 模式
```

`build.sh` 分为两个阶段：

1. **cmake duckdb** — 配置并编译 DuckDB 核心库，输出到 `duckdb/build/release/`（或 `duckdb/build/debug/`）
2. **cmake starce** — 将 StarCE 扩展链接到 DuckDB，最终二进制为 `duckdb/build/release/duckdb`

编译完成后，DuckDB 二进制位于 `duckdb/build/release/duckdb`（release）或 `duckdb/build/debug/duckdb`（debug）。

## 创建数据库文件

### STATS 数据库

```bash
bash setup/duckdb/create_stats_db.sh [duckdb_binary_path]
```

- 在 `Benchmark/duckdb/` 下创建 `stats.db`（约 22 MB）
- 包含 8 张表：badges, comments, postHistory, postLinks, posts, tags, users, votes
- 数据来源：`Benchmark/STATS/*.csv`

### IMDB 数据库

```bash
bash setup/duckdb/create_imdb_db.sh [duckdb_binary_path]
```

- 在 `Benchmark/duckdb/` 下创建 `imdb.db`（约 2.6 GB）
- 包含 21 张 IMDB 表
- 数据来源：`Benchmark/IMDB/*.csv`

## Schema 说明

- **STATS** — 使用 `Benchmark/STATS/stats_duckDB.sql`，主键使用 `CREATE SEQUENCE` 替代 PostgreSQL 的 `SERIAL` 类型，以兼容 DuckDB
- **IMDB** — 使用 `Benchmark/IMDB/imdb_schema.sql`，该 schema 本身即为 DuckDB 兼容格式，无需修改（不含 SERIAL 类型）

## 注意事项

- **IMDB CSV 无表头** — COPY 命令不加 `HEADER` 选项
- **STATS CSV 有表头** — COPY 命令需要 `HEADER` 选项
- 脚本在数据库文件已存在时会跳过创建，防止误覆盖；如需重建请手动 `rm` 对应的 `.db` 文件

## StarCE 使用

StarCE 通过不同的 schema JSON 文件来区分 workload（如 `schema_joblight.json` 定义 JOBLight 的表和列子集）。

对于 IMDB 系列 workload（JOBLight、JOBM 等），只需一个全量的 `imdb.db`，StarCE 会根据 schema JSON 中的表名和列名自动筛选所需数据。不需要为每个 workload 单独创建数据库文件。
