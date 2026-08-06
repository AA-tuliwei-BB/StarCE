---
name: starce-estimation-internals
description: Detailed explanation of StarCE estimation mechanisms: DegreeSequence compressed degree sequence representation, DSStatistic multi-table join statistics, EqualSet equivalence classes, statistics collection flow (CollectStatistics), cardinality estimation flow (EstimateCardinality: AttrEset→DSStatistic→predicate filtering→Merge), AdjustRate/PredMethod/CompressPrecision parameter meanings, and known limitations. Use when mentioning StarCE internals, degree sequence, DSStatistic, EqualSet, Merge dot product, AdjustToAverage, statistics collection, estimation flow.
---

# StarCE Estimation Mechanism Details

## Core Data Structures

### DegreeSequence

Defined in `statistic.hpp`. Compressed representation of frequency distribution for a column's values:

```
maxDegree: [d1, d2, d3, ...]   // Max degree per bucket (descending)
count:     [c1, c2, c3, ...]   // Number of distinct values in each bucket
```

- `GetCard()` = Σ count[i] × maxDegree[i] (total row count)
- `GetNDV()` = Σ count[i] (number of distinct values)
- `AddDegree(degree, count, precision)` compresses into buckets by log(precision)
- `dot(other)` computes dot product of two degree sequences (for join upper bound estimation)

### DSStatistic (Multi-Table Join Statistics)

Each EqualSet corresponds to one DSStatistic, containing:

- `card`: true cardinality of this join (computed during collection phase)
- `ds[table]`: degree sequence per table, representing "how many rows a given join key value corresponds to in the join result"
- `centralDs`: degree sequence of the central table (used in StarSplit mode)

### EqualSet

A set of `(TableName, ColumnName)` pairs, representing columns in the schema that are equivalent via join conditions. Example:

```
{badges.UserId, users.Id, postHistory.UserId, votes.UserId}
```

StarCE pre-enumerates all EqualSet subsets during schema analysis and collects DSStatistic for each subset.

---

## Statistics Collection (main.cpp: CollectStatistics)

For each EqualSet, execute the following SQL to collect degree sequences:

```sql
-- For each table, group by join key and count occurrences per value
SELECT val, table1_cnt, table2_cnt, ..., COUNT(*) AS freq
FROM (
  SELECT val, SUM(CASE WHEN tbl='t1' THEN cnt ELSE 0 END) AS t1_cnt, ...
  FROM (
    SELECT col AS val, 't1' AS tbl, COUNT(*) AS cnt FROM t1 WHERE col IS NOT NULL GROUP BY col
    UNION ALL ...
  ) GROUP BY val
) GROUP BY table1_cnt, table2_cnt, ...
```

**Note**: NULL values are filtered during collection (`WHERE col IS NOT NULL`).

For each `(t1_cnt, t2_cnt, ...)` combination, `DSStatistic::AddDegree` is called:

```cpp
// For each table, degree = product of all other tables' cnt
ds[table].AddDegree(product / table_cnt, table_cnt * freq)
card += product * freq
```

After collection, `FinishCollection()` is called to sort degree sequences in descending order and truncate to the card upper bound.

Statistics are serialized to `experiment/running_space/statistics_{benchmark}.json`.

---

## Cardinality Estimation (starce.hpp: EstimateCardinality)

Input: list of table IDs `rels` involved in the current query.

**Step 1: Identify AttrEset (join column equivalence classes)**

`GetAttrEsetFromRels(rels)` extracts the query's equivalence classes from global `attrEsets` (built by `AddPredicate`). Each AttrEset corresponds to an EqualSet.

**Step 2: Load DSStatistic**

For each AttrEset, call `GetStatisticsFromEset(eset)` to load the corresponding DSStatistic from pre-collected statistics.

**Step 3: Apply Predicate Filtering (PredMethod=0, default)**

For tables with predicates:
```cpp
singleStats = DSStatistic(table_id, GetTableCard(table_id))  // filtered single-table cardinality
singleStats.AdjustToAverage(relNDV, PredicateAdjustRate)
dsStats[i].Merge(singleStats, table_id)
```

`AdjustToAverage` shrinks the degree sequence's extreme values toward the mean:
```
maxDegree[i] = maxDegree[i] × k + avgDegree × (1 - k)
```
where `k = PredicateAdjustRate` (default equals AdjustRate, approximately 0.1).

**Step 4: Merge Multiple AttrEsets**

When two AttrEsets share a common table, they are merged through that table's degree sequence:

```cpp
// Dot product of the shared table's degree sequences
newCard += count × degree1 × degree2
```

This is an upper bound estimate: assuming independence of degree sequences on both sides, the actual join result ≤ the dot product result.

**Step 5: Return product of all root node cards**

---

## Key Parameters

| Parameter | Default | Meaning |
|------|--------|------|
| `AdjustRate` | Read from statistics file (~0.1) | Shrinkage ratio toward mean after Merge |
| `PredicateAdjustRate` | Same as AdjustRate | Shrinkage ratio during predicate filtering |
| `CompressPrecision` | 2.0 | Degree sequence bucketing precision (log base) |
| `PredMethod` | 0 | 0=adjustment rate, 1=uniformity assumption |
| `EnableStarSplit` | false | Whether to split large EqualSets into star subsets |

---

## Known Limitations

### 1. Degree Sequence Breakdown Under Highly Selective Predicates

Degree sequences in EqualSets are based on schema statistics without predicates. When a table's predicate selectivity is very high (e.g., retaining 20% of rows), the table's extreme max_degree in Merge cannot be effectively compressed, leading to overestimation.

Typical case: STATS Q57, postHistory predicate compresses rows to 22.1%, but in EqualSet A (5-table UserId join), postHistory's max_degree = 2.78e+8, and the post-Merge estimate exceeds the true value by 1000x+.

### 2. Multi-EqualSet Merge Error Accumulation

When a query's join graph spans multiple EqualSets, overestimation may be introduced at each Merge step, with errors accumulating and amplifying across multiple Merges.

### 3. Correlation Between Different EqualSets Ignored

Merge assumes independence of degree sequences across two EqualSets, but in real data, different join columns may be correlated (e.g., the same user's activity level correlated across multiple tables).
