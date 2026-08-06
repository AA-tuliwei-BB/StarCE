---
name: toggle-explain
description: Batch add, remove, or toggle EXPLAIN prefix for SQL files (keeping EXPLAIN on the same line as the SQL), used for testing StarCE/duckdb estimator via EXPLAIN without actually executing queries. Works with "one SQL per line" workload files (e.g., STATS-CEB subquery/single_query), preserving comments and blank lines.
---

# toggle-explain

## Use Cases

- Need to trigger StarCE estimator with `EXPLAIN <SQL>` without executing queries
- Need to batch add/remove `EXPLAIN` for large sets of subqueries/single-table queries

## Constraints and Behavior

- Only supports `.sql` files with "one SQL statement per line"
- Blank lines and comment lines starting with `--` or `#` are preserved as-is
- `EXPLAIN` is prepended to the same line: `EXPLAIN <original SQL line with leading whitespace stripped>`
- Case-insensitive detection: both `explain`/`EXPLAIN` are treated as already present
- Line endings are preserved (`\n` or `\r\n`)

## Quick Usage

Script location: `scripts/toggle_explain.py`

### Generate "With EXPLAIN" New File (Recommended)

Generate from `Benchmark/workloads/STATS-CEB/subquery/subquery.sql` to `experiment/running_space/`:

```bash
python3 scripts/toggle_explain.py \
  Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --mode add \
  -o experiment/running_space
```

Default output: `experiment/running_space/subquery_explain.sql`

To change the suffix:

```bash
python3 scripts/toggle_explain.py \
  Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --mode add \
  -o experiment/running_space \
  --suffix _explain
```

### In-Place Modification (Caution)

```bash
python3 scripts/toggle_explain.py \
  experiment/running_space/subquery_explain.sql \
  --mode toggle \
  --in-place
```

### Remove EXPLAIN (Generate New File)

```bash
python3 scripts/toggle_explain.py \
  experiment/running_space/subquery_explain.sql \
  --mode remove \
  -o experiment/running_space \
  --suffix _noexplain
```

## Common Workflow (StarCE)

1. First generate EXPLAIN version of input workload (as above)
2. Set `SQL_PATH` in `experiment/running_space/config.json` to point to the EXPLAIN version
3. Run StarCE, redirect output to file
4. (Optional) Use `scripts/extract_card_from_explain.py` to extract estimated cardinalities from output
