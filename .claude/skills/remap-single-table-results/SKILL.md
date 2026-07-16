---
name: remap-single-table-results
description: 将 STATS-CEB 中“从 queries 提取的单表查询结果（如 pg_est.txt）”按“从 subquery 提取的单表查询顺序”重排，并输出新的 result 文件供 StarCE `UseSingleTableCard` 后续测试使用。适用于本仓库的 `experiment/running_space/single_query_from_queries.sql`、`single_query_from_subquery.sql`、`benchmark/stats-ceb/single_queries/{single_query.sql,pg_est.txt}`。当用户提到 remap/对齐/一一对应、single table、pg_est、UseSingleTableCard、subquery 顺序时使用。
---

# remap-single-table-results

## 目的

- 把“queries workload 提取出来的单表 SQL”与“subquery workload 提取出来的单表 SQL”做一一对应（忽略 `WHERE` 中 `AND` 条件顺序差异）
- 读取 `benchmark/stats-ceb/single_queries/pg_est.txt`（与 `benchmark/stats-ceb/single_queries/single_query.sql` 行对齐）
- 输出一个新的 result 文件，使其行顺序与 `single_query_from_subquery.sql` 对齐

## 快速开始（默认路径即为本仓库约定）

在仓库根目录运行：

```bash
python3 scripts/remap_single_table_results.py \
  --mapping-tsv experiment/running_space/single_table_mapping.tsv
```

默认输出：

- `experiment/running_space/pg_est_subquery_order.txt`
- `experiment/running_space/single_table_mapping.tsv`

## 典型输入输出（你通常不需要改）

- 输入 SQL（StarCE RecordingSingleQuery 产物）
  - `experiment/running_space/single_query_from_queries.sql`
  - `experiment/running_space/single_query_from_subquery.sql`
- canonical（workload 自带，一行一个）
  - `benchmark/stats-ceb/single_queries/single_query.sql`
  - `benchmark/stats-ceb/single_queries/pg_est.txt`
- 输出 result（供后续测试）
  - `experiment/running_space/pg_est_subquery_order.txt`

## 对接 StarCE（UseSingleTableCard）

把 `experiment/running_space/config.json` 调成：

- `UseSingleTableCard=1`
- `SINGLE_QUERY_PATH=experiment/running_space/single_query_from_subquery.sql`
- `SINGLE_QUERY_RESULT_PATH=experiment/running_space/pg_est_subquery_order.txt`

## 常见问题

- 结果文件行数不匹配：检查 `single_query_from_*.sql` 与 canonical 的行数是否一致（应当都是 350 行）
- 对齐失败：脚本会直接报错并在 stderr 输出原因（常见是 SQL 集合不一致或 canonical query/result 行数不一致）

