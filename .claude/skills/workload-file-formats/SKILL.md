---
name: workload-file-formats
description: Describes the directory structure and file formats of each workload (STATS-CEB, JOBLight, JOBLightRanges, JOBM) under Benchmark/workloads/: queries.sql, subquery.sql, subquery2.sql, single_query.sql, result/*.txt (real/duckDB/factorjoin/safebound/starce), pg_est.txt, real.txt, schema JSON, config.json format conventions and line correspondence relationships. Use when mentioning workload file formats, queries.sql, subquery.sql, subquery2.sql, single_query.sql, result txt, pg_est, schema json, Benchmark/workloads.
---

# Benchmark/workloads File Format Quick Reference

## Directory Structure Overview

```
Benchmark/workloads/
├── dummy_query.sql                # Empty placeholder file
├── STATS-CEB/                     # Stack Exchange statistics benchmark
├── JOBLight/                      # JOB-Light (IMDB simplified join)
├── JOBLightRanges/                # JOB-Light + range predicates
└── JOBM/                          # JOB-M (IMDB multi-table join)
```

Typical layout of each workload subdirectory:

```
<workload>/
├── queries.sql                    # Original benchmark queries
├── schema_<name>.json             # Schema definition (not present for STATS-CEB)
├── config.json                    # StarCE runtime config (STATS-CEB, JOBM only)
├── single_query/
│   ├── single_query.sql           # Single-table query set
│   ├── pg_est.txt                 # PostgreSQL cardinality estimates
│   └── real.txt                   # True cardinalities (not all workloads have this)
└── subquery/
    ├── subquery.sql               # Subquery set (SELECT COUNT(*))
    ├── subquery2.sql              # Subquery set (SELECT *, not present for STATS-CEB)
    └── result/
        ├── real.txt               # True cardinalities
        ├── duckDB.txt             # DuckDB estimates
        ├── factorjoin.txt         # FactorJoin estimates (STATS-CEB only)
        ├── safebound.txt          # SafeBound estimates
        └── starce.txt             # StarCE estimates (STATS-CEB only)
```

## File Format Details

### 1. queries.sql — Original Benchmark Queries

- One SQL per line, no blank lines, no comments
- Format: `SELECT COUNT(*) FROM t1 AS a, t2 AS b WHERE a.col=b.col AND ...;` (trailing semicolon)
- Tables use aliases (`AS`), predicates include equi-join conditions + range/equality filters
- STATS-CEB uses `::timestamp` casts; JOB series uses numeric comparisons

Example (STATS-CEB):
```sql
select count(*) FROM badges as b, users as u WHERE b.UserId= u.Id AND u.UpVotes>=0;
```

Example (JOBLight):
```sql
SELECT COUNT(*) FROM movie_companies AS mc,title AS t,movie_info_idx AS mi_idx WHERE t.id=mc.movie_id AND t.id=mi_idx.movie_id AND mi_idx.info_type_id=112 AND mc.company_type_id=2;
```

### 2. subquery/subquery.sql — Subquery Set (COUNT)

- One SQL per line, same format as queries.sql: `SELECT COUNT(*) FROM ... WHERE ...;`
- All "subset subqueries" expanded from original queries (subset of tables + relevant joins + relevant predicates)
- Table aliases use `<TableName>1` form uniformly (e.g., `badges AS badges1`)
- Row count far larger than queries.sql (e.g., STATS-CEB 146→2471, JOBM 112→6424)

### 3. subquery/subquery2.sql — Subquery Set (SELECT *)

- **Line-by-line correspondence** with subquery.sql, same row count
- Only difference: `SELECT COUNT(*)` replaced with `SELECT *`
- Purpose: used by methods requiring `SELECT *` format like SafeBound
- **STATS-CEB does not have this file**

### 4. single_query/single_query.sql — Single-Table Query Set

- One SQL per line, involving only **a single table**
- Format: `SELECT COUNT(*) FROM <table> WHERE <predicates>;`
- Derived from decomposing per-table predicates in subqueries (deduplicated and permuted)

Example:
```sql
SELECT COUNT(*) FROM badges WHERE badges.Date<='2014-08-02 12:24:29'::timestamp;
```

### 5. result/*.txt — Subquery Cardinality Results

- Plain text, one value per line, **line-by-line correspondence** with subquery.sql
- `real.txt`: true cardinality (integer)
- `duckDB.txt` / `duckdb.txt`: DuckDB estimate (integer)
- `factorjoin.txt`: FactorJoin estimate (float)
- `safebound.txt`: SafeBound estimate (float)
- `starce.txt`: StarCE estimate (float)

Example (real.txt):
```
14929017
3203614
9940949
```

Example (factorjoin.txt):
```
17089313.997781295
2691939.532955823
14130747.971743993
```

### 6. single_query/pg_est.txt — PostgreSQL Single-Table Estimates

- One integer per line, **line-by-line correspondence** with single_query.sql
- Values are PostgreSQL's cardinality estimates for the corresponding single-table queries

### 7. single_query/real.txt — Single-Table True Cardinalities

- One integer per line, **line-by-line correspondence** with single_query.sql
- Values are true row counts for the corresponding single-table queries
- Not present in all workloads (JOBLight/JOBLightRanges lack this file)

### 8. schema_\<name\>.json — Schema Definition

- JSON object with two top-level fields:
  - `PredColumns`: list of predicate columns, each `{"TableName":"...", "ColumnName":"..."}`
  - `EqualSets`: equi-join sets, each group `{"Entries": [{"TableName":"...", "ColumnName":"..."},...]}`

Example fragment:
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

Note: STATS-CEB's schema file is not under the workloads directory; it is at `benchmark/stats-ceb/schema.json` (specified by `SCHEMA_PATH` in config.json).

### 9. config.json — StarCE Runtime Configuration

- JSON object containing feature switches and path configuration
- Only present under STATS-CEB and JOBM directories
- Detailed field descriptions in skill `starce-usage`

## Line Correspondence (Critical Constraint)

| File A | File B | Relationship |
|--------|--------|------|
| subquery.sql | subquery2.sql | Line-by-line correspondence, same row count |
| subquery.sql | result/*.txt (all) | Line-by-line correspondence, same row count |
| single_query.sql | pg_est.txt | Line-by-line correspondence, same row count |
| single_query.sql | real.txt | Line-by-line correspondence, same row count |

Breaking line correspondence will cause StarCE or evaluation scripts to produce incorrect results.

## Workload Scales

| Workload | queries | subquery | single_query | Has subquery2 | Has config |
|----------|---------|----------|--------------|---------------|-----------|
| STATS-CEB | 146 | 2471 | 350 | No | Yes |
| JOBLight | 70 | 451 | 45 | Yes | No |
| JOBLightRanges | 999 | 8292 | — | Yes | No |
| JOBM | 112 | 6424 | 127 | Yes | Yes |
