# DuckDB Environment Setup

## Prerequisites

- gcc / cmake and other build toolchain
- DuckDB build dependencies (see project root `build.sh` for details)
- TestEnv conda environment (Python duckdb package v1.5.2)

## Build DuckDB + StarCE

Execute in the project root directory:

```bash
./build.sh          # release mode
./build.sh debug    # debug mode
```

`build.sh` has two phases:

1. **cmake duckdb** — Configure and compile the DuckDB core library, output to `duckdb/build/release/` (or `duckdb/build/debug/`)
2. **cmake starce** — Link the StarCE extension to DuckDB, final binary is `duckdb/build/release/duckdb`

After compilation, the DuckDB binary is located at `duckdb/build/release/duckdb` (release) or `duckdb/build/debug/duckdb` (debug).

## Create Database Files

### STATS Database

```bash
bash setup/duckdb/create_stats_db.sh [duckdb_binary_path]
```

- Creates `stats.db` under `Benchmark/duckdb/` (~22 MB)
- Contains 8 tables: badges, comments, postHistory, postLinks, posts, tags, users, votes
- Data source: `Benchmark/STATS/*.csv`

### IMDB Database

```bash
bash setup/duckdb/create_imdb_db.sh [duckdb_binary_path]
```

- Creates `imdb.db` under `Benchmark/duckdb/` (~2.6 GB)
- Contains 21 IMDB tables
- Data source: `Benchmark/IMDB/*.csv`

## Schema Notes

- **STATS** — Uses `Benchmark/STATS/stats_duckDB.sql`, with primary keys using `CREATE SEQUENCE` instead of PostgreSQL `SERIAL` type for DuckDB compatibility
- **IMDB** — Uses `Benchmark/IMDB/imdb_schema.sql`, which is natively DuckDB-compatible and requires no modification (no SERIAL types)

## Notes

- **IMDB CSV has no header** — COPY command does not use `HEADER` option
- **STATS CSV has header** — COPY command requires `HEADER` option
- The script skips creation when the database file already exists to prevent accidental overwrites; to rebuild, manually `rm` the corresponding `.db` file

## StarCE Usage

StarCE distinguishes workloads via different schema JSON files (e.g., `schema_joblight.json` defines the table and column subset for JOBLight).

For IMDB-series workloads (JOBLight, JOBM, etc.), only a single full `imdb.db` is needed; StarCE automatically filters the required data based on table and column names in the schema JSON. No need to create separate database files for each workload.
