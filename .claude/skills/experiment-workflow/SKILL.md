---
name: experiment-workflow
description: StarCE experiment workflow overview: experiment directory structure, ExperimentRunner.py core driver logic, operational workflows for each Test notebook (TestStarCE/TestDuckDB/TestSafebound), analysis methods for each Evaluate notebook (EvaluateAccuracy/EvaluateCompress/EvaluateBuild/EvaluatePerformance), and file organization of the checkpoint directory. Use when the user mentions experiment workflow, how to run experiments, ExperimentRunner, cardinality collection, Q-Error calculation, accuracy comparison, build time, performance testing, find_worst_subqueries.
---

# StarCE Experiment Workflow

## Overall Architecture

Experiments are divided into two phases: **Cardinality Collection** (Test notebooks) → **Result Analysis** (Evaluate notebooks).

```
Phase 1: Cardinality collection for each method
  TestStarCE.ipynb       → checkpoint/StarCE/card_*.txt
  TestDuckDB.ipynb       → checkpoint/DuckDB/card_*.txt
  TestSafebound.ipynb    → checkpoint/SafeBound/SafeBound_3_*_evaluate_results.txt

Phase 2: Result analysis and visualization
  EvaluateAccuracy.ipynb   → Q-Error boxplot + histogram (accuracy comparison)
  EvaluateCompress.ipynb   → CompressPrecision parameter sensitivity
  EvaluateBuild.ipynb      → Build time + statistics size
  EvaluatePerformance.ipynb → Planning time + execution time end-to-end comparison

Auxiliary Tools
  ExperimentRunner.py      → Core driver module (called by all Test notebooks)
  find_worst_subqueries.py → Find Top-K subqueries with largest errors
  init_experiments.sh      → Initialize running_space (create databases, copy executables)
```

---

## Directory Structure

```
experiment/
├── running_space/          ← StarCE working directory, all relative paths are based here
│   ├── config.json         ← Written by ExperimentRunner before each run
│   ├── starce / duckdb     ← Executables
│   ├── statistics_*.json   ← StarCE statistics cache
│   ├── dummy_query.sql     ← Empty file, used to measure startup overhead
│   └── dummy_result.txt    ← Empty file, placeholder
├── checkpoint/             ← Persistent results for each method
│   ├── StarCE/
│   │   ├── card_stats.txt / card_jobm.txt / card_joblight.txt / card_joblr.txt
│   │   ├── benchmark_times.csv
│   │   └── compress_precision/{benchmark}/card_{benchmark}_cp{val}.txt
│   ├── DuckDB/             ← card_*.txt
│   ├── SafeBound/
│   │   ├── SafeBound_3_{benchmark}.pkl
│   │   ├── SafeBound_3_{benchmark}_evaluate_results.txt
│   │   └── benchmark_times.csv
│   └── figures/            ← All generated PDF charts
├── ExperimentRunner.py     ← Core driver module
├── find_worst_subqueries.py
├── init_experiments.sh
├── TestStarCE.ipynb
├── TestDuckDB.ipynb
├── TestSafebound.ipynb
├── EvaluateAccuracy.ipynb
├── EvaluateCompress.ipynb
├── EvaluateBuild.ipynb
└── EvaluatePerformance.ipynb
```

---

## ExperimentRunner.py

The core dependency for all Test notebooks, providing three abstraction layers.

### `StarCEConfig` (dataclass)

Maps all fields of `running_space/config.json`, additionally providing:
- `to_json_file(path)` — serialize and write to config.json
- `copy()` / `update(**kwargs)` — immutable-style derivation of new configs
- `from_json_file(path)` — deserialize

### `ExperimentRunner` (ABC)

**Directory constants** (set in `__init__`):
- `script_dir` = `experiment/`
- `running_space` = `experiment/running_space/`
- `checkpoint_dir` = `experiment/checkpoint/`
- `benchmark_dir` = `Benchmark/`

**Core methods**:

