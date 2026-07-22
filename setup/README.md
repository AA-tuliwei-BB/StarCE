# StarCE Unified Environment Setup

This directory provides a complete project environment setup guide and scripts.

## Quick Start

```bash
# 1. Conda environment
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. Dataset initialization
bash setup/dataset/init_stats.sh      # Verify STATS-CEB
bash setup/dataset/init_imdb.sh       # Download IMDB (~3.5GB)

# 3. Build StarCE (DuckDB + StarCE)
./build.sh

# 4. Create DuckDB databases
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh

# 5. PostgreSQL environment (see setup/postgresql/README.md)
#    ⚠️ PG 13.1 required — do NOT use conda/apt PG (18.x/16.x are incompatible)
```

## Directory Structure

| Directory | Description |
|------|------|
| `conda/` | Conda environment export files, Python 3.10.4 / TestEnv |
| `dataset/` | Dataset initialization scripts (data lands in Benchmark/) |
| `postgresql/` | PostgreSQL 13.1 installation, configuration, and database creation |
| `duckdb/` | DuckDB compilation, .db file creation, CSV import |

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

## Next Steps

After environment setup, refer to the following skills for experiments:

- [starce-usage](../.claude/skills/starce-usage/SKILL.md) — StarCE usage guide
- [pg-end2end](../.claude/skills/pg-end2end/SKILL.md) — PG end-to-end testing
- [experiment-workflow](../.claude/skills/experiment-workflow/SKILL.md) — Experiment workflow overview
