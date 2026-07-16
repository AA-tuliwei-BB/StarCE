# StarCE 估计偏差排查方法论

## 总体流程

```
1. 定位问题查询（find_worst_subqueries.py）
2. 确认偏差方向和量级
3. 分析 join 图结构 → 识别 AttrEset
4. 查找对应 EqualSet 的统计信息
5. 分析谓词过滤效果
6. 定位误差来源（EqualSet 本身 vs Merge vs 谓词处理）
```

---

## Step 1：定位问题查询

```bash
python experiment/find_worst_subqueries.py \
  --sql   Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --real  Benchmark/workloads/STATS-CEB/subquery/result/real.txt \
  --est   experiment/checkpoint/StarCE/card_stats.txt \
  --topk  20 \
  --out   experiment/checkpoint/StarCE/topk_subqueries_stats.sql
```

输出文件中每条 SQL 前有注释：`-- idx=N true=X est=Y qerror=Z`

---

## Step 2：确认偏差方向

StarCE 理论上只会高估（上界估计），不会低估。如果出现低估，通常是：
- 统计信息文件损坏或过期（需要 `RefreshStatistics=1` 重新收集）
- 谓词解析失败（`ParsePredicate` 抛出异常被忽略）

---

## Step 3：分析 join 图 → 识别 AttrEset

手动分析 SQL 的 WHERE 子句，将所有 join 条件合并为等价类：

```
例：badges.UserId = users.Id
    postHistory.UserId = votes.UserId
    posts.OwnerUserId = postHistory.UserId
    votes.UserId = badges.UserId
→ 合并后：{badges.UserId, users.Id, postHistory.UserId, votes.UserId, posts.OwnerUserId}

    posts.Id = postLinks.RelatedPostId
→ {posts.Id, postLinks.RelatedPostId}
```

每个等价类对应一个 AttrEset，StarCE 会为其查找对应的 EqualSet 统计信息。

---

## Step 4：查找 EqualSet 统计信息

```python
import json

with open('experiment/running_space/statistics_stats.json') as f:
    data = json.load(f)

# 查找特定 EqualSet
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

关注点：
- `card`：该 EqualSet 的无谓词基数，是估计的起点
- 各表的 `max_degree`：极端值越大，谓词过滤后越容易高估
- `ndv`：参与 join 的不同值数量

---

## Step 5：分析谓词过滤效果

```sql
-- 在 DuckDB 中查询各表过滤后大小
SELECT COUNT(*) FROM table1 WHERE <predicates>;
```

计算各表的保留率（filtered / total）。保留率越低，谓词选择性越高，StarCE 越容易高估。

**高风险场景**：某张表的保留率 < 30%，且该表在 EqualSet 中的 max_degree 很大。

---

## Step 6：定位误差来源

### 情形 A：EqualSet 本身基数就已高估

EqualSet 的 `card` 远大于真实的无谓词 join 基数。

验证方法：
```sql
-- 直接查询无谓词的 join 基数
SELECT COUNT(*) FROM t1 JOIN t2 ON t1.col = t2.col JOIN t3 ON ...;
```

若 EqualSet card 与真实值接近，则问题不在这里。

### 情形 B：谓词过滤处理不当（最常见）

EqualSet card 准确，但应用谓词后估计值仍然很高。

分析：
1. 找出选择性最高的谓词（保留率最低的表）
2. 查看该表在 EqualSet 中的 `max_degree`
3. 若 `max_degree >> filtered_card`，则 Merge 时该极端值无法被压缩

典型案例（STATS Q57 subquery 471）：
- postHistory 谓词保留率 22.1%（66973/303187）
- EqualSet A 中 postHistory.max_degree = 2.78e+8
- 过滤后 postHistory 只有 66973 行，但 max_degree 仍主导 Merge 结果

### 情形 C：多 EqualSet Merge 误差累积

查询的 join 图跨越多个 EqualSet，每次 Merge 都引入高估。

分析：
1. 列出所有 AttrEset 及其对应的 EqualSet card
2. 模拟 Merge 顺序（按 join 图的连通性）
3. 找出哪一步 Merge 引入了最大的误差

### 情形 D：NULL 值问题（已修复）

StarCE 的统计收集已过滤 NULL（`WHERE col IS NOT NULL`），此问题不应出现。
若怀疑，可检查：
```sql
SELECT COUNT(*) FROM table WHERE col IS NULL;
```

---

## 常用辅助查询

```sql
-- 查看某列的频率分布（top 10）
SELECT col, COUNT(*) as cnt FROM table GROUP BY col ORDER BY cnt DESC LIMIT 10;

-- 查看某列的 max_freq（非 NULL）
SELECT MAX(cnt) FROM (SELECT col, COUNT(*) as cnt FROM table WHERE col IS NOT NULL GROUP BY col);

-- 验证两表 join 的真实基数
SELECT COUNT(*) FROM t1 JOIN t2 ON t1.col = t2.col;

-- 验证带谓词的 join 基数
SELECT COUNT(*) FROM t1 JOIN t2 ON t1.col = t2.col WHERE t1.pred AND t2.pred;
```

---

## 快速检查清单

- [ ] 确认 StarCE 是高估还是低估
- [ ] 找出 Q-Error 最大的子查询（find_worst_subqueries.py）
- [ ] 分析 join 图，识别 AttrEset 等价类
- [ ] 查找对应 EqualSet 的统计信息（statistics_*.json）
- [ ] 检查各表谓词的保留率
- [ ] 对比 EqualSet max_degree 与过滤后行数
- [ ] 必要时直接在 DuckDB 中验证真实基数
