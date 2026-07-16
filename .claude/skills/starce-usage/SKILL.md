---
name: starce-usage
description: 总结 StarCE 在本仓库的运行与测试方法：通过修改 `experiment/running_space/config.json` 控制输入 SQL、统计信息、数据库与输出路径；支持最差 SQL 定点测试、EXPLAIN 触发估计器（不实际执行）、RecordingSubquery/RecordingSingleQuery 记录子查询与单表查询集合、收集相对误差（rel err）。当用户提到 starce、config.json、RecordingSubquery、RecordingSingleQuery、UseSingleTableCard、EXPLAIN、subquery、q-error/rel err 时使用。
---

# StarCE 用法（本仓库）

## 核心思路

- StarCE 通过 `experiment/running_space/config.json` 控制行为
- 最常用的测试方法是：
  - 把要跑的 SQL 文件放到 `experiment/running_space/`（避免路径/权限问题）
  - 需要“只测估计器”时，对每条 SQL 加 `EXPLAIN`（同一行，不换行）
  - 在 `experiment/running_space/` 目录下运行 `./starce`（让程序能直接找到同目录的 `config.json`）

## 必改配置项速查（`experiment/running_space/config.json`）

- `DB_PATH`：DuckDB 数据库路径（例如 `Benchmark/duckdb/stats.db`）
- `STATS_PATH`：StarCE 的统计信息 json（通常来自 `experiment/checkpoint/StarCE/`）
- `SCHEMA_PATH`：schema json（按 workload 选择）
- `SQL_PATH`：输入 SQL 文件路径（建议指向 `experiment/running_space/*.sql`）

### Recording 相关

- `RecordingSubquery=1`：
  - `SUBQUERY_PATH`：子查询明细输出（SQL 列表）
  - `SUBQUERY_RESULT_PATH`：子查询估计结果输出（可能会覆盖原文件）
- `RecordingSingleQuery=1`：
  - `SINGLE_QUERY_PATH`：提取到的“单表查询集合”输出（SQL 列表）
  - `SINGLE_QUERY_RESULT_PATH`：单表估计结果路径（在某些模式下也可能被写出/覆盖）

重要：如果你不想改动/覆盖原有结果文件（例如 workload 自带的 `pg_est.txt` 或 checkpoint 里的输出），在开启对应的 Recording 时，务必把 `SUBQUERY_RESULT_PATH`（config 里的第 16 项附近）和 `SINGLE_QUERY_RESULT_PATH`（第 18 项附近）改到 `experiment/running_space/` 下的新文件名。

## 常见坑（先排雷）

- 运行目录：建议 `cd experiment/running_space && ./starce`，避免“找不到 config.json”
- 输出文件不存在：部分输出路径可能要求文件存在（必要时先创建空文件）
- 表别名：某些 SQL 输入文件缺少 `FROM <table> AS <alias>` 会触发解析报错；优先使用带别名的 workload 版本（例如 `benchmark/stats-ceb/queries.sql`）

## 工作流 1：最差 SQL 定点测试（带子查询记录与误差）

目标：从 `experiment/checkpoint/StarCE/topk_subqueries_stats.sql` 取第一条（q-error 最大）SQL，单独跑并记录子查询/误差。

步骤：

1. 把第一条 SQL 保存到 `experiment/running_space/test_worst.sql`
2. 配置 `config.json`：
   - `SQL_PATH` → `.../experiment/running_space/test_worst.sql`
   - `RecordingSubquery=1`
   - `IsCollectingRelErr=1`
   - `SUBQUERY_PATH`/`SUBQUERY_RESULT_PATH`/`REL_ERR_PATH` 指向 `experiment/running_space/` 下的新输出文件
   - `SCHEMA_PATH`/`STATS_PATH`/`REAL_CARD_PATH` 按 STATS-CEB 对应路径设置
3. 运行：

```bash
cd experiment/running_space
./starce > worst_run.log 2>&1
```

结果通常看：

- `SUBQUERY_PATH`：记录到的子查询
- `SUBQUERY_RESULT_PATH`：子查询估计结果
- `REL_ERR_PATH`：误差输出

## 工作流 2：EXPLAIN 触发估计器（不实际执行）

目标：批量对很多 SQL “只跑估计器”，不真正执行查询。

步骤：

1. 把目标 SQL 文件放到 `experiment/running_space/`（例如 `queries.sql` 或 `subquery.sql`）
2. 批量加 `EXPLAIN`（保证 `EXPLAIN` 与 SQL 同行）：
   - 推荐用脚本：`scripts/toggle_explain.py`
   - 也可以参考项目 Skill：`.cursor/skills/toggle-explain/SKILL.md`
3. 配置 `config.json`：
   - `SQL_PATH` → `experiment/running_space/<name>_explain.sql`
4. 运行并保存输出：

```bash
cd experiment/running_space
./starce > explain_output.log 2>&1
```

可选：如果需要从 `EXPLAIN` 输出里抽取估计基数，使用仓库里的 `scripts/extract_card_from_explain.py` 对输出文件做解析。

## 工作流 3：从 queries 与 subquery 提取单表查询集合并对比

目标：验证 “从 stats-ceb 的 queries 与 subquery 提取出的单表查询集合是否相同”。

推荐做法：两边都用 `EXPLAIN` 输入，确保走同一条估计器路径。

步骤：

1. 准备 explain 版本输入：
   - `queries_explain.sql`（由 queries.sql 批量加 EXPLAIN）
   - `subquery_explain.sql`（由 subquery.sql 批量加 EXPLAIN）
2. 配置并跑两次（输出到两个不同文件）：
   - 第一次：
     - `RecordingSingleQuery=1`
     - `SQL_PATH=.../queries_explain.sql`
     - `SINGLE_QUERY_PATH=.../single_query_from_queries.sql`
   - 第二次：
     - `SQL_PATH=.../subquery_explain.sql`
     - `SINGLE_QUERY_PATH=.../single_query_from_subquery.sql`
3. 对比建议：
   - 直接按行字符串比较可能会“不相同”，常见原因是 `WHERE` 子句里 `AND` 条件顺序不同
   - 先把 `WHERE` 按 `AND` 拆开排序（归一化）再做集合对比，能判断“语义集合是否一致”

## 工作流 4：UseSingleTableCard（消费单表估计结果）

目标：让 StarCE 直接读取已有的单表估计结果文件（而不是在线估计）。

步骤：

1. 配置：
   - `UseSingleTableCard=1`
   - `SINGLE_QUERY_RESULT_PATH` 指向已有结果文件（例如 workload 自带的 `pg_est.txt`）
2. 运行正常查询/EXPLAIN 测试

常见错误：

- “No single table card for table ...”：说明要用的单表谓词没有出现在结果文件中，或结果文件路径不对/版本不匹配

