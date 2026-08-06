---
name: starce-overview
description: StarCE project overview: system architecture, all config.json parameter meanings, core data structures (EqualSet/DegreeSequence/DSStatistic/StatisticManager), main operation modes, and the complete data flow for injecting external cardinality estimates (FactorJoin/SafeBound/PostgreSQL) into DuckDB. Use when mentioning StarCE overall architecture, config parameter meanings, cardinality injection mechanism, injection data flow, statistics collection, operation modes.
---

# StarCE Overview

StarCE is a **cardinality estimator embedded in DuckDB** that intercepts and replaces the default cardinality estimation by modifying the Join Order Optimizer, supporting both its own statistical algorithm and comparison experiments with external estimators (FactorJoin, SafeBound, PostgreSQL, etc.).

## Project Structure

| Path | Role |
|------|------|
| `main.cpp` | Entry point: parses config, drives statistics collection, executes SQL, outputs results |
| `duckdb/src/include/duckdb/starce/starce.hpp` | **All core logic** (header-only inline implementation), `StatisticManager` singleton |
| `duckdb/src/include/duckdb/starce/statistic.hpp` | `DegreeSequence`, `DSStatistic` data structures |
| `duckdb/src/include/duckdb/starce/equalset.hpp` | `EqualSet`, `TableColumn` data structures |
| `duckdb/src/optimizer/join_order/query_graph_manager.cpp` | Injection point: registers table info, replaces single-table cardinality |
| `duckdb/src/optimizer/join_order/cardinality_estimator.cpp` | Injection point: replaces multi-table join cardinality estimation |
| `duckdb/src/optimizer/join_order/relation_manager.cpp` | `ResetCardinality()`: overwrites `LogicalGet.estimated_cardinality` |
| `experiment/running_space/` | Working directory, all relative paths are relative to this |

---

## config.json Parameter Reference

All configuration is in `experiment/running_space/config.json`, read at program startup.

### Operation Mode Switches (0/1)

| Field | Meaning |
|------|------|
| `EnableStarCE` | Whether to enable StarCE estimator; 0 falls back to DuckDB native estimation |
| `RecordingSubquery` | Record multi-table subquery SQL and their StarCE estimated cardinalities generated during estimation of each SQL; write to `SUBQUERY_PATH` and `SUBQUERY_RESULT_PATH` after execution |
| `RecordingSingleQuery` | Record single-table filter query SQL (no cardinalities) to `SINGLE_QUERY_PATH`, for external tools (PG/DuckDB) to compute and backfill cardinalities |
| `SubqueryOutputGroupByMain` | When `RecordingSubquery` outputs, group by main query (`=== N ===` delimiter line) |
| `UseSubqueryCard` | Inject precomputed multi-table subquery cardinalities from file, **completely bypassing** StarCE's own algorithm |
| `UseSingleTableCard` | Inject precomputed single-table filter cardinalities from file (e.g., PostgreSQL estimates); StarCE itself still participates in join estimation |
| `UseAssignedAdjustRate` | Use manually specified `ADJUST_RATE` / `PREDICATE_ADJUST_RATE` from config, instead of auto-computed values |
| `RefreshStatistics` | Force re-collection of statistics, ignore `STATS_PATH` cache |
| `EnableStarSplit` | Enable large EqualSet splitting optimization (split by `MaxStarSize`); prints eset size distribution after execution |
| `IsCollectingRelErr` | Read true cardinalities (`REAL_CARD_PATH`), output subquery relative errors to `REL_ERR_PATH` after execution |

### Algorithm Parameters

| Field | Type | Meaning |
|------|------|------|
| `PredMethod` | int | Predicate estimation method: `0`=adjustment rate (DS merge), `1`=uniformity assumption (scaling factor) |
| `CollectParallel` | int | Statistics collection parallel thread count (capped at hardware thread count) |
| `CompressPrecision` | double | DegreeSequence logarithmic bucket precision, default `1.2`, affects statistics cache filename suffix (e.g., `statistics_STATS_cp1.2.json`) |
| `ADJUST_RATE` | double | Global adjustment rate for join estimation (effective when `UseAssignedAdjustRate=1`) |
| `PREDICATE_ADJUST_RATE` | double | Predicate filtering adjustment rate (effective when `UseAssignedAdjustRate=1`) |

