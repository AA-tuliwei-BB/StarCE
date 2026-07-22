# StarCE

A DuckDB-based cardinality estimation system that uses Degree Sequence Statistics for cardinality estimation of join queries.

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

Benchmark datasets live under **`Benchmark/`**:
- `Benchmark/STATS/` — STATS-CEB data (8 tables, ~39 MB, included in repo)
- `Benchmark/IMDB/` — IMDB data (21 tables, ~4.8 GB, requires download)
- `Benchmark/workloads/` — query workloads and result files

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

Other methods referenced in experiments (not included in this repo):

| Method | Description |
|------|------|
| FLAT / FSPN | Factorized Sum-Product Network |
| DeepDB / BayesCard | Deep learning cardinality estimation |
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
