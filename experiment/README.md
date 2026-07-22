# Experiment Workflow

This directory contains all experiment scripts, Jupyter notebooks, and auxiliary modules for running cardinality estimation benchmarks and analyzing results.

## 🚀 One-Click Reproduction

```bash
cd experiment/
python reproduce.py                    # Run all methods + all analysis
python reproduce.py --methods starce duckdb  # StarCE + DuckDB only
python reproduce.py --phase2-only      # Re-run analysis on existing data
python reproduce.py --dry-run          # Preview what will run
python reproduce.py --list-methods     # List available methods
```

This runs all Test notebooks (Phase 1) followed by all Evaluate notebooks (Phase 2).
See `python reproduce.py --help` for full options.

---

## ⚠️  Workflow Order — Read This First

**Always run TestXXX scripts first to generate data, then run Evaluate notebooks to analyze.**

```
┌─────────────────────────────────┐
│  Phase 1: Data Generation       │
│  (TestXXX notebooks / scripts)  │
│  ↓ produces result files +      │
│    checkpoint data               │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│  Phase 2: Analysis              │
│  (EvaluateXXX notebooks)        │
│  ↓ reads checkpoint data,        │
│    produces plots + tables       │
└─────────────────────────────────┘
```

Evaluate notebooks **do not** produce raw estimation results — they consume data that must already exist in `checkpoint/` and `Benchmark/workloads/*/result/`. If you skip Phase 1, the analysis notebooks will fail with missing-file errors.

---

## Directory Layout

| Path | Purpose |
|------|---------|
| `running_space/` | Runtime working directory — config.json, temporary SQL files, statistics cache |
| `checkpoint/` | Intermediate results (CSV) produced by Test scripts, consumed by Evaluate notebooks |
| `plot_style.py` | Shared module: method colors, violin plot helpers (imported by Evaluate notebooks) |

---

## Phase 1: Test Scripts (Generate Data)

Each script runs cardinality estimation for one or more methods on multiple benchmarks and saves results.

### StarCE family

| Script | Description | Output |
|--------|-------------|--------|
| `TestStarCE.ipynb` | Run StarCE on STATS-CEB, JOBLight, JOBLightRanges, JOBM. Collects subquery cardinalities, build time, and estimate time. | `checkpoint/StarCE/`, `Benchmark/workloads/*/result/starce.txt` |
| `TestDuckDB.ipynb` | Run native DuckDB estimator (baseline) on the same workloads. | `checkpoint/DuckDB/`, `Benchmark/workloads/*/result/duckdb.txt` |

### Bound methods

| Script | Description | Output |
|--------|-------------|--------|
| `TestSafebound.ipynb` | Run SafeBound on STATS-CEB, JOBLight, JOBLightRanges, JOBM. Requires PostgreSQL to be running. | `checkpoint/SafeBound/`, `Benchmark/workloads/*/result/safebound.txt` |
| `TestLpBound.py` | Run LpBound build time, estimate time, and optionally JOBLightRanges accuracy. Requires a separate `lpbound` conda environment. | `checkpoint/LpBound/` |

### Probabilistic / ML methods

| Script | Description | Output |
|--------|-------------|--------|
| `TestFactorJoin.ipynb` | Run FactorJoin on STATS-CEB (BN mode), JOBLight (BN mode), JOBLightRanges (BN mode), JOBM (sampling mode), and JobJoin. | `checkpoint/FactorJoin/`, `Benchmark/workloads/*/result/factorjoin.txt` |
| `TestBayesCard.ipynb` | Run BayesCard (pure BN path) via `BayesCardRunner.py` on supported benchmarks. | `checkpoint/BayesCard/` |

### PostgreSQL baseline

| Script | Description | Output |
|--------|-------------|--------|
| `TestPostgreBasic.ipynb` | Run PostgreSQL `EXPLAIN` estimates (`pg_est`) on STATS-CEB and IMDB workloads. | `Benchmark/workloads/*/pg_est.txt` |

### One-time setup (before running any Test scripts)

```bash
# Initialize experiment environment — verifies DBs exist, copies binaries to running_space
bash init_experiments.sh

# If running SafeBound: start PostgreSQL and configure
bash setup_pgsql.sh
```

