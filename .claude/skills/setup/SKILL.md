---
name: setup
description: Unified environment setup guide for the StarCE project: conda environment, dataset acquisition (STATS/IMDB), PostgreSQL configuration, DuckDB compilation and database creation. Use when mentioning environment setup, project initialization, setting up from scratch, setup, installing environment, creating database.
---

# StarCE Project Unified Environment Setup

## Quick Start

```bash
# 1. Conda environment
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. Datasets
bash setup/dataset/init_stats.sh
bash setup/dataset/init_imdb.sh

# 3. Compile StarCE (DuckDB + StarCE)
./build.sh

# 4. Create DuckDB databases
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh
```

## Sub-Guides

| Guide | Path | Description |
|------|------|------|
| Conda Environment | `setup/conda/README.md` | Python 3.10.4, TestEnv environment configuration |
| Datasets | `setup/dataset/README.md` | STATS-CEB and IMDB data acquisition |
| PostgreSQL | `setup/postgresql/README.md` | PG 13.1 installation, configuration, database creation |
| DuckDB | `setup/duckdb/README.md` | Compilation, .db file creation, CSV import |

## Dataset Overview

| Dataset | Table Count | Size | Acquisition Method |
|--------|------|------|----------|
| STATS-CEB | 8 | ~39 MB | Already in repo, `init_stats.sh` verifies |
| IMDB | 21 | ~4.8 GB | `init_imdb.sh` downloads |

Data is uniformly stored under `Benchmark/STATS/` and `Benchmark/IMDB/`.

## PostgreSQL Databases

| Database | Table Count | Description |
|--------|------|------|
| stats | 8 | STATS-CEB |
| imdb | 21 | Full IMDB |
| imdblight | 6 | JOBLight subset |
| imdblightranges | 6 | JOBLightRanges subset |
| imdbm | 17 | JOBM subset |

## Compilation

Always use `./build.sh` (release) or `./build.sh debug`. Release mode is smaller and faster (~560KB), debug mode allows debugging (~11MB).

## Running Space Initialization

```bash
RUNNING_SPACE=experiment/running_space
mkdir -p $RUNNING_SPACE

# Copy build artifacts
cp build/starce $RUNNING_SPACE/
cp duckdb/build/release/duckdb $RUNNING_SPACE/

# Create placeholder files required by starce (must exist even for stats collection only)
touch $RUNNING_SPACE/dummy_query.sql $RUNNING_SPACE/dummy_result.txt
```

> starce reads the file pointed to by `SQL_PATH` (default `dummy_query.sql`) and writes to `REAL_CARD_PATH` (default `dummy_result.txt`) at startup. Both files must exist, otherwise starce will crash with `Failed to open file`.

## LpBound Environment

> See [`setup/lpbound/SKILL.md`](lpbound/SKILL.md) — standalone reproduction guide, including conda environment snapshot.

## Related Skills

- [postgresql-env](../postgresql-env/SKILL.md) - PG connection configuration
- [benchmark-datasets](../benchmark-datasets/SKILL.md) - Dataset details
- [starce-usage](../starce-usage/SKILL.md) - How to run StarCE
- [experiment-workflow](../experiment-workflow/SKILL.md) - Experiment workflow
