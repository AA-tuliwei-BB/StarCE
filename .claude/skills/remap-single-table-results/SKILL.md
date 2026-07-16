---
name: remap-single-table-results
description: Rearrange single-table query results extracted from STATS-CEB queries (e.g., pg_est.txt) to match the single-table query order extracted from subqueries, and output a new result file for StarCE UseSingleTableCard downstream testing. Applies to experiment/running_space/single_query_from_queries.sql, single_query_from_subquery.sql, benchmark/stats-ceb/single_queries/{single_query.sql,pg_est.txt}. Use when mentioning remap/alignment/one-to-one correspondence, single table, pg_est, UseSingleTableCard, subquery order.
---

# remap-single-table-results

## Purpose

- Establish one-to-one correspondence between "single-table SQL extracted from queries workload" and "single-table SQL extracted from subquery workload" (ignoring `AND` condition order differences in `WHERE`)
- Read `benchmark/stats-ceb/single_queries/pg_est.txt` (line-aligned with `benchmark/stats-ceb/single_queries/single_query.sql`)
- Output a new result file whose line order is aligned with `single_query_from_subquery.sql`

## Quick Start (default paths match this repo's conventions)

Run from the repo root:

```bash
python3 scripts/remap_single_table_results.py \
  --mapping-tsv experiment/running_space/single_table_mapping.tsv
```

Default outputs:

- `experiment/running_space/pg_est_subquery_order.txt`
- `experiment/running_space/single_table_mapping.tsv`

## Typical Inputs and Outputs (usually no need to change)

- Input SQL (StarCE RecordingSingleQuery output)
  - `experiment/running_space/single_query_from_queries.sql`
  - `experiment/running_space/single_query_from_subquery.sql`
- Canonical (workload built-in, one per line)
  - `benchmark/stats-ceb/single_queries/single_query.sql`
  - `benchmark/stats-ceb/single_queries/pg_est.txt`
- Output result (for downstream testing)
  - `experiment/running_space/pg_est_subquery_order.txt`

## Integration with StarCE (UseSingleTableCard)

Set `experiment/running_space/config.json` to:

- `UseSingleTableCard=1`
- `SINGLE_QUERY_PATH=experiment/running_space/single_query_from_subquery.sql`
- `SINGLE_QUERY_RESULT_PATH=experiment/running_space/pg_est_subquery_order.txt`

## Common Issues

- Result file line count mismatch: check that `single_query_from_*.sql` and canonical files have consistent line counts (should all be 350 lines)
- Alignment failure: the script will error out and print the reason to stderr (commonly SQL set mismatch or canonical query/result line count mismatch)