---

## Phase 2: Evaluate Notebooks (Analyze Data)

These notebooks read from `checkpoint/` and `Benchmark/workloads/*/result/` to produce plots and comparison tables. Run them **after** the relevant Test scripts have completed.

| Notebook | Description | Required Test Scripts |
|----------|-------------|-----------------------|
| `EvaluateAccuracy.ipynb` | Compute relative error of estimated cardinalities across all methods. Produces violin plots, Q-Error distribution tables, and per-query error breakdown. | All TestXXX scripts for the methods you want to compare |
| `EvaluateBuild.ipynb` | Compare build/statistics-collection time across methods. Produces tables and bar charts. | TestStarCE, TestDuckDB, TestSafebound, TestFactorJoin, TestLpBound |
| `EvaluatePerformance.ipynb` | Compare planning time and execution time across methods. | TestStarCE, TestDuckDB, TestSafebound (planning + runtime data) |
| `EvaluatePlanAndBuild.ipynb` | Combined planning time + build time analysis across all methods. | TestStarCE, TestDuckDB, TestSafebound, TestFactorJoin, TestLpBound |
| `EvaluateCompress.ipynb` | Test the impact of different `CompressPrecision` values on StarCE accuracy and build time (parameter sweep). | TestStarCE (with multiple CompressPrecision runs) |
| `EvaluatePredMethod.ipynb` | Test the impact of StarCE predicate handling methods (`PredMethod`) on estimation accuracy. | TestStarCE (with multiple PredMethod runs) |
| `EvaluateSplitStar.ipynb` | Test the impact of `EnableStarSplit` + `MaxStarSize` on accuracy, build time, and estimate time. | TestStarCE (with multiple SplitStar runs) |
| `ScalabilityExperiment.ipynb` | Evaluate StarCE scalability along two dimensions: data size (table row count) and query complexity (number of joins). | TestStarCE (scalability-specific runs) |

---

## Auxiliary Files

| File | Description |
|------|-------------|
| `ExperimentRunner.py` | Core driver class — provides base classes (`ExperimentRunner`, `BenchmarkConfig`) and utilities for running StarCE/DuckDB/SafeBound. Many Test notebooks import from this module. |
| `BayesCardRunner.py` | BayesCard training and inference orchestration. Called by `TestBayesCard.ipynb`. |
| `plot_style.py` | Shared plotting module: cross-method color scheme (`METHOD_COLORS`), method display order, violin plot helpers. Imported by all Evaluate notebooks. |
| `init_experiments.sh` | One-time initialization: verifies `stats.db`/`imdb.db` exist, copies `duckdb` and `starce` binaries to `running_space/`. |
| `setup_pgsql.sh` | Starts PostgreSQL and sets up the connection for SafeBound experiments. |

---

## Quick Start (Minimal Example)

```bash
cd experiment/

# One-time setup
bash init_experiments.sh
bash setup_pgsql.sh

# Phase 1: Generate data
# Run the Test notebooks for the methods you need, e.g.:
jupyter notebook TestStarCE.ipynb      # Run all cells
jupyter notebook TestDuckDB.ipynb      # Run all cells

# Phase 2: Analyze
jupyter notebook EvaluateAccuracy.ipynb  # Run all cells → produces plots and tables
```

---

## Configuration

Each Test notebook reads configuration from `running_space/config.json`. Key parameters:

| Parameter | Description |
|-----------|-------------|
| `benchmark` | Target benchmark name (`stats-ceb`, `joblight`, `joblightranges`, `jobm`) |
| `CompressPrecision` | Degree sequence compression precision (0–1, default 0.2) |
| `AdjustRate` | Adjust-to-average rate |
| `PredMethod` | Predicate handling method (0–3) |
| `EnableStarSplit` | Enable star-split optimization |
| `MaxStarSize` | Maximum star size for SplitStar |
| `RecordingSubquery` | Record subquery SQL during estimation |
| `UseSubqueryCard` | Inject external subquery cardinalities |
| `UseSingleTableCard` | Inject single-table cardinalities |

For detailed parameter documentation, see the [starce-usage](../.claude/skills/starce-usage/SKILL.md) skill.
