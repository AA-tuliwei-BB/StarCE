---
name: starce-single-query-debug
description: Specialized single-query parameter tuning test: running_space configuration, parameter quick reference (PredMethod/CompressPrecision/AdjustRate/UseSingleTableCard), control experiments (DuckDB native/TrueCard injection/RecordingSubquery), switching statistics precision, error analysis workflow. Use when mentioning single-query testing, parameter comparison, config.json parameters, RecordingSubquery, UseSubqueryCard, UseSingleTableCard, PredMethod, CompressPrecision switching.
---

# StarCE Single-Query Specialized Testing

## Purpose

Configure running_space to run only one (or a few) queries for rapid parameter iteration, observing changes in execution time and estimated values.

---

## Basic Steps

### 1. Extract Target Query

```bash
# Run from project root directory
cd experiment/running_space

# Extract the Nth line from queries.sql (query numbering starts at 1)
sed -n '58p' ../../Benchmark/workloads/STATS-CEB/queries.sql > q58_only.sql

# Can also manually write multiple queries
cat > my_queries.sql << 'EOF'
select count(*) FROM ...;
select count(*) FROM ...;
EOF
```

### 2. Modify config.json

Key fields:

```json
{
    "EnableStarCE": 1,
    "UseSubqueryCard": 0,
    "UseSingleTableCard": 1,
    "RefreshStatistics": 0,
    "PredMethod": 1,
    "CompressPrecision": 1.5,
    "DB_PATH": "Benchmark/duckdb/stats.db",
    "SCHEMA_PATH": "../../Benchmark/STATS/schema_stats.json",
    "STATS_PATH": "statistics_stats.json",
    "SQL_PATH": "q58_only.sql",
    "SUBQUERY_PATH": "../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql",
    "SUBQUERY_RESULT_PATH": "dummy_result.txt",
    "SINGLE_QUERY_PATH": "../../Benchmark/workloads/STATS-CEB/single_query/single_query.sql",
    "SINGLE_QUERY_RESULT_PATH": "../../Benchmark/workloads/STATS-CEB/single_query/pg_est.txt",
    "ADJUST_RATE": 1,
    "PREDICATE_ADJUST_RATE": 1
}
```

### 3. Run and Time

```bash
cd experiment/running_space
time ./starce
```

Output line `runtime: XXXX ms` is DuckDB's actual execution time; the `time` command's total includes process startup overhead.

---

## Tunable Parameter Quick Reference

| Parameter | Meaning | Typical Values |
|------|------|--------|
| `EnableStarCE` | Whether to enable StarCE estimation | 0=DuckDB native (control), 1=StarCE |
| `PredMethod` | Predicate handling method | 0=adjustment rate, 1=uniformity assumption |
| `CompressPrecision` | Degree sequence bucketing precision | 1.1/1.2/1.5/2.0 |
| `ADJUST_RATE` | Shrinkage ratio toward mean after Merge | 0.1~1.0 |
| `PREDICATE_ADJUST_RATE` | Shrinkage ratio during predicate filtering | 0.1~1.0 |
| `UseAssignedAdjustRate` | Whether to use manually specified AdjustRate | 0=read from statistics file, 1=use the two values above |
| `EnableStarSplit` | Whether to split large EqualSets | 0/1 |
| `UseSingleTableCard` | Whether to use external single-table cardinalities | 0=DuckDB estimate, 1=inject |

### Switching Statistics Precision (No Recollection Needed)

Precomputed files with different CompressPrecision already exist in running_space:

```
statistics_STATS_cp1.1.json   # Finest
statistics_STATS_cp1.2.json
statistics_STATS_cp1.5.json
statistics_STATS_cp2.json     # Coarsest
statistics_stats.json         # Default (cp2.0)
```

Modify `STATS_PATH` to switch directly; no need to change `CompressPrecision` (CompressPrecision only takes effect during collection).

---

## Common Control Experiments

### Control 1: Disable StarCE, Observe DuckDB Native Performance

```json
"EnableStarCE": 0
```

