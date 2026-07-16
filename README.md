# StarCE

A DuckDB-based cardinality estimation system that uses Degree Sequence Statistics for cardinality estimation of join queries.

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

## Project Structure

```
├── main.cpp                      # StarCE entry: statistics collection + SQL execution
├── duckdb/                       # DuckDB source + StarCE extension headers
│   └── src/include/duckdb/starce/
│       ├── starce.hpp            # StatisticManager (core estimation logic)
│       ├── statistic.hpp         # DSStatistic, DegreeSequence
│       └── equalset.hpp          # EqualSet definition and serialization
├── methods/
│   ├── FactorJoin/               # FactorJoin method
│   ├── SafeBound/                # SafeBound method
│   └── LpBound/                  # LpBound method
├── experiment/                   # Experiment scripts and notebooks
├── Benchmark/                    # Benchmark datasets and workloads
│   ├── STATS/                    # STATS-CEB data (8 tables)
│   ├── IMDB/                     # IMDB data (21 tables)
│   └── workloads/                # Query workloads
└── setup/                        # Unified environment setup guide
```

## Datasets

| Dataset | Tables | Size | Description |
|--------|------|------|------|
| STATS-CEB | 8 | ~39 MB | Stack Overflow data, included in repo |
| IMDB | 21 | ~4.8 GB | Internet Movie Database, requires download |
| JOBLight | 6 | IMDB subset | Only 6 core tables |
| JOBLightRanges | 6 | IMDB subset | JOBLight + Range predicates |
| JOBM | 17 | IMDB subset | Excludes 4 wide tables |

## External Methods

| Method | Description |
|------|------|
| FactorJoin | Bayesian network + sampling cardinality estimation |
| SafeBound | Safe bound cardinality estimation |
| LpBound | Linear programming bound estimation |
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
python ExperimentRunner.py
```

For detailed experiment workflows, configuration files, and evaluation methods, see Claude Code skills (`/experiment-workflow`, `/starce-usage`, etc.).
