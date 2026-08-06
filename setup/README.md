# StarCE Unified Environment Setup

## Quick Start

```bash
# 1. Conda environment
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. Datasets
bash setup/dataset/init_stats.sh      # Verify STATS-CEB
bash setup/dataset/init_imdb.sh       # Download IMDB (~3.5GB)

# 3. Build StarCE + DuckDB
./build.sh

# 4. Create DuckDB databases
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh

# 5. PostgreSQL 13.1 — see setup/postgresql/README.md
#    ⚠️ PG 13.1 required — do NOT use conda/apt PG (18.x/16.x are incompatible)

# 6. Method-specific — see subdirectories below
```

## Directory Structure

| Directory | Description |
|------|------|
| `conda/` | Conda environment files (TestEnv, Python 3.10.4) |
| `dataset/` | Dataset download and verification scripts |
| `duckdb/` | DuckDB compilation and .db creation scripts |
| `postgresql/` | PostgreSQL 13.1 installation, configuration, and database creation |
| `safebound/` | SafeBound Cython extension compilation |
| `lpbound/` | LpBound conda environment, C++ solver, and data setup |

## Datasets

| Dataset | Tables | Size | Location |
|--------|------|------|------|
| STATS-CEB | 8 | ~39 MB | `Benchmark/STATS/` (included in repo) |
| IMDB | 21 | ~4.8 GB | `Benchmark/IMDB/` (requires download) |

## Build Artifacts

| Artifact | Location | Description |
|------|------|------|
| stats.db | `Benchmark/duckdb/stats.db` | STATS DuckDB database |
| imdb.db | `Benchmark/duckdb/imdb.db` | Full IMDB DuckDB database |
| stats (PG) | PostgreSQL | STATS-CEB database |
| imdb (PG) | PostgreSQL | Full IMDB database |
| imdblight (PG) | PostgreSQL | JOBLight subset (6 tables) |
| imdblightranges (PG) | PostgreSQL | JOBLightRanges subset (6 tables) |
| imdbm (PG) | PostgreSQL | JOBM subset (17 tables) |