### Control 2: Inject True Subquery Cardinalities (TrueCard Upper Bound)

```json
"UseSubqueryCard": 1,
"UseSingleTableCard": 0,
"SUBQUERY_PATH": "../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql",
"SUBQUERY_RESULT_PATH": "../../Benchmark/workloads/STATS-CEB/subquery/result/real.txt"
```

**Important**: `SUBQUERY_PATH` line count must match `SUBQUERY_RESULT_PATH`, otherwise cardinality mappings become misaligned, injecting wrong cardinalities and producing worse plans.

- JOBLight: `subquery.sql` has 836 lines, `real.txt` has 451 lines, **mismatch** — confirm which version to use
- After injection, always run EXPLAIN first to verify the plan is reasonable before executing the actual query

### Control 3: Record StarCE's Estimates for Each Subquery

```json
"RecordingSubquery": 1,
"SQL_PATH": "explain_q58.sql",
"SUBQUERY_RESULT_PATH": "q58_starce_cards.txt"
```

First generate the EXPLAIN version:
```bash
echo "EXPLAIN $(cat q58_only.sql)" > explain_q58.sql
```

---

## Typical Workflow: Parameter Tuning Comparison

```bash
cd experiment/running_space

# Baseline: StarCE current config
time ./starce 2>&1 | grep runtime

# Change one parameter
sed -i 's/"PredMethod": 1/"PredMethod": 0/' config.json
time ./starce 2>&1 | grep runtime

# Switch statistics file
sed -i 's/statistics_stats.json/statistics_STATS_cp1.1.json/' config.json
time ./starce 2>&1 | grep runtime

# Restore
git checkout config.json  # or manually revert
```

---

## Notes

- `SQL_PATH` when using relative paths: relative to `running_space/` directory
- `STATS_PATH` when using relative paths: relative to `running_space/` directory; `SCHEMA_PATH`, `SUBQUERY_PATH`, etc. are relative to `running_space/` directory
- `RefreshStatistics: 1` will recollect statistics (time-consuming); keep at 0 when tuning parameters
- When `UseAssignedAdjustRate: 0`, `ADJUST_RATE` and `PREDICATE_ADJUST_RATE` are read from the statistics file; manual settings are ignored
- STATS benchmark corresponds to `stats.db`; JOBM/JOBLight correspond to `imdb.db`
- **config.json is frequently overwritten by the experiment framework (EvaluatePerformanceBreakdown and other notebooks)**; always `cat config.json` before running to verify correct content
- **query_idx is 1-indexed**; Q59 in reports corresponds to line 59 of `queries.sql` (`sed -n '59p'`)
- Single execution time in running_space (~100ms scale) is vastly different from times measured by the experiment framework (seconds), because the framework launches a separate process per query (no page cache warmup), while running_space has cache from consecutive runs. **The two are not directly comparable**; comparing relative differences between two configurations must be done under identical conditions

---

## Error Analysis Workflow (for Specific Queries)

When performance anomalies are found for a particular query, the following steps are recommended:

### 1. Confirm Query Content

```bash
# query_idx=59 corresponds to line 60
sed -n '60p' /path/to/queries.sql
```

### 2. Record StarCE's Subquery Estimates Using RecordingSubquery

```json
"RecordingSubquery": 1,
"SQL_PATH": "explain_q59.sql",          // must be EXPLAIN version
"SUBQUERY_RESULT_PATH": "q59_starce_cards.txt"
```

After running, the first half of `q59_starce_cards.txt` contains estimates, and the second half contains the corresponding SQL.

### 3. Compare Against True Cardinalities

Use duckdb to run true cardinalities for each subquery and compare against StarCE estimates to find the subquery with the largest Q-Error.

### 4. Inject True Cardinalities to See Optimal Plan

```json
"UseSubqueryCard": 1,
"UseSingleTableCard": 0,
"SUBQUERY_PATH": "...",        // line count must match real.txt
"SUBQUERY_RESULT_PATH": "..."  // real.txt
```

First run EXPLAIN to compare structural differences between the two plans, then execute to confirm time differences.
