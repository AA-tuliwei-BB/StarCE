---
name: workload-file-formats
description: 描述 Benchmark/workloads/ 下各 workload（STATS-CEB、JOBLight、JOBLightRanges、JOBM）的目录结构与文件格式：queries.sql、subquery.sql、subquery2.sql、single_query.sql、result/*.txt（real/duckDB/factorjoin/safebound/starce）、pg_est.txt、real.txt、schema JSON、config.json 的格式约定与行对应关系。当用户提到 workload 文件格式、queries.sql、subquery.sql、subquery2.sql、single_query.sql、result txt、pg_est、schema json、Benchmark/workloads 时使用。
---

# Benchmark/workloads 文件格式速查

## 目录结构总览

```
Benchmark/workloads/
├── dummy_query.sql                # 空占位文件
├── STATS-CEB/                     # Stack Exchange 统计基准
├── JOBLight/                      # JOB-Light（IMDB 简化 join）
├── JOBLightRanges/                # JOB-Light + 范围谓词
└── JOBM/                          # JOB-M（IMDB 多表 join）
```

每个 workload 子目录的典型布局：

```
<workload>/
├── queries.sql                    # 原始基准查询
├── schema_<name>.json             # Schema 定义（STATS-CEB 无此文件）
├── config.json                    # StarCE 运行配置（仅 STATS-CEB、JOBM）
├── single_query/
│   ├── single_query.sql           # 单表查询集合
│   ├── pg_est.txt                 # PostgreSQL 基数估计
│   └── real.txt                   # 真实基数（非所有 workload 都有）
└── subquery/
    ├── subquery.sql               # 子查询集合（SELECT COUNT(*)）
    ├── subquery2.sql              # 子查询集合（SELECT *，STATS-CEB 无此文件）
    └── result/
        ├── real.txt               # 真实基数
        ├── duckDB.txt             # DuckDB 估计
        ├── factorjoin.txt         # FactorJoin 估计（仅 STATS-CEB）
        ├── safebound.txt          # SafeBound 估计
        └── starce.txt             # StarCE 估计（仅 STATS-CEB）
```

## 各文件格式详解

### 1. queries.sql — 原始基准查询

- 每行一条 SQL，无空行、无注释
- 格式：`SELECT COUNT(*) FROM t1 AS a, t2 AS b WHERE a.col=b.col AND ...;`（末尾有分号）
- 表使用别名（`AS`），谓词包含等值 join 条件 + 范围/等值过滤
- STATS-CEB 使用 `::timestamp` 转型；JOB 系列使用数值比较

示例（STATS-CEB）：
```sql
select count(*) FROM badges as b, users as u WHERE b.UserId= u.Id AND u.UpVotes>=0;
```

示例（JOBLight）：
```sql
SELECT COUNT(*) FROM movie_companies AS mc,title AS t,movie_info_idx AS mi_idx WHERE t.id=mc.movie_id AND t.id=mi_idx.movie_id AND mi_idx.info_type_id=112 AND mc.company_type_id=2;
```

### 2. subquery/subquery.sql — 子查询集合（COUNT）

- 每行一条 SQL，格式同 queries.sql：`SELECT COUNT(*) FROM ... WHERE ...;`
- 由原始 queries 展开得到的所有"子集子查询"（子集的表 + 相关 join + 相关谓词）
- 表别名统一为 `<TableName>1` 形式（如 `badges AS badges1`）
- 行数远大于 queries.sql（如 STATS-CEB 146→2471，JOBM 112→6424）

### 3. subquery/subquery2.sql — 子查询集合（SELECT *）

- 与 subquery.sql **逐行对应**、行数相同
- 唯一区别：`SELECT COUNT(*)` 替换为 `SELECT *`
- 用途：供 SafeBound 等需要 `SELECT *` 格式的方法使用
- **STATS-CEB 没有此文件**

### 4. single_query/single_query.sql — 单表查询集合

- 每行一条 SQL，只涉及**单张表**
- 格式：`SELECT COUNT(*) FROM <table> WHERE <predicates>;`
- 由 subquery 中的各表谓词拆解而来（去重后排列）

示例：
```sql
SELECT COUNT(*) FROM badges WHERE badges.Date<='2014-08-02 12:24:29'::timestamp;
```

### 5. result/*.txt — 子查询基数结果

- 纯文本，每行一个数值，与 subquery.sql **逐行一一对应**
- `real.txt`：真实基数（整数）
- `duckDB.txt` / `duckdb.txt`：DuckDB 估计值（整数）
- `factorjoin.txt`：FactorJoin 估计值（浮点数）
- `safebound.txt`：SafeBound 估计值（浮点数）
- `starce.txt`：StarCE 估计值（浮点数）

示例（real.txt）：
```
14929017
3203614
9940949
```

示例（factorjoin.txt）：
```
17089313.997781295
2691939.532955823
14130747.971743993
```

### 6. single_query/pg_est.txt — PostgreSQL 单表估计

- 每行一个整数，与 single_query.sql **逐行一一对应**
- 值为 PostgreSQL 对该单表查询的基数估计

### 7. single_query/real.txt — 单表真实基数

- 每行一个整数，与 single_query.sql **逐行一一对应**
- 值为对应单表查询的真实行数
- 非所有 workload 都有（JOBLight/JOBLightRanges 无此文件）

### 8. schema_\<name\>.json — Schema 定义

- JSON 对象，两个顶层字段：
  - `PredColumns`：谓词列列表，每项 `{"TableName":"...", "ColumnName":"..."}`
  - `EqualSets`：等值 join 集合，每组 `{"Entries": [{"TableName":"...", "ColumnName":"..."},...]}`

示例片段：
```json
{
  "PredColumns": [
    {"TableName":"title", "ColumnName":"production_year"}
  ],
  "EqualSets": [
    {
      "Entries": [
        {"TableName": "title", "ColumnName": "id"},
        {"TableName": "movie_companies", "ColumnName": "movie_id"}
      ]
    }
  ]
}
```

注意：STATS-CEB 的 schema 文件不在 workloads 目录下，而是在 `benchmark/stats-ceb/schema.json`（由 config.json 的 `SCHEMA_PATH` 指定）。

### 9. config.json — StarCE 运行配置

- JSON 对象，包含功能开关和路径配置
- 仅 STATS-CEB 和 JOBM 目录下有
- 详细字段说明见 skill `starce-usage`

## 行对应关系（关键约束）

| 文件 A | 文件 B | 关系 |
|--------|--------|------|
| subquery.sql | subquery2.sql | 逐行对应，行数相同 |
| subquery.sql | result/*.txt（所有） | 逐行对应，行数相同 |
| single_query.sql | pg_est.txt | 逐行对应，行数相同 |
| single_query.sql | real.txt | 逐行对应，行数相同 |

破坏行对应关系会导致 StarCE 或评估脚本产生错误结果。

## 各 workload 规模

| Workload | queries | subquery | single_query | 有 subquery2 | 有 config |
|----------|---------|----------|--------------|---------------|-----------|
| STATS-CEB | 146 | 2471 | 350 | 否 | 是 |
| JOBLight | 70 | 451 | 45 | 是 | 否 |
| JOBLightRanges | 999 | 8292 | — | 是 | 否 |
| JOBM | 112 | 6424 | 127 | 是 | 是 |
