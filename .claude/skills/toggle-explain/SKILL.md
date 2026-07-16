---
name: toggle-explain
description: 为 SQL 文件批量添加、移除或切换 EXPLAIN 前缀（保持 EXPLAIN 与 SQL 同行），用于用 EXPLAIN 测试 StarCE/duckdb 估计器而不实际执行查询。适用于“每行一条 SQL”的 workload 文件（如 STATS-CEB subquery/single_query），并保留注释与空行。
---

# toggle-explain

## 适用场景

- 需要用 `EXPLAIN <SQL>` 触发 StarCE 估计器，但不执行查询
- 需要对大量子查询/单表查询批量加/去掉 `EXPLAIN`

## 约束与行为

- 只支持“每行一条 SQL 语句”的 `.sql` 文件
- 空行、以 `--` 或 `#` 开头的注释行会原样保留
- `EXPLAIN` 会被加到同一行行首：`EXPLAIN <原SQL行去掉左侧空格后的内容>`
- 识别大小写不敏感：`explain`/`EXPLAIN` 都会被当作已存在
- 行尾换行符会保留（`\n` 或 `\r\n`）

## 快速用法

脚本位置：`scripts/toggle_explain.py`

### 生成“带 EXPLAIN”的新文件（推荐）

把 `Benchmark/workloads/STATS-CEB/subquery/subquery.sql` 生成到 `experiment/running_space/`：

```bash
python3 scripts/toggle_explain.py \
  Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --mode add \
  -o experiment/running_space
```

默认会写出：`experiment/running_space/subquery_explain.sql`

如果想改后缀名：

```bash
python3 scripts/toggle_explain.py \
  Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --mode add \
  -o experiment/running_space \
  --suffix _explain
```

### 原地修改（谨慎）

```bash
python3 scripts/toggle_explain.py \
  experiment/running_space/subquery_explain.sql \
  --mode toggle \
  --in-place
```

### 去掉 EXPLAIN（生成新文件）

```bash
python3 scripts/toggle_explain.py \
  experiment/running_space/subquery_explain.sql \
  --mode remove \
  -o experiment/running_space \
  --suffix _noexplain
```

## 常见工作流（StarCE）

1. 先把输入 workload 生成 explain 版本（如上）
2. 在 `experiment/running_space/config.json` 把 `SQL_PATH` 指向 explain 版本
3. 运行 StarCE，把输出重定向到文件
4. （可选）用 `scripts/extract_card_from_explain.py` 从输出里抽取估计基数

