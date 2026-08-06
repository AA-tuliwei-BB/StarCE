---
name: starce-error-diagnosis
description: Methodology and toolchain for diagnosing estimation bias for a given query: locate problematic query → confirm bias direction → analyze join graph → look up EqualSet statistics → analyze predicate filtering → pinpoint error source (EqualSet itself vs Merge vs predicate handling). Use when mentioning StarCE overestimation/underestimation cause analysis, error diagnosis, Q-Error localization, EqualSet statistics inspection, max_degree, predicate filtering effectiveness.
---

# StarCE Estimation Bias Diagnosis Methodology

## Overall Flow

```
1. Locate problematic query (find_worst_subqueries.py)
2. Confirm bias direction and magnitude
3. Analyze join graph structure → identify AttrEset
4. Find statistics for the corresponding EqualSet
5. Analyze predicate filtering effectiveness
6. Pinpoint error source (EqualSet itself vs Merge vs predicate handling)
```

---

## Step 1: Locate Problematic Query

```bash
python experiment/find_worst_subqueries.py \
  --sql   Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --real  Benchmark/workloads/STATS-CEB/subquery/result/real.txt \
  --est   experiment/checkpoint/StarCE/card_stats.txt \
  --topk  20 \
  --out   experiment/checkpoint/StarCE/topk_subqueries_stats.sql
```

Each SQL in the output file has a comment prefix: `-- idx=N true=X est=Y qerror=Z`

---

## Step 2: Confirm Bias Direction

StarCE theoretically only overestimates (upper bound estimation) and never underestimates. If underestimation occurs, it is usually due to:
- Corrupted or stale statistics file (requires `RefreshStatistics=1` to recollect)
- Predicate parsing failure (`ParsePredicate` threw an exception that was silently caught)

---

## Step 3: Analyze Join Graph → Identify AttrEset

Manually analyze the SQL WHERE clause, merging all join conditions into equivalence classes:

```
Example: badges.UserId = users.Id
    postHistory.UserId = votes.UserId
    posts.OwnerUserId = postHistory.UserId
    votes.UserId = badges.UserId
→ Merged: {badges.UserId, users.Id, postHistory.UserId, votes.UserId, posts.OwnerUserId}

    posts.Id = postLinks.RelatedPostId
→ {posts.Id, postLinks.RelatedPostId}
```

Each equivalence class corresponds to an AttrEset. StarCE looks up the corresponding EqualSet statistics for each.

---

## Step 4: Look Up EqualSet Statistics

```python
import json

with open('experiment/running_space/statistics_stats.json') as f:
    data = json.load(f)

# Find a specific EqualSet
target = {'table1': 'col1', 'table2': 'col2', ...}
for s in data['Statistics']:
    cols = {e['TableName']: e['ColumnName'] for e in s['EqualSet']['Entries']}
    if cols == target:
        print(f"card: {s['DSStatistic']['Cardinality']:.3e}")
        for ds in s['DSStatistic']['DSStatistic']:
            deg = ds['DegreeSequence']
            if deg:
                print(f"  {ds['Table']}: max_degree={max(d['MaxDegree'] for d in deg):.3e}, "
                      f"ndv={sum(d['Count'] for d in deg)}")
```

Key points to check:
- `card`: The EqualSet's cardinality without predicates — the starting point of estimation
- Each table's `max_degree`: larger extreme values lead to more overestimation after predicate filtering
- `ndv`: number of distinct values participating in the join

---

## Step 5: Analyze Predicate Filtering Effectiveness

```sql
-- Query filtered table sizes in DuckDB
SELECT COUNT(*) FROM table1 WHERE <predicates>;
```

Compute retention rate per table (filtered / total). Lower retention rates mean higher predicate selectivity, making StarCE more prone to overestimation.

**High-risk scenario**: A table's retention rate < 30%, and its max_degree in the EqualSet is very large.

---

## Step 6: Pinpoint Error Source

### Case A: EqualSet base cardinality is already overestimated

The EqualSet's `card` is far larger than the true join cardinality without predicates.

Verification method:
```sql
-- Directly query the join cardinality without predicates
SELECT COUNT(*) FROM t1 JOIN t2 ON t1.col = t2.col JOIN t3 ON ...;
```

If the EqualSet card is close to the true value, the problem lies elsewhere.

### Case B: Improper predicate filtering handling (most common)

The EqualSet card is accurate, but the estimate remains high after applying predicates.

Analysis:
1. Find the most selective predicate (table with lowest retention rate)
2. Check that table's `max_degree` in the EqualSet
3. If `max_degree >> filtered_card`, the extreme value cannot be compressed during Merge

Typical case (STATS Q57 subquery 471):
- postHistory predicate retention rate 22.1% (66973/303187)
- In EqualSet A, postHistory.max_degree = 2.78e+8
- After filtering, postHistory has only 66973 rows, but max_degree still dominates Merge result

### Case C: Multi-EqualSet Merge error accumulation

The query's join graph spans multiple EqualSets, with overestimation introduced at each Merge step.

Analysis:
1. List all AttrEsets and their corresponding EqualSet cards
2. Simulate the Merge order (by join graph connectivity)
3. Identify which Merge step introduced the largest error

### Case D: NULL value issue (already fixed)

StarCE's statistics collection already filters NULL (`WHERE col IS NOT NULL`), so this issue should not arise.
If suspected, check:
```sql
SELECT COUNT(*) FROM table WHERE col IS NULL;
```

---

## Common Helper Queries

```sql
-- View frequency distribution of a column (top 10)
SELECT col, COUNT(*) as cnt FROM table GROUP BY col ORDER BY cnt DESC LIMIT 10;

-- View max_freq of a column (non-NULL)
SELECT MAX(cnt) FROM (SELECT col, COUNT(*) as cnt FROM table WHERE col IS NOT NULL GROUP BY col);

-- Verify true join cardinality of two tables
SELECT COUNT(*) FROM t1 JOIN t2 ON t1.col = t2.col;

-- Verify join cardinality with predicates
SELECT COUNT(*) FROM t1 JOIN t2 ON t1.col = t2.col WHERE t1.pred AND t2.pred;
```

---

## Quick Checklist

- [ ] Confirm whether StarCE is overestimating or underestimating
- [ ] Find subqueries with largest Q-Error (find_worst_subqueries.py)
- [ ] Analyze join graph, identify AttrEset equivalence classes
- [ ] Look up corresponding EqualSet statistics (statistics_*.json)
- [ ] Check retention rates of each table's predicates
- [ ] Compare EqualSet max_degree against filtered row counts
- [ ] When necessary, verify true cardinality directly in DuckDB
