# StarCE

StarCE is a cardinality estimator built on star degree summaries (StarDS): multi-table degree sequence statistics that capture exact cross-table alignment over a shared join key, yet are collected with one scan per table. Implemented inside DuckDB, StarCE estimates Berge-acyclic join queries, with or without predicates, by composing collected summaries via degree-sequence inference.

This repository is the artifact for the paper "Cardinality Estimation with Star Degree Summaries" (submitted to PVLDB). It contains the full system, the baselines (SafeBound, LpBound, FactorJoin, BayesCard), all query workloads with true cardinalities and baseline estimates, and scripts that reproduce every experiment in the paper (Exp-1–7, Figures 5–8, Tables 2–3).

---
### ⚠️  ATTENTION — Source Code Location

**StarCE core estimation logic:**
- `duckdb/src/include/duckdb/starce/starce.hpp` — `StatisticManager` (core estimation)
- `duckdb/src/include/duckdb/starce/statistic.hpp` — `DSStatistic`, `DegreeSequence`
- `duckdb/src/include/duckdb/starce/equalset.hpp` — `EqualSet` definition & serialization
- `main.cpp` — program entry (statistics collection + SQL execution)

**Related works (baseline implementations) under `methods/`:**
- `methods/FactorJoin/` — FactorJoin (Bayesian network + sampling) [[SIGMOD 2023]](https://dl.acm.org/doi/10.1145/3588924)
- `methods/SafeBound/` — SafeBound (safe upper bounds) [[SIGMOD 2023]](https://dl.acm.org/doi/10.1145/3588907)
- `methods/LpBound/` — LpBound (linear programming bounds) [[SIGMOD 2025]](https://dl.acm.org/doi/10.1145/3725321)

---

## Quick Start

```bash
# 1. Environment
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. Data
bash setup/dataset/init_stats.sh
bash setup/dataset/init_imdb.sh

# 3. Build
./build.sh

# 4. Create DuckDB database
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh
```

For full environment setup (including PostgreSQL), see [setup/README.md](setup/README.md).

## Experiment Directory

All experiment scripts and analysis notebooks live under **`experiment/`**.
See **[experiment/README.md](experiment/README.md)** for the full workflow.

`experiment/measure_pg_single_query_est.sh` measures PostgreSQL single-table cardinality estimation latency (bpftrace probe on `clauselist_selectivity`); results are written to `experiment/checkpoint/Postgre/`.

Benchmark datasets live under **`Benchmark/`**:
- `Benchmark/STATS/` — STATS-CEB data (8 tables, ~39 MB, included in repo)
- `Benchmark/IMDB/` — IMDB data (21 tables, ~4.8 GB, requires download)
- `Benchmark/workloads/` — query workloads and result files

## Result Data

All raw experimental data (true cardinalities and estimates of every method) is committed in this repository. **Every file is one number per line** (no headers): the i-th line corresponds to the i-th subquery in `Benchmark/workloads/<benchmark>/subquery/subquery.sql`.

### True Cardinalities and Baseline Estimates (Exp-1 / Fig. 5)

Path: `Benchmark/workloads/<benchmark>/subquery/result/`

| File | Content |
|------|---------|
| `real.txt` | True cardinalities (executed queries) |
| `starce.txt` | StarCE estimates |
| `duckDB.txt` / `duckdb.txt` | DuckDB estimates (lowercase on JOBLight/JOBLightRanges/JOBM, `duckDB` on STATS-CEB) |
| `safebound.txt` | SafeBound estimates |
| `factorjoin.txt` | FactorJoin estimates |
| `lpbound.txt` | LpBound estimates |
| `bayescard.txt` | BayesCard estimates |
| `postgres.txt` | PostgreSQL estimates |
| `flat.txt`, `deepdb.txt`, `neurocard.txt` | External estimates (from Han et al. [10]; STATS-CEB and JOBLight only) |

Coverage (number of subqueries): STATS-CEB 2,471 · JOBLight 451 · JOBLightRanges 8,292 · JOBM 6,424.

Naming exceptions per benchmark: JOBLightRanges uses `factorjoin_joblight.txt`; JOBM uses `starce_grouped.txt` and `factorjoin_remapped.txt`.

### Error Distributions (Exp-7)

Per-query error is computed directly from the result files above by `experiment/EvaluateAccuracy.ipynb` (violin plots are exported to `experiment/checkpoint/figures/accuracy_violin_*.pdf`); the raw inputs are the `real.txt`/estimate files themselves, so the full error distribution is exactly reproducible from the committed data.

Microbenchmark per-query error data:
- `experiment/checkpoint/StarCE/compress_precision/compress_error_data.csv` (CompressPrecision sweep)
- `experiment/checkpoint/StarCE/split_star/splitstar_error_data.csv` (SplitStar sweep)
- `experiment/checkpoint/StarCE/pred_method/` (AR/PAR parameter sweep, one cardinality file per parameter combination)

## How to Reproduce Experiments

| Step | Action |
|------|--------|
| **1** | Follow **[setup/README.md](setup/README.md)** to set up the environment (conda, datasets, PostgreSQL, DuckDB) |
| **2** | Run `cd experiment && python reproduce.py` for one-click reproduction |
|  | Or follow **[experiment/README.md](experiment/README.md)** to run individual steps manually |

## Project Structure

```
├── main.cpp                      # StarCE entry: statistics collection + SQL execution
├── duckdb/                       # DuckDB source + StarCE extension headers
│   └── src/include/duckdb/starce/
│       ├── starce.hpp            # StatisticManager (core estimation logic)
│       ├── statistic.hpp         # DSStatistic, DegreeSequence
│       └── equalset.hpp          # EqualSet definition and serialization
├── methods/                       # Related works for baseline comparison
│   ├── FactorJoin/               # FactorJoin (SIGMOD 2023)
│   ├── SafeBound/                # SafeBound (SIGMOD 2023)
│   └── LpBound/                  # LpBound (SIGMOD 2025)
├── experiment/                   # Experiment scripts and notebooks
│   └── README.md                 # Experiment workflow guide
├── Benchmark/                    # Benchmark datasets and workloads
│   ├── STATS/                    # STATS-CEB data (8 tables)
│   ├── IMDB/                     # IMDB data (21 tables)
│   └── workloads/                # Query workloads
├── Stats-CEB/                    # End-to-End-CardEst-Benchmark (upstream benchmark)
├── setup/                        # Unified environment setup guide
│   └── README.md                 # Environment setup guide
```

## Datasets

| Dataset | Tables | Size | Description |
|--------|------|------|------|
| STATS-CEB | 8 | ~39 MB | Stack Overflow data, included in repo |
| IMDB | 21 | ~4.8 GB | Internet Movie Database, requires download |
| JOBLight | 6 | IMDB subset | Only 6 core tables |
| JOBLightRanges | 6 | IMDB subset | JOBLight + Range predicates |
| JOBM | 17 | IMDB subset | Excludes 4 wide tables |

## Related Works

Methods under `methods/` are related works included for baseline comparison in experiments.

| Method | Location | Venue |
|------|----------|-------|
| FactorJoin | `methods/FactorJoin/` | SIGMOD 2023 |
| SafeBound | `methods/SafeBound/` | SIGMOD 2023 |
| LpBound | `methods/LpBound/` | SIGMOD 2025 |

BayesCard is runnable from this repository: `experiment/TestBayesCard.ipynb` + `experiment/BayesCardRunner.py` (its model components reuse `methods/SafeBound/test_benchmark.py`). Its estimates are in `Benchmark/workloads/*/subquery/result/bayescard.txt`.

The following methods are included as estimate files only (not runnable in this repository); the numbers are taken from Han et al. [10]:

| Method | Description |
|------|------|
| FLAT / FSPN | Factorized Sum-Product Network |
| DeepDB | Deep learning cardinality estimation |
| NeuroCard | Neural cardinality estimation |

## Build

```bash
./build.sh          # release mode → build/starce
./build.sh debug    # debug mode → build-debug/starce
```

## Experiments

```bash
cd experiment
python reproduce.py          # one-click reproduction (all methods + analysis)
python reproduce.py --help   # see all options
```

For detailed experiment workflows, configuration, and evaluation methods, see [experiment/README.md](experiment/README.md).