| Method | Description |
|------|------|
| `save_config(config)` | Write `StarCEConfig` to `running_space/config.json` |
| `run_starce()` | Execute `./starce` in `running_space/`, returns `(success, elapsed_sec)` |
| `_prepare_input_sql_with_explain(src, dst)` | Prefix each SQL in src with `EXPLAIN`, write to dst |
| `_prepare_input_sql_without_explain(src, dst)` | Direct copy (used to measure actual execution time) |
| `inner_test_planning_time(config, ...)` | Planning time = EXPLAIN runtime − dummy_query.sql runtime |
| `inner_test_running_time(config, ...)` | Execution time = normal SQL runtime − EXPLAIN runtime |

**Workload config factory methods** (return pre-populated `StarCEConfig`):
- `get_stats_config()` — STATS-CEB, stats.db
- `get_jobm_config()` — JOBM, imdb.db
- `get_joblight_config()` — JOBLight, imdb.db (lightweight schema)
- `get_joblight_ranges_config()` — JOBLightRanges, imdb.db

### Subclasses

**`StarCETestRunner`** (`EnableStarCE=1`):
- `inner_test_build_time(config, db_name, num_runs)` — `RefreshStatistics=1`, measure statistics collection time and file size
- `get_est_cards(benchmark)` — `RecordingSubquery=1` + EXPLAIN mode run, results written to `checkpoint/StarCE/card_*.txt`

**`DuckDBTestRunner`** (`EnableStarCE=0`):
- Same interface as StarCETestRunner, but StarCE disabled, measuring DuckDB native performance
- `test_build_time()` is a no-op (DuckDB has no build step)

**`InjectionTestRunner`** (`UseSubqueryCard=1`):
- `inner_test_planning_time_with_injection(config, ..., injected_card_path, card_est_time)` — inject external cardinalities, planning time additionally includes the estimator's own overhead
- Used to test SafeBound/FactorJoin end-to-end performance under the same DuckDB framework

### `setup_starce_executable(project_root, running_space)`

Copies executable from `build/starce` to `running_space/starce` and sets permissions `0o755`.

---

## Test Notebook Workflows

### TestStarCE.ipynb

```
1. Build Phase
   for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
       config = get_{benchmark}_db_config()
       config.RefreshStatistics = 1
       inner_test_build_time(config, db_name)
       → Record build time + statistics_*.json file size

2. Evaluate Phase (get_est_cards)
   for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
       - Prefix subquery.sql lines with EXPLAIN
       - RecordingSubquery=1, SUBQUERY_RESULT_PATH → output file
       - run_starce() → read StarCE estimated cardinality for each subquery
       → checkpoint/StarCE/card_{benchmark}.txt

3. Summary → checkpoint/StarCE/benchmark_times.csv
```

### TestDuckDB.ipynb

```
for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
    1. Prefix subquery.sql lines with EXPLAIN → running_space/explain.sql
    2. subprocess.run([duckdb_exec, db_path], stdin=explain.sql)
    3. extract_card_from_explain.process_data() parse output
       (match "\d+ Rows" pattern, split query blocks by "\n\n")
    4. Write checkpoint/DuckDB/card_{benchmark}.txt
```

DuckDB bypasses StarCE entirely — it directly calls the `duckdb` executable and parses EXPLAIN text to extract estimated row counts.

### TestSafebound.ipynb

```
1. Build Phase
   for benchmark in [STATS, JOBM, JOBLight, JOBLightRanges]:
       build_stats_object(method, benchmark, parameters)
       → checkpoint/SafeBound/SafeBound_3_{benchmark}.pkl

2. Evaluate Phase
   for benchmark:
       pkl = pickle.load(SafeBound_3_{benchmark}.pkl)
       for sql in subquery_file:
           - Stats: sql_to_joingraph(sql)  ← custom parser
           - Others: SQLQueriesToJoinQueryGraphs(sql)  ← SafeBound library
           card = pkl.functionalFrequencyBound(query)
       → checkpoint/SafeBound/SafeBound_3_{benchmark}_evaluate_results.txt

3. Summary → checkpoint/SafeBound/benchmark_times.csv
```

Note: Stats/JOBM uses `subquery.sql`; JOBLight/JOBLightRanges uses `subquery2.sql`.
---

## Evaluate Notebook Descriptions

### EvaluateAccuracy.ipynb — Accuracy Comparison

**Q-Error definition**: `max(1, est) / max(1, true)`, `log10` applied when plotting