### Path Configuration

| Field | Purpose |
|------|------|
| `SCHEMA_PATH` | Schema JSON, defining equi-join relationships (EqualSets) between tables, used for statistics collection |
| `DB_PATH` | DuckDB database file (e.g., `imdb.db`, `stats.db`) |
| `STATS_PATH` | Statistics cache JSON, generated after first run, loaded directly on subsequent runs |
| `SQL_PATH` | Main input SQL file, one per line, StarCE executes them in order |
| `SUBQUERY_PATH` | Subquery SQL file: written when `RecordingSubquery=1`; read when `UseSubqueryCard=1` |
| `SUBQUERY_RESULT_PATH` | Subquery cardinality file, line-aligned with `SUBQUERY_PATH` |
| `SINGLE_QUERY_PATH` | Single-table query SQL file: written when `RecordingSingleQuery=1`; read when `UseSingleTableCard=1` |
| `SINGLE_QUERY_RESULT_PATH` | Single-table query cardinality file (e.g., `pg_est_subquery_order.txt`) |
| `REAL_CARD_PATH` | True subquery cardinality file, read when `IsCollectingRelErr=1` |
| `REL_ERR_PATH` | Relative error output file, written when `IsCollectingRelErr=1` |

---

## Core Data Structures

### EqualSet (`equalset.hpp`)

A set of `(table_name, column_name)` pairs connected by equi-joins, e.g., `posts.Id = votes.PostId` forms an EqualSet with two elements. Statistics are collected and stored per EqualSet.

### DegreeSequence (`statistic.hpp`)

Logarithmic-bucket-compressed degree sequence: records "how many keys have degree (join degree) ≤ maxDegree[i]".
- `dot(other)` — merges two DS by worst-case matching strategy, computes join cardinality upper bound
- `GetCard()` — returns total cardinality (Σ count[i] × maxDegree[i])
- `GetNDV()` — returns NDV (Σ count[i])

### DSStatistic (`statistic.hpp`)

Complete statistics for one EqualSet, containing:
- `centralDs` — central degree sequence (joint degree of the join result)
- `ds[table]` — edge degree sequence per table
- `card` — true cardinality

Key operations:
- `Merge(other, commonTable)` — merge two DSStatistics along a common table (core join estimation)
- `AdjustToAverage(ndv, k)` — shrink toward uniform distribution by adjustment rate k
- `ApplyFilterCoefficient(coeff)` — scale overall by coefficient (used when PredMethod=1)

### StatisticManager (`starce.hpp`)

Global singleton (`starce::StatisticManager::GetInstance()`), holds:
- `statistics: map<EqualSet, DSStatistic*>` — statistics for all EqualSets
- `subqueryCard: map<string, int64_t>` — injected multi-table subquery cardinalities
- `singleQueryCard: map<string, int64_t>` — injected single-table filter cardinalities
- `filterString: map<idx_t, string>` — predicate filter conditions per relation

---

## main.cpp Execution Flow

```
ReadConfig("config.json")
    │
    ▼
Initialize StatisticManager, sync config parameters
    │
    ▼
TryReadStatistics(STATS_PATH)
    ├── success → deserialize statistics cache (skip collection)
    └── failure → CollectStatistics(DB_PATH, SCHEMA_PATH)
                   │  Execute aggregate SQL per EqualSet, multi-threaded parallel
                   └→ serialize to STATS_PATH
    │
    ▼
sm.EnableStarCE = EnableStarCE   ← only enable estimator after stats collection
    │
    ▼
Load external cardinalities by switch:
    UseSubqueryCard    → ReadSubqueryCard()    load subqueryCard map
    UseSingleTableCard → ReadSingleQueryCard() load singleQueryCard map
    IsCollectingRelErr → ReadRealCard()        load realCard map
    │
    ▼
ExecuteSql(con, SQL_PATH)
    For each SQL: sm.ParsePredicate(sql) → con.Query(sql)
    During DuckDB execution, StarCE Hooks trigger (see injection mechanism below)
    │
    ▼
Post-execution output:
    RecordingSubquery    → OutputSubquery()    write subquery SQL + cardinalities
    RecordingSingleQuery → OutputSingleQuery() write single-table query SQL
    IsCollectingRelErr   → OutputRelErr()      write relative errors
```

