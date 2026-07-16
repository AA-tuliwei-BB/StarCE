---
name: starce-estimation-internals
description: StarCE 估计机制详解：DegreeSequence 度序列压缩表示、DSStatistic 多表 join 统计体、EqualSet 等价类、统计信息收集流程（CollectStatistics）、基数估计流程（EstimateCardinality: AttrEset→DSStatistic→谓词过滤→Merge）、AdjustRate/PredMethod/CompressPrecision 参数含义及已知局限性。当用户提到 StarCE 内部机制、度序列、DSStatistic、EqualSet、Merge 点积、AdjustToAverage、统计收集、估计流程时使用。
---

# StarCE 估计机制详解

## 核心数据结构

### DegreeSequence（度序列）

`statistic.hpp` 中定义。压缩表示一列值的频率分布：

```
maxDegree: [d1, d2, d3, ...]   // 每个桶的最大度（降序）
count:     [c1, c2, c3, ...]   // 每个桶中有多少个不同值
```

- `GetCard()` = Σ count[i] × maxDegree[i]（总行数）
- `GetNDV()` = Σ count[i]（不同值数量）
- `AddDegree(degree, count, precision)` 按 log(precision) 分桶压缩
- `dot(other)` 对两个度序列做点积（用于 join 上界估计）

### DSStatistic（多表 join 统计体）

每个 EqualSet 对应一个 DSStatistic，包含：

- `card`：该 join 的真实基数（收集阶段计算）
- `ds[table]`：每张表的度序列，表示"该表某个 join key 值在 join 结果中对应多少行"
- `centralDs`：中心表的度序列（用于 StarSplit 模式）

### EqualSet

一组 `(TableName, ColumnName)` 对，表示 schema 中通过 join 条件等价的列集合。例如：

```
{badges.UserId, users.Id, postHistory.UserId, votes.UserId}
```

StarCE 在 schema 分析阶段预先枚举所有 EqualSet 的子集，并为每个子集收集 DSStatistic。

---

## 统计信息收集（main.cpp: CollectStatistics）

对每个 EqualSet，执行如下 SQL 收集度序列：

```sql
-- 对每张表按 join key 分组，统计每个值的出现次数
SELECT val, table1_cnt, table2_cnt, ..., COUNT(*) AS freq
FROM (
  SELECT val, SUM(CASE WHEN tbl='t1' THEN cnt ELSE 0 END) AS t1_cnt, ...
  FROM (
    SELECT col AS val, 't1' AS tbl, COUNT(*) AS cnt FROM t1 WHERE col IS NOT NULL GROUP BY col
    UNION ALL ...
  ) GROUP BY val
) GROUP BY table1_cnt, table2_cnt, ...
```

**注意**：收集时已过滤 NULL 值（`WHERE col IS NOT NULL`）。

对每个 `(t1_cnt, t2_cnt, ...)` 组合，调用 `DSStatistic::AddDegree`：

```cpp
// 对每张表，degree = 其他所有表的 cnt 之积
ds[table].AddDegree(product / table_cnt, table_cnt * freq)
card += product * freq
```

收集完成后调用 `FinishCollection()`，对度序列降序排列并截断到 card 上界。

统计信息序列化到 `experiment/running_space/statistics_{benchmark}.json`。

---

## 基数估计（starce.hpp: EstimateCardinality）

输入：当前查询涉及的表 ID 列表 `rels`。

**Step 1：识别 AttrEset（join 列等价类）**

`GetAttrEsetFromRels(rels)` 从全局 `attrEsets`（由 `AddPredicate` 构建）中提取当前查询的等价类。每个 AttrEset 对应一个 EqualSet。

**Step 2：加载 DSStatistic**

对每个 AttrEset，调用 `GetStatisticsFromEset(eset)` 从预收集的统计信息中加载对应的 DSStatistic。

**Step 3：应用谓词过滤（PredMethod=0，默认）**

对有谓词的表：
```cpp
singleStats = DSStatistic(table_id, GetTableCard(table_id))  // 过滤后单表基数
singleStats.AdjustToAverage(relNDV, PredicateAdjustRate)
dsStats[i].Merge(singleStats, table_id)
```

`AdjustToAverage` 将度序列的极端值向均值方向收缩：
```
maxDegree[i] = maxDegree[i] × k + avgDegree × (1 - k)
```
其中 `k = PredicateAdjustRate`（默认等于 AdjustRate，约 0.1）。

**Step 4：Merge 多个 AttrEset**

当两个 AttrEset 共享同一张表时，通过该表的度序列进行 Merge：

```cpp
// 对共享表的度序列做点积
newCard += count × degree1 × degree2
```

这是一个上界估计：假设两侧的度序列独立，实际 join 结果 ≤ 点积结果。

**Step 5：返回所有根节点的 card 乘积**

---

## 关键参数

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `AdjustRate` | 从统计信息中读取（约 0.1） | Merge 后向均值收缩的比例 |
| `PredicateAdjustRate` | 同 AdjustRate | 谓词过滤时的收缩比例 |
| `CompressPrecision` | 2.0 | 度序列分桶精度（log 底数） |
| `PredMethod` | 0 | 0=调整率，1=均匀假设 |
| `EnableStarSplit` | false | 是否将大 EqualSet 拆分为 star 子集 |

---

## 已知局限性

### 1. 高选择性谓词下度序列失效

EqualSet 的度序列基于无谓词的 schema 统计。当某张表的谓词选择性很高（如保留 20% 的行），Merge 操作中该表的极端 max_degree 无法被有效压缩，导致高估。

典型案例：STATS Q57，postHistory 谓词将行数压缩到 22.1%，但 EqualSet A（5 表 UserId join）中 postHistory 的 max_degree = 2.78e+8，Merge 后估计值比真实值高 1000x+。

### 2. 多 EqualSet Merge 的误差累积

当查询的 join 图跨越多个 EqualSet 时，每次 Merge 都可能引入高估，误差在多步 Merge 中累积放大。

### 3. 不同 EqualSet 间的相关性被忽略

Merge 假设两个 EqualSet 的度序列独立，但实际数据中不同 join 列之间可能存在相关性（如同一用户在多张表中的活跃度相关）。
