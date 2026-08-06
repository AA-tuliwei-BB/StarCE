---
name: starce-usage
description: Summary of running and testing StarCE in this repo: control input SQL, statistics, database and output paths by modifying experiment/running_space/config.json; support worst-SQL pinpoint testing, EXPLAIN-triggered estimator (no actual execution), RecordingSubquery/RecordingSingleQuery to record subquery and single-table query sets, collecting relative error (rel err). Use when mentioning starce, config.json, RecordingSubquery, RecordingSingleQuery, UseSingleTableCard, EXPLAIN, subquery, q-error/rel err.
---

# StarCE Usage (This Repo)

## Core Concept

- StarCE behavior is controlled via `experiment/running_space/config.json`
- The most common testing approach is:
  - Place the SQL file to run in `experiment/running_space/` (to avoid path/permission issues)
  - When "estimator-only testing" is needed, prepend `EXPLAIN` to each SQL (same line, no line break)
  - Run `./starce` from the `experiment/running_space/` directory (so the program can find `config.json` in the same directory)

## Must-Change Config Items Quick Reference (`experiment/running_space/config.json`)

- `DB_PATH`: DuckDB database path (e.g., `Benchmark/duckdb/stats.db`)
- `STATS_PATH`: StarCE statistics JSON (usually from `experiment/checkpoint/StarCE/`)
- `SCHEMA_PATH`: schema JSON (choose by workload)
- `SQL_PATH`: input SQL file path (recommend pointing to `experiment/running_space/*.sql`)

### Recording-Related

- `RecordingSubquery=1`:
  - `SUBQUERY_PATH`: subquery detail output (SQL list)
  - `SUBQUERY_RESULT_PATH`: subquery estimation result output (may overwrite original file)
- `RecordingSingleQuery=1`:
  - `SINGLE_QUERY_PATH`: extracted "single-table query set" output (SQL list)
  - `SINGLE_QUERY_RESULT_PATH`: single-table estimation result path (may also be written/overwritten in some modes)

Important: If you don't want to modify/overwrite existing result files (e.g., workload-built-in `pg_est.txt` or checkpoint outputs), when enabling the corresponding Recording, you must redirect `SUBQUERY_RESULT_PATH` (near item 16 in config) and `SINGLE_QUERY_RESULT_PATH` (near item 18) to new filenames under `experiment/running_space/`.

## Common Pitfalls (Troubleshoot First)

- Working directory: recommend `cd experiment/running_space && ./starce` to avoid "cannot find config.json"
- Output file not found: some output paths may require the file to exist (create empty files if needed)
- Table aliases: some SQL input files missing `FROM <table> AS <alias>` will trigger parse errors; prefer workload versions with aliases (e.g., `benchmark/stats-ceb/queries.sql`)

## Workflow 1: Worst SQL Pinpoint Testing (with Subquery Recording and Error)

Goal: Take the first SQL (largest q-error) from `experiment/checkpoint/StarCE/topk_subqueries_stats.sql`, run it individually and record subqueries/errors.

Steps:

1. Save the first SQL to `experiment/running_space/test_worst.sql`
2. Configure `config.json`:
   - `SQL_PATH` → `.../experiment/running_space/test_worst.sql`
   - `RecordingSubquery=1`
   - `IsCollectingRelErr=1`
   - `SUBQUERY_PATH`/`SUBQUERY_RESULT_PATH`/`REL_ERR_PATH` point to new output files under `experiment/running_space/`
   - `SCHEMA_PATH`/`STATS_PATH`/`REAL_CARD_PATH` set to corresponding STATS-CEB paths
3. Run:

```bash
cd experiment/running_space
./starce > worst_run.log 2>&1
```

Results to check:

- `SUBQUERY_PATH`: recorded subqueries
- `SUBQUERY_RESULT_PATH`: subquery estimation results
- `REL_ERR_PATH`: error output

## Workflow 2: EXPLAIN Trigger Estimator (No Actual Execution)

Goal: Batch "run estimator only" on many SQL queries without actually executing them.

Steps:

1. Place target SQL file in `experiment/running_space/` (e.g., `queries.sql` or `subquery.sql`)
2. Batch add `EXPLAIN` (ensuring `EXPLAIN` is on the same line as the SQL):
   - Recommend using script: `scripts/toggle_explain.py`
   - Can also reference project Skill: `.cursor/skills/toggle-explain/SKILL.md`
3. Configure `config.json`:
   - `SQL_PATH` → `experiment/running_space/<name>_explain.sql`
4. Run and save output:

```bash
cd experiment/running_space
./starce > explain_output.log 2>&1
```

Optional: If extracting estimated cardinalities from `EXPLAIN` output, use `scripts/extract_card_from_explain.py` in the repo to parse the output file.

## Workflow 3: Extract Single-Table Query Sets from Queries and Subqueries and Compare

Goal: Verify whether "single-table query sets extracted from stats-ceb queries and subqueries are identical".

Recommended approach: use `EXPLAIN` input on both sides to ensure the same estimator path.

Steps:

1. Prepare EXPLAIN-version inputs:
   - `queries_explain.sql` (batch-add EXPLAIN to queries.sql)
   - `subquery_explain.sql` (batch-add EXPLAIN to subquery.sql)
2. Configure and run twice (output to two different files):
   - First run:
     - `RecordingSingleQuery=1`
     - `SQL_PATH=.../queries_explain.sql`
     - `SINGLE_QUERY_PATH=.../single_query_from_queries.sql`
   - Second run:
     - `SQL_PATH=.../subquery_explain.sql`
     - `SINGLE_QUERY_PATH=.../single_query_from_subquery.sql`
3. Comparison suggestions:
   - Direct line-by-string comparison may produce "not identical" — common reason is different `AND` condition order in `WHERE`
   - First split `WHERE` by `AND`, sort (normalize), then do set comparison to determine "semantic set agreement"

## Workflow 4: UseSingleTableCard (Consume Single-Table Estimation Results)

Goal: Have StarCE directly read an existing single-table estimation result file (rather than estimating online).

Steps:

1. Configure:
   - `UseSingleTableCard=1`
   - `SINGLE_QUERY_RESULT_PATH` point to existing result file (e.g., workload-built-in `pg_est.txt`)
2. Run normal query/EXPLAIN testing

Common error:

- "No single table card for table ...": indicates the single-table predicate was not found in the result file, or the result file path is wrong/version mismatched
