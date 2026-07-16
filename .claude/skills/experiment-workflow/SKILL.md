---
name: experiment-workflow
description: StarCE 实验流程总览：实验目录结构、ExperimentRunner.py 核心驱动逻辑、各 Test notebook（TestStarCE/TestDuckDB/TestSafebound/TestPostgreBasic）的操作流程、各 Evaluate notebook（EvaluateAccuracy/EvaluateCompress/EvaluateBuild/EvaluatePerformance）的分析方式，以及 checkpoint 目录的文件组织。当用户提到实验流程、如何运行实验、ExperimentRunner、基数收集、Q-Error 计算、精度对比、构建时间、性能测试、find_worst_subqueries 时使用。
---

# StarCE 实验流程

## 总体架构

实验分两个阶段：**基数收集**（Test notebooks）→ **结果分析**（Evaluate notebooks）。

```
阶段一：各方法基数收集
  TestStarCE.ipynb       → checkpoint/StarCE/card_*.txt
  TestDuckDB.ipynb       → checkpoint/DuckDB/card_*.txt
  TestSafebound.ipynb    → checkpoint/SafeBound/SafeBound_3_*_evaluate_results.txt
  TestPostgreBasic.ipynb → checkpoint/Postgre/card_*.txt

阶段二：结果分析与可视化
  EvaluateAccuracy.ipynb   → Q-Error boxplot + histogram（精度对比）
  EvaluateCompress.ipynb   → CompressPrecision 参数敏感性
  EvaluateBuild.ipynb      → 构建时间 + 统计信息大小
  EvaluatePerformance.ipynb → 计划时间 + 执行时间端到端对比

辅助工具
  ExperimentRunner.py      → 核心驱动模块（被所有 Test notebook 调用）
  find_worst_subqueries.py → 定位误差最大的 Top-K 子查询
  init_experiments.sh      → 初始化 running_space（建库、复制可执行文件）
```

---

## 目录结构

```
experiment/
├── running_space/          ← StarCE 工作目录，所有相对路径以此为基准
│   ├── config.json         ← 每次运行前由 ExperimentRunner 写入
│   ├── starce / duckdb     ← 可执行文件
│   ├── statistics_*.json   ← StarCE 统计信息缓存
│   ├── dummy_query.sql     ← 空文件，用于测量启动开销
│   └── dummy_result.txt    ← 空文件，占位用
├── checkpoint/             ← 各方法结果持久化
│   ├── StarCE/
│   │   ├── card_stats.txt / card_jobm.txt / card_joblight.txt / card_joblr.txt
│   │   ├── benchmark_times.csv
│   │   └── compress_precision/{benchmark}/card_{benchmark}_cp{val}.txt
│   ├── DuckDB/             ← card_*.txt
│   ├── SafeBound/
│   │   ├── SafeBound_3_{benchmark}.pkl
│   │   ├── SafeBound_3_{benchmark}_evaluate_results.txt
│   │   └── benchmark_times.csv
│   ├── Postgre/
│   │   ├── card_*.txt
│   │   └── pg_stats_summary.csv
│   └── figures/            ← 所有生成的 PDF 图表
├── ExperimentRunner.py     ← 核心驱动模块
├── find_worst_subqueries.py
├── init_experiments.sh
├── TestStarCE.ipynb
├── TestDuckDB.ipynb
├── TestSafebound.ipynb
├── TestPostgreBasic.ipynb
├── EvaluateAccuracy.ipynb
├── EvaluateCompress.ipynb
├── EvaluateBuild.ipynb
└── EvaluatePerformance.ipynb
```

---

## ExperimentRunner.py

所有 Test notebook 的核心依赖，提供三个抽象层次。

### `StarCEConfig`（dataclass）

映射 `running_space/config.json` 的全部字段，额外提供：
- `to_json_file(path)` — 序列化写入 config.json
- `copy()` / `update(**kwargs)` — 不可变式派生新配置
- `from_json_file(path)` — 反序列化

### `ExperimentRunner`（ABC）

**目录常量**（`__init__` 中确定）：
- `script_dir` = `experiment/`
- `running_space` = `experiment/running_space/`
- `checkpoint_dir` = `experiment/checkpoint/`
- `benchmark_dir` = `Benchmark/`

**核心方法**：

| 方法 | 说明 |
|------|------|
| `save_config(config)` | 将 `StarCEConfig` 写入 `running_space/config.json` |
| `run_starce()` | 在 `running_space/` 执行 `./starce`，返回 `(success, elapsed_sec)` |
| `_prepare_input_sql_with_explain(src, dst)` | 对 src 中每条 SQL 加 `EXPLAIN` 前缀写入 dst |
| `_prepare_input_sql_without_explain(src, dst)` | 直接复制（用于测实际执行时间） |
| `inner_test_planning_time(config, ...)` | 计划时间 = EXPLAIN运行时间 − dummy_query.sql 运行时间 |
| `inner_test_running_time(config, ...)` | 执行时间 = 普通SQL运行时间 − EXPLAIN运行时间 |