**Input files**:

| Method | Input Path |
|------|---------|
| StarCE | `checkpoint/StarCE/card_{benchmark}.txt` |
| DuckDB | `checkpoint/DuckDB/card_{benchmark}.txt` |
| SafeBound | `checkpoint/SafeBound/SafeBound_3_{benchmark}_evaluate_results.txt` |
| FactorJoin | `checkpoint/FactorJoin/card_{benchmark}.txt` |
| True Cardinality | `Benchmark/workloads/{benchmark}/subquery/result/real.txt` |

**Output charts** (PDF → `checkpoint/figures/`):
- `accuracy_boxplot_benchmarks_grouped.pdf` — 4 benchmarks × 5 methods grouped boxplot
- `accuracy_histograms_{benchmark}.pdf` — per-benchmark overlaid histograms (4 charts)
- `accuracy_individual_histograms_{benchmark}.pdf` — per-benchmark individual subplot histograms (4 charts)

### EvaluateCompress.ipynb — CompressPrecision Parameter Experiment

Experimental design: 4 benchmarks × 4 cp values (1.1 / 1.2 / 1.5 / 2.0) = 16 StarCE runs.

Each run **must** have `RefreshStatistics=1`, with statistics files written to a temporary path (not overwriting checkpoint).

Output:
- Estimated cardinalities: `checkpoint/StarCE/compress_precision/{benchmark}/card_{benchmark}_cp{val}.txt`
- Chart: `checkpoint/figures/compress_precision_boxplot_benchmarks_grouped.pdf`

### EvaluateBuild.ipynb — Build Time Comparison

**Data sources** (each method's CSV uniformly renamed via `load_method_data()`):
- StarCE: `checkpoint/StarCE/benchmark_times.csv`
- SafeBound: `checkpoint/SafeBound/benchmark_times.csv`

**Output charts**: Build time bar chart (log y-axis) + statistics size bar chart (linear y-axis, MB)

**Measured data reference** (seconds):

| Benchmark | SafeBound | StarCE |
|-----------|-----------|--------|
| JOBLight | 0.35 | 0.08 |
| JOBM | 3.40 | 1.46 |
| STATS | 1.21 | 0.15 |

### EvaluatePerformance.ipynb — End-to-End Performance Comparison

Compared methods: DuckDB (`DuckDBTestRunner`) / StarCE (`StarCETestRunner`) / SafeBound (`InjectionTestRunner`)

**Time calculation logic**:
- `planning_time` = EXPLAIN time − dummy startup time (SafeBound also needs + estimator overhead)
- `running_time` = normal SQL time − EXPLAIN time

**Output charts** (1×3 subplots): Planning Time / Running Time / End-to-End Time

**Measured data reference**:

| Method | Benchmark | Planning | Running |
|------|-----------|----------|---------|
| DuckDB | STATS | 0.16s | 228.6s |
| StarCE | STATS | 0.18s | 113.2s |
| SafeBound | STATS | 0.45s | 133.1s |
| SafeBound | JOBM | 264.2s | 39.3s (JOBM sampling is extremely costly) |

---

## find_worst_subqueries.py

Given three line-aligned files, locate the Top-K subqueries with the largest errors:

```bash
python find_worst_subqueries.py \
  --sql   Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --real  Benchmark/workloads/STATS-CEB/subquery/result/real.txt \
  --est   experiment/checkpoint/StarCE/card_stats.txt \
  --topk  20 \
  --out   experiment/checkpoint/StarCE/topk_subqueries_stats.sql
```

Q-Error = `max(1, max(est, true)) / max(1, min(est, true))`, output SQL file includes comment headers (idx/true/est/qerror).

---

## init_experiments.sh

```bash
bash experiment/init_experiments.sh <imdb_data_path> <stats_data_path> [debug|release]
```

Initialization steps:
1. Copy `starce` and `duckdb` from `build/` to `running_space/`, set executable permissions
2. Create `Benchmark/duckdb/imdb.db` (import IMDB CSV, no header)
3. Create `Benchmark/duckdb/stats.db` (import STATS CSV, with header)
4. Create empty `dummy_query.sql` and `dummy_result.txt`
5. Skip if `.db` files already exist (idempotent)