---

## External Cardinality Injection Mechanism

### Injection Point: DuckDB Join Order Optimizer

StarCE integrates into DuckDB's optimizer by modifying 4 files, triggered during each query execution:

```
JoinOrderOptimizer::Optimize()
    │
    ├── QueryGraphManager::Build()
    │       ├── sm.PrepareEstimate()               ← clear query context
    │       ├── sm.AddTable(i, name, cols, card)   ← register each relation
    │       ├── sm.AddPredicate(t1,t2,c1,c2)       ← build EqualSet
    │       └── [UseSingleTableCard]
    │           RelationManager::ResetCardinality(sm)
    │               └── LogicalGet.estimated_cardinality = sm.GetTableCard(i)
    │
    ├── CardinalityEstimator::EstimateCardinalityWithSet()
    │       └── [use_starce=true]
    │           result = sm.EstimateCardinality(rels)
    │               ├── [UseSubqueryCard] → subqueryCard[sql] (short-circuit return)
    │               └── [otherwise] StarCE DS statistical algorithm
    │
    └── sm.FinishEstimate()
```

### Mode A: UseSingleTableCard — Single-Table Cardinality Replacement

Use case: Replace DuckDB default statistics with single-table estimates from external tools like PostgreSQL; StarCE itself still handles join estimation.

```
single_query.sql + pg_est.txt
    │
    ReadSingleQueryCard() → sm.singleQueryCard: map<string, int64_t>
    │
    QueryGraphManager::Build() → ResetCardinality(sm)
    │   GetTableCard(i) → GetSingleQuery(i) reconstruct SELECT COUNT(*) SQL
    │                   → singleQueryCard[sql]
    └→ LogicalGet.estimated_cardinality overwritten
       StarCE DS algorithm uses injected single-table cardinalities for join estimation
```

### Mode B: UseSubqueryCard — Multi-Table Subquery Cardinality Short-Circuit

Use case: Inject complete results from FactorJoin/SafeBound/true cardinalities, fully replacing StarCE's algorithm, comparing costs within the same DuckDB framework.

```
subquery.sql + factorjoin.txt (or safebound.txt / real.txt)
    │
    ReadSubqueryCard() → sm.subqueryCard: map<string, int64_t>
    │
    EstimateCardinality(rels)
    │   GetSubquery(rels) normalizes to generate SQL string (tables/columns sorted)
    └→ subqueryCard[sql] → returned directly, bypassing all StarCE algorithms
```

**Key design**: SQL strings serve as map keys, normalized by `GetSubquery()` / `GetSingleQuery()` (table names and column names sorted), ensuring consistent strings across different call paths.

---

## Main Operation Mode Summary

| Mode | Key Switch Combination | Typical Use |
|------|-------------|---------|
| Normal estimation | `EnableStarCE=1`, all injection/recording = 0 | StarCE self-estimation effectiveness evaluation |
| Record single-table queries | `RecordingSingleQuery=1` | Generate single-table SQL for external tools to compute cardinalities |
| Inject single-table cardinalities | `UseSingleTableCard=1` | Replace single-table with PG estimates, compare impact on join estimation |
| Record subqueries | `RecordingSubquery=1` | Generate StarCE-estimated multi-table subqueries and cardinalities |
| Inject subquery cardinalities | `UseSubqueryCard=1` | Inject FactorJoin/SafeBound/true cardinalities for comparison experiments |
| Collect errors | `IsCollectingRelErr=1` + `UseSubqueryCard=1` | Compute Q-Error of an estimator against true cardinalities |
| DuckDB native | `EnableStarCE=0` | As baseline |