**Workload 配置工厂方法**（返回预填充的 `StarCEConfig`）：
- `get_stats_config()` — STATS-CEB，stats.db
- `get_jobm_config()` — JOBM，imdb.db
- `get_joblight_config()` — JOBLight，imdb.db（轻量 schema）
- `get_joblight_ranges_config()` — JOBLightRanges，imdb.db

### 子类

**`StarCETestRunner`**（`EnableStarCE=1`）：
- `inner_test_build_time(config, db_name, num_runs)` — `RefreshStatistics=1`，测统计收集时间和文件大小
- `get_est_cards(benchmark)` — `RecordingSubquery=1` + EXPLAIN 模式运行，结果写入 `checkpoint/StarCE/card_*.txt`

**`DuckDBTestRunner`**（`EnableStarCE=0`）：
- 与 StarCETestRunner 同接口，但关闭 StarCE，测量 DuckDB 原生性能
- `test_build_time()` 为空操作（DuckDB 无构建步骤）

**`InjectionTestRunner`**（`UseSubqueryCard=1`）：
- `inner_test_planning_time_with_injection(config, ..., injected_card_path, card_est_time)` — 注入外部基数，计划时间额外加上估计器本身耗时
- 用于在相同 DuckDB 框架下测试 SafeBound/FactorJoin 的端到端性能

### `setup_starce_executable(project_root, running_space)`

从 `build/starce` 复制可执行文件到 `running_space/starce` 并赋权 `0o755`。

---

## 各 Test Notebook 流程

### TestStarCE.ipynb

```
1. Build 阶段
   for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
       config = get_{benchmark}_db_config()
       config.RefreshStatistics = 1
       inner_test_build_time(config, db_name)
       → 记录构建时间 + statistics_*.json 文件大小

2. Evaluate 阶段（get_est_cards）
   for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
       - 将 subquery.sql 加 EXPLAIN 前缀
       - RecordingSubquery=1，SUBQUERY_RESULT_PATH → 输出文件
       - run_starce() → 读取每条子查询的 StarCE 估计基数
       → checkpoint/StarCE/card_{benchmark}.txt

3. 汇总 → checkpoint/StarCE/benchmark_times.csv
```

### TestDuckDB.ipynb

```
for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
    1. 将 subquery.sql 加 EXPLAIN 前缀 → running_space/explain.sql
    2. subprocess.run([duckdb_exec, db_path], stdin=explain.sql)
    3. extract_card_from_explain.process_data() 解析输出
       （匹配 "\d+ Rows" 模式，以 "\n\n" 分割查询块）
    4. 写 checkpoint/DuckDB/card_{benchmark}.txt
```

DuckDB 不经过 StarCE，直接调用 `duckdb` 可执行文件，解析 EXPLAIN 文本提取估计行数。

### TestSafebound.ipynb

```
1. Build 阶段
   for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
       build_stats_object(method, benchmark, parameters)
       → checkpoint/SafeBound/SafeBound_3_{benchmark}.pkl

2. Evaluate 阶段
   for benchmark:
       pkl = pickle.load(SafeBound_3_{benchmark}.pkl)
       for sql in subquery_file:
           - Stats: sql_to_joingraph(sql)  ← 自定义解析器
           - 其余: SQLQueriesToJoinQueryGraphs(sql)  ← SafeBound 库
           card = pkl.functionalFrequencyBound(query)
       → checkpoint/SafeBound/SafeBound_3_{benchmark}_evaluate_results.txt

3. 汇总 → checkpoint/SafeBound/benchmark_times.csv
```

注意：Stats/JOBM 使用 `subquery.sql`；JOBLight/JOBLightRanges 使用 `subquery2.sql`。

### TestPostgreBasic.ipynb

```
连接信息：host=127.0.0.1 port=5432，psql=/usr/local/pgsql/13.1/bin/psql
数据库映射：STATS→stats，JOBLight→imdblight，JOBLightRanges→imdblightranges，JOBM→imdbm

for benchmark:
    1. ANALYZE（收集 PG 统计信息，PG_PARALLELISM=8）
    2. 转换 SQL：count(*) → *，加 EXPLAIN 前缀
    3. psql -f explain.sql -o pg_{benchmark}_explain.txt
    4. extract_card_from_pg_plan.extract_cardinalities() 解析计划文本
    5. 写 checkpoint/Postgre/card_{benchmark}.txt

汇总 → checkpoint/Postgre/pg_stats_summary.csv
```

