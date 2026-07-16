---
name: extract-worst-subqueries
description: 从 STATS-CEB 的真实基数与估计基数文件中计算 Q-Error，找出误差最大的 Top-K 子查询并导出为可手动测试的 .sql 文件。用于排查 StarCE 在 STATS 上误差过大、需要定位“误差最大子查询/TopK子查询/Q-Error/提取子查询/手动测试”时。
---

# Extract Worst Subqueries (STATS-CEB)

## 适用场景

- 你在 STATS-CEB 上发现误差大，怀疑实现问题，需要快速定位 **Q-Error 最大** 的若干子查询，导出出来手工复现测试。

## 输入与输出（默认）

- **子查询 SQL**：`Benchmark/workloads/STATS-CEB/subquery/subquery.sql`（每行一条 `SELECT COUNT(*) ...;`）
- **真实基数**：`Benchmark/workloads/STATS-CEB/subquery/result/real.txt`（每行一个数字）
- **StarCE 估计基数**：`experiment/checkpoint/StarCE/card_stats.txt`（每行一个数字）
- **导出文件**：`experiment/checkpoint/StarCE/topk_subqueries_stats.sql`

## 误差指标（Q-Error）

为避免 0 造成异常，计算前做截断：

- \(t = \max(1, true)\)
- \(e = \max(1, est)\)
- \(qerror = \max(e, t) / \min(e, t)\)（始终 ≥ 1）

## 操作步骤（必须按顺序）

1. 确认输入文件存在，且三者**行数一致**（否则无法逐行对齐）。
2. 在仓库根目录运行脚本：

```bash
python3 experiment/find_worst_subqueries.py --topk 20
```

3. 打开输出文件 `experiment/checkpoint/StarCE/topk_subqueries_stats.sql`，每条子查询上方会有注释：
   - `idx`：在原始 `subquery.sql` / `real.txt` / `card_stats.txt` 中的**1-based 行号**
   - `true` / `est` / `qerror`：对应数值
4. 抽查 Top-3：
   - `subquery.sql` 第 `idx` 行应与导出的 SQL 文本一致
   - `real.txt` / `card_stats.txt` 第 `idx` 行应与注释里的 `true/est` 一致

## 常用参数

- 指定导出条数：

```bash
python3 experiment/find_worst_subqueries.py --topk 50
```

- 指定输出文件：

```bash
python3 experiment/find_worst_subqueries.py --topk 30 --out experiment/checkpoint/StarCE/top30_subqueries_stats.sql
```

## 注意事项

- 这个流程假设三个输入文件是**逐行一一对应**生成的；若你更换了生成子查询的顺序或过滤了空行，需要重新生成对应文件，确保对齐。

