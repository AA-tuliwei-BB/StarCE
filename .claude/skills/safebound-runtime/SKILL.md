# SafeBound Runtime 实验流水线

## 1. 概述

`methods/SafeBound/` 下的 PostgreSQL 端对端实验流水线。将基数估计值通过 pg_hint_plan `/*+ Rows() */` 注入 PG 优化器，测量 JOBM 查询的**实际执行时间**。对比三种基数估计方法对 PG 执行计划质量的影响。

## 2. 关键文件

| 文件 | 用途 |
|------|------|
| `Source/ExperimentUtils/RuntimeUtils.py` | 入口 `evaluate_runtime()` + 各方法实现。`reset_cache()` 也在其中 |
| `Source/DBConnectionUtils.py` | `getDBConn()` 连接 PG，`getSizeEstimate()` (EXPLAIN)，`getSizeEstimateAndActual()` (EXPLAIN + 实际执行) |
| `Source/ExperimentUtils/BuildUtils.py` | `build_stats_object()` 构建 SafeBound/Simplicity/PG 统计对象，存为 `.pkl` |
| `Source/ExperimentUtils/TrueCardUtils.py` | `gather_true_cardinalities()` 预收集真实基数，存为 `TrueCardinality_JOBM.pkl` |
| `Source/SafeBoundUtils.pyx` | `SafeBound` 类 (Cython)，`functionalFrequencyBound()` 产生保守上界估计 |
| `Source/JoinGraphUtils.pyx` | `JoinQueryGraph`、`JoinHint`、`getIntermediateQueries()` — 枚举 join graph 所有连通子图 |
| `Source/SQLParser.py` | `SQLFileToJoinQueryGraphs()` — 解析 workload SQL 文件 |
| `Workloads/JOBMQueries.sql` | 113 条 JOBM 查询 |
| `run_cold.py` | 我们的 JOBM 冷启动脚本，依次调用 `evaluate_runtime()` |

## 3. 三种方法对比

三种都通过 pg_hint_plan `/*+ Rows() */` 注入，测量 `getSizeEstimateAndActual()` 的耗时（EXPLAIN + SELECT COUNT(*)）。

### TC (TrueCardinality)
- 从 `StatObjects/TrueCardinality_JOBM.pkl` 加载预收集的真实基数
- 无运行时估计开销 (InferenceTime = -1)
- **热缓存: 0.88s** — 最快
- **冷缓存: 6.66s (7.6x 退化)** — 精确小基数 → Nested Loop → HDD 随机 I/O 灾难

### SB (SafeBound)
- 运行时调用 `functionalFrequencyBound()` 对每个中间子查询产生保守上界
- 保守上界 → PG 偏好 Hash Join → 顺序 I/O
- **热缓存: 1.15s**，**冷缓存: 4.01s (3.5x 退化)** — 冷缓存最优

### PG (Postgres)
- 对每个中间子查询调用 `getSizeEstimate()` 获取 PG 自身估计 → 注回 pg_hint_plan
- 含 per-subquery EXPLAIN 和 hint 解析开销 (~0.65s/查询)
- **热缓存: 1.74s**，**冷缓存: 7.99s**
- PG native (无 hint、无子查询 EXPLAIN) 为 ~1.09s，与 pg-end2end 吻合

## 4. 环境搭建

### PG 配置 (SafeBound README 推荐)
```
shared_buffers = 4GB
work_mem = 2GB
effective_cache_size = 32GB
max_parallel_workers = 6
```

### 数据库部署
按 `CreateJOBBenchmark.bash` 顺序：
1. `createdb imdb`
2. `psql imdb -f Data/IMDB/schema.sql`
3. `psql imdb -f Data/IMDB/imdb_create.sql` (\copy CSV)
4. `psql imdb -f Data/IMDB/fkindexes.sql`
5. `psql -f Data/IMDB/CreateJOBMDB.sql` → 生成 `imdbm`
6. `ANALYZE`

### pg_hint_plan
```bash
git clone https://github.com/ossc-db/pg_hint_plan.git -b PG13
cd pg_hint_plan && make PG_CONFIG=/usr/local/pgsql/13.1/bin/pg_config
sudo make install PG_CONFIG=/usr/local/pgsql/13.1/bin/pg_config
```
在 `postgresql.conf` 中设置: `shared_preload_libraries = 'pg_hint_plan'`

### sudoers (reset_cache 免密)
```
liwei ALL=(root) NOPASSWD: /usr/bin/systemctl restart postgresql-13
liwei ALL=(root) NOPASSWD: /usr/bin/sh
```

## 5. 我们对原始脚本的修改

### Bug 修复: `rootDirectory` → `rootFileDirectory`
`InferenceUtils.py` 和 `RuntimeUtils.py` 中引用了未定义的变量 `rootDirectory` (应为 `rootFileDirectory`)，导致 `NameError`。共修复 ~33 处。

### 环境适配: Socket 路径
`DBConnectionUtils.py` 中 PG socket 从 `/var/run/postgresql` 改为 `/tmp`。

### 无侵入修改
`reset_cache()` 保持原始顺序 (drop_caches → restart PG)。所有修改均不改变原有实验逻辑。

## 6. 运行实验

> **注意**: `evaluate_runtime()` 在第 0 轮也会调用 `reset_cache()`（drop_caches + restart PG），
> 所以即使 `runs=1` 也是冷启动。热缓存需要跳过 `reset_cache()` 的手动脚本。

### 冷缓存（原版 SafeBound Runtime）
```bash
cd methods/SafeBound
conda run -n TestEnv python run_cold.py   # runs=2 或 5
```
`run_cold.py` 调用 `evaluate_runtime()`，自动 `reset_cache()` / `dbConn.reset()` / `changeStatisticsTarget()` / CSV 输出。

### 热缓存（手动计时，无 reset_cache）
```python
from DBConnectionUtils import getDBConn
# ... 加载 hints，直接调 getSizeEstimateAndActual()，无中间重启
```
当前无独立热缓存脚本（`run_jobm_warm.py` 已删除），需要时从 REPORT.md 中的数据复现。

### 输出格式
CSV 列: `QueryLabel`, `RunLabel`, `InferenceTime`, `Runtime`, `StatsSize`

## 7. 关键发现

```
热缓存: TC (0.88s) < SB (1.15s) < PG (1.74s)
冷缓存: SB (4.01s) < TC (6.66s) < PG (7.99s)
```

- TC 热快冷慢：精确小基数 → Nested Loop → HDD 冷缓存随机 I/O
- SB 冷缓存最优：保守上界 → Hash Join → 顺序 I/O
- pg_hint_plan Rows hint 额外开销 ~0.65s/查询
- pg_hint_plan 与 C 代码注入的计划结构完全一致

## 8. 关联 Skills

- [[pg-end2end]] — C 代码 key-value 注入流水线
- [[postgresql-env]] — PG 环境详情
- [[benchmark-datasets]] — JOBM 数据集