---

## 各 Evaluate Notebook 说明

### EvaluateAccuracy.ipynb — 精度对比

**Q-Error 定义**：`max(1, est) / max(1, true)`，绘图时取 `log10`

**输入文件**：

| 方法 | 输入路径 |
|------|---------|
| StarCE | `checkpoint/StarCE/card_{benchmark}.txt` |
| DuckDB | `checkpoint/DuckDB/card_{benchmark}.txt` |
| SafeBound | `checkpoint/SafeBound/SafeBound_3_{benchmark}_evaluate_results.txt` |
| Postgre | `checkpoint/Postgre/card_{benchmark}.txt` |
| FactorJoin | `checkpoint/FactorJoin/card_{benchmark}.txt` |
| 真实基数 | `Benchmark/workloads/{benchmark}/subquery/result/real.txt` |

**输出图表**（PDF → `checkpoint/figures/`）：
- `accuracy_boxplot_benchmarks_grouped.pdf` — 4 benchmark × 5 方法分组箱线图
- `accuracy_histograms_{benchmark}.pdf` — 各 benchmark 叠加直方图（4 张）
- `accuracy_individual_histograms_{benchmark}.pdf` — 各 benchmark 独立子图直方图（4 张）

### EvaluateCompress.ipynb — CompressPrecision 参数实验

实验设计：4 benchmark × 4 个 cp 值（1.1 / 1.2 / 1.5 / 2.0）= 16 次 StarCE 运行。

每次运行**必须** `RefreshStatistics=1`，统计文件写入临时路径（不覆盖 checkpoint）。

输出：
- 估计基数：`checkpoint/StarCE/compress_precision/{benchmark}/card_{benchmark}_cp{val}.txt`
- 图表：`checkpoint/figures/compress_precision_boxplot_benchmarks_grouped.pdf`

### EvaluateBuild.ipynb — 构建时间对比

**数据来源**（各方法 CSV 经 `load_method_data()` 统一重命名）：
- StarCE：`checkpoint/StarCE/benchmark_times.csv`
- SafeBound：`checkpoint/SafeBound/benchmark_times.csv`
- Postgre：`checkpoint/Postgre/pg_stats_summary.csv`

**输出图表**：构建时间柱状图（log 纵轴）+ 统计信息大小柱状图（线性纵轴，MB）

**实测数据参考**（秒）：

| Benchmark | Postgre | SafeBound | StarCE |
|-----------|---------|-----------|--------|
| JOBLight | 0.76 | 0.35 | 0.08 |
| JOBM | 0.78 | 3.40 | 1.46 |
| STATS | 0.62 | 1.21 | 0.15 |

### EvaluatePerformance.ipynb — 端到端性能对比

对比方法：DuckDB（`DuckDBTestRunner`）/ StarCE（`StarCETestRunner`）/ SafeBound（`InjectionTestRunner`）

**时间计算逻辑**：
- `planning_time` = EXPLAIN时间 − dummy启动时间（SafeBound 还需 + 估计器耗时）
- `running_time` = 普通SQL时间 − EXPLAIN时间

**输出图表**（1×3 子图）：Planning Time / Running Time / End-to-End Time

**实测数据参考**：

| 方法 | Benchmark | Planning | Running |
|------|-----------|----------|---------|
| DuckDB | STATS | 0.16s | 228.6s |
| StarCE | STATS | 0.18s | 113.2s |
| SafeBound | STATS | 0.45s | 133.1s |
| SafeBound | JOBM | 264.2s | 39.3s（JOBM 采样耗时极大）|

---

## find_worst_subqueries.py

给定三个行对齐文件，定位误差最大的 Top-K 子查询：

```bash
python find_worst_subqueries.py \
  --sql   Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --real  Benchmark/workloads/STATS-CEB/subquery/result/real.txt \
  --est   experiment/checkpoint/StarCE/card_stats.txt \
  --topk  20 \
  --out   experiment/checkpoint/StarCE/topk_subqueries_stats.sql
```

Q-Error = `max(1, max(est, true)) / max(1, min(est, true))`，输出 SQL 文件含注释头（idx/true/est/qerror）。

---

## init_experiments.sh

```bash
bash experiment/init_experiments.sh <imdb_data_path> <stats_data_path> [debug|release]
```

初始化步骤：
1. 从 `build/` 复制 `starce` 和 `duckdb` 到 `running_space/`，赋予可执行权限
2. 创建 `Benchmark/duckdb/imdb.db`（导入 IMDB CSV，无表头）
3. 创建 `Benchmark/duckdb/stats.db`（导入 STATS CSV，有表头）
4. 创建空的 `dummy_query.sql` 和 `dummy_result.txt`
5. 若 `.db` 文件已存在则跳过（幂等）
