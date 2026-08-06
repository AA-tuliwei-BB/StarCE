---
name: remap-benchmark-estimates
description: Map external cardinality estimation results (flat/bayescard/deepdb/neurocard) from End-to-End-CardEst-Benchmark to the Benchmark/workloads/ directory format using normalized signatures, supporting STATS-CEB and JOBLight. Use when mentioning mapping FLAT estimates, importing external method results, control experiment estimates, benchmark estimation files.
---

# External Benchmark Estimate Remapping

## Overview

`scripts/remap/map_benchmark_estimates.py` maps precomputed estimation results from `Stats-CEB/End-to-End-CardEst-Benchmark` into the project's standard `Benchmark/` directory format.

Supported methods: flat, bayescard, deepdb, neurocard (4 total).

Supported datasets: STATS-CEB (2471 entries), JOBLight (451 entries).

## Mapping Principle

1. **SQL normalization**: Table names sorted lexicographically, join conditions use Union-Find to establish equivalence classes, each class uses the lexicographically earliest column as anchor to generate minimal non-redundant joins, filters sorted lexicographically
2. **Bridge table inference**: When direct matching fails, infer bridge tables from join column names (STATS: userid→users, postid→posts; JOBLight: movie_id→title), add bridge table and retry matching
3. Signature = `(sorted_tables, canonical_joins, sorted_filters)` exact match

## Usage

```bash
# Run from project root directory
python scripts/remap/map_benchmark_estimates.py
```

## Data Flow

```
Stats-CEB/End-to-End-CardEst-Benchmark/workloads/
├── stats_CEB/sub_plan_queries/
│   ├── stats_CEB_sub_queries.sql          # 2603 SP queries (SQL||index format)
│   └── estimates/
│       ├── stats_CEB_sub_queries_flat.txt
│       ├── stats_CEB_sub_queries_bayescard.txt
│       ├── stats_CEB_sub_queries_deepdb.txt
│       └── stats_CEB_sub_queries_neurocard.txt
└── job-light/sub_plan_queries/
    ├── job_light_sub_query.sql             # 696 SP queries
    └── estimates/
        ├── job_light_sub_queries_flat.txt
        ├── job_light_sub_queries_bayescard.txt
        ├── job_light_sub_queries_deepdb.txt
        └── job_light_sub_queries_neurocard.txt

        ↓ mapping ↓

Benchmark/workloads/
├── STATS-CEB/subquery/result/{flat,bayescard,deepdb,neurocard}.txt  # 2471 lines each
└── JOBLight/subquery/result/{flat,bayescard,deepdb,neurocard}.txt   # 451 lines each
```

## Notes

- The SP query file `stats_CEB_sub_queries.sql` is in raw `SQL||index` format (no `{aliases}` prefix)
- deepdb and neurocard SP signatures contain conflicting estimates (same normalized query maps to multiple different values); the script takes the first one
- Mapping coverage is 100%, no manual intervention needed
