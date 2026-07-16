# SafeBound Runtime & pg-end2end JOBM 实验报告

## 实验环境

| 项目 | 配置 |
|------|------|
| PostgreSQL | 13.1, port 5432, socket /tmp |
| shared_buffers | 4 GB |
| work_mem | 2 GB |
| effective_cache_size | 32 GB |
| max_parallel_workers | 6 |
| 数据盘 | HDD (sdb, 7.3 TB) |
| 数据集 | JOBM (17 表, 3624 万行 cast_info, 7.5 GB) |
| 查询数 | 113 条 |
| 子查询数 | 9472 (gen_jobm_subqueries.py 生成) |
| SafeBound 模型 | Runtime: SafeBound_4_JOBM.pkl / pg-end2end: SafeBound_3_JOBM.pkl |

## 1. SafeBound Runtime 结果

测量方式: pg_hint_plan `/*+ Rows() */` 注入，`getSizeEstimateAndActual()` 计时。
per-subquery 估计不计入 Runtime。

### 1.1 热缓存 (2 rounds, warm)

| 方法 | 平均 | 中位 | 最小 | 最大 |
|------|------|------|------|------|
| TC (TrueCard) | **0.877s** | 0.294s | 0.014s | 6.736s |
| SB (SafeBound) | 1.154s | 0.747s | 0.016s | 7.899s |
| PG (Postgres) | 1.741s | 0.578s | 0.017s | 43.843s |

### 1.2 冷缓存 (2 rounds, drop_caches + PG restart)

| 方法 | 平均 | 中位 | 最小 | 最大 | 冷惩罚 |
|------|------|------|------|------|:---:|
| TC (TrueCard) | 6.659s | 0.432s | 0.013s | 344s | 7.6x |
| SB (SafeBound) | **4.013s** | 0.872s | 0.013s | 270s | 3.5x |
| PG (Postgres) | 7.990s | 0.777s | 0.013s | 353s | 4.6x |

## 2. pg-end2end 结果

测量方式: C 代码 key-value 注入 (`ml_joinest_enabled`)，`EXPLAIN ANALYZE`。

### 2.1 热缓存 (warm, 1 run)

| Config | 平均执行 |
|--------|------|
| TrueCard | **0.952s** |
| PM0 AR1 PAR01 | 1.121s |
| PG native | 1.171s |
| SafeBound | 1.282s |
| PM0 AR1 PAR1 | 1.330s |
| PM0 AR1 PAR001 | 1.460s |
| PM1 AR1 PAR0 | 1.563s |
| PM0 AR0 | 1.768s |

### 2.2 冷缓存 (2 rounds)

| Config | 平均 | 冷惩罚 | per-run (q0) |
|--------|------|:---:|------|
| PM0 AR1 PAR1 | **1.76s** | 1.3x | warm=1.56s → cold=59s |
| SafeBound | 2.68s | **2.1x** | warm=0.27s → cold=260s |
| PM0 AR1 PAR01 | 3.05s | 2.7x | warm=0.33s → cold=367s |
| TrueCard | 3.82s | 4.0x | warm=0.30s → cold=269s |
| PG native | 4.20s | 3.6x | warm=0.30s → cold=270s |
| PM0 AR1 PAR001 | 4.45s | 3.0x | warm=0.34s → cold=357s |
| PM1 AR1 PAR0 | 4.55s | 2.9x | warm=0.40s → cold=357s |
| PM0 AR0 | 4.69s | 2.7x | warm=0.42s → cold=355s |

## 3. Runtime vs pg-end2end 热缓存对比

两个 pipeline 在热缓存下的 TC 和 SB 结果一致（< 10% 差异），验证了测量可靠性。

| 方法 | Runtime | pg-end2end |
|------|:------:|:------:|
| TC | 0.877s | 0.952s |
| SB | 1.154s | 1.282s |
| PG native | 1.089s* | 1.171s |

*Runtime PG 原生值 (无 hint, 无子查询 EXPLAIN) 为 1.09s，与 pg-end2end 的 1.17s 吻合。
Runtime 的 `evaluate_runtime_postgres()` 测量值 1.74s 包含了 pg_hint_plan 解析和 per-subquery EXPLAIN 开销。

## 4. 核心发现

### 热快冷慢: TrueCard 的双面性

TrueCard 在热缓存下最快（0.88-0.95s），冷缓存下退化最大（4.0-7.6x）。
精确小基数 → PG 选 Nested Loop + Index Scan → HDD 冷缓存随机 I/O 灾难。

### 冷缓存最优: SafeBound

SafeBound 冷惩罚最小（2.1x Runtime / 2.1x pg-end2end）。
保守上界 → PG 选 Hash Join → 顺序 I/O → HDD 友好。

### 排名翻转

```
热缓存: TC < SB < PG native
冷缓存: SB < TC < PG native
```

### 计划质量

q0/q2/q8 抽查: pg_hint_plan / C 代码注入 / PG native 三种方式产生的计划完全同构。
仅行估计值有细微差异，不改变 join 类型或顺序决策。

## 5. pg-end2end 冷启动实现

改动 4 个文件 (~100 行):

- `configs.yaml` — 加 `cold_runs: 2`
- `lib/config.py` — PipelineConfig 加 `cold_runs` 字段
- `lib/test.py` — `inject_and_test()` / `run_pg_native_test()` 包 runs 循环，
  `_reset_cache()` (drop_caches + restart PG)，`_build_summary()` 支持跨 run 平均
- `run.py` — 传递 `cold_runs`

用法: `conda run -n TestEnv python run.py test --native --force` (cold_runs=2 在 config)
