---
name: extract-worst-subqueries
description: Compute Q-Error from STATS-CEB true cardinality and estimated cardinality files, find the Top-K subqueries with the largest errors, and export them as .sql files for manual testing. Use when troubleshooting large StarCE errors on STATS, or when needing to locate “worst subqueries/TopK subqueries/Q-Error/extract subqueries/manual testing”.
---

# Extract Worst Subqueries (STATS-CEB)

## Applicable Scenarios

- You found large errors on STATS-CEB, suspect an implementation issue, and need to quickly locate the subqueries with the **largest Q-Error**, export them for manual reproduction testing.

## Input and Output (Default)

- **Subquery SQL**: `Benchmark/workloads/STATS-CEB/subquery/subquery.sql` (one `SELECT COUNT(*) ...;` per line)
- **True cardinality**: `Benchmark/workloads/STATS-CEB/subquery/result/real.txt` (one number per line)
- **StarCE estimated cardinality**: `experiment/checkpoint/StarCE/card_stats.txt` (one number per line)
- **Export file**: `experiment/checkpoint/StarCE/topk_subqueries_stats.sql`

## Error Metric (Q-Error)

To avoid anomalies caused by 0, truncation is applied before calculation:

- \(t = \max(1, true)\)
- \(e = \max(1, est)\)
- \(qerror = \max(e, t) / \min(e, t)\) (always ≥ 1)

## Operation Steps (Must Be Followed in Order)

1. Confirm input files exist and all three have **the same line count** (otherwise line-by-line alignment is impossible).
2. Run the script from the repository root:

```bash
python3 experiment/find_worst_subqueries.py --topk 20
```

3. Open the output file `experiment/checkpoint/StarCE/topk_subqueries_stats.sql`. Each subquery will have a comment header above it:
   - `idx`: **1-based line number** in the original `subquery.sql` / `real.txt` / `card_stats.txt`
   - `true` / `est` / `qerror`: corresponding values
4. Spot-check Top-3:
   - Line `idx` in `subquery.sql` should match the exported SQL text
   - Line `idx` in `real.txt` / `card_stats.txt` should match the `true/est` values in the comment

## Common Parameters

- Specify export count:

```bash
python3 experiment/find_worst_subqueries.py --topk 50
```

- Specify output file:

```bash
python3 experiment/find_worst_subqueries.py --topk 30 --out experiment/checkpoint/StarCE/top30_subqueries_stats.sql
```

## Notes

- This workflow assumes the three input files were generated **line-by-line one-to-one corresponding**. If you changed the subquery generation order or filtered empty lines, you need to regenerate the corresponding files to ensure alignment.

