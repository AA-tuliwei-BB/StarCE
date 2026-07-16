# PostgreSQL Environment Setup

## 1. Prerequisites

```bash
sudo apt-get install build-essential flex bison libreadline-dev
```

## 2. Install PostgreSQL 13.1

End-to-end cardinality injection testing requires a source-modified PG. The source is in the repository:

```bash
cd Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1

# First-time compilation
./configure --prefix=/usr/local/pgsql/13.1

# Build and install
make -j4
cd src/backend
sudo make install
```

> If cardinality injection is not needed, you can directly use PG 13.x installed via the system package manager.

## 3. Initialization and Configuration

```bash
# Initialize data directory
/usr/local/pgsql/13.1/bin/initdb -D <PGDATA>
```

Modify `<PGDATA>/postgresql.conf`:

```ini
# Performance parameters
shared_buffers = 4GB
work_mem = 2GB
effective_cache_size = 32GB
max_parallel_workers = 6
max_parallel_workers_per_gather = 6

# pg_hint_plan preload
shared_preload_libraries = 'pg_hint_plan'
dynamic_library_path = '$libdir:<PROJECT_ROOT>/methods/SafeBound/lib'
```

Modify `<PGDATA>/pg_hba.conf`, add trust authentication:

```
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
```

## 4. Start PostgreSQL

```bash
/usr/local/pgsql/13.1/bin/pg_ctl start -D <PGDATA>
```

## 5. Create Databases

Ensure PG is started and data is initialized:

```bash
# Initialize datasets first
bash setup/dataset/init_stats.sh
bash setup/dataset/init_imdb.sh

# Create PG databases
bash setup/postgresql/create_stats_db.sh
bash setup/postgresql/create_imdb_db.sh
```

Created databases:

| Database | Tables | Description |
|--------|------|------|
| stats | 8 | STATS-CEB, Stack Overflow data |
| imdb | 21 | Full IMDB |
| imdblight | 6 | JOBLight subset |
| imdblightranges | 6 | JOBLightRanges subset |
| imdbm | 17 | JOBM subset |

## 6. pg_hint_plan

pg_hint_plan is used for Rows hint injection in SafeBound end-to-end testing.

- Shared library location: `methods/SafeBound/lib/pg_hint_plan.so`
- Preloaded via `shared_preload_libraries = 'pg_hint_plan'`

## 7. Cardinality Injection Hooks (Optional)

Source modifications are in `Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1/`, which already contains the injection logic.

Registered GUC variables:

| Variable | Type | Description |
|------|------|------|
| `ml_joinest_enabled` | bool | Enable join cardinality injection |
| `ml_joinest_fname` | string | Estimate file name (under PGDATA) |
| `ml_cardest_enabled` | bool | Enable single-table cardinality injection |
| `ml_cardest_fname` | string | Single-table estimate file name |
| `print_sub_queries` | bool | Print subqueries |
| `query_no` | int | Current query number |

See [pg-end2end skill](../.claude/skills/pg-end2end/SKILL.md) and `experiment/pg_end2end/pgsql-setup.md` for the complete injection workflow.

## 8. Verification

```bash
psql -U postgres -c "SELECT datname FROM pg_database WHERE datname LIKE 'imdb%' OR datname = 'stats';"
psql -U postgres -d stats -c "\dt"
psql -U postgres -d imdb -c "SELECT count(*) FROM title;"
```

## 9. FAQ

**PG startup failure: port in use**
```bash
ps aux | grep postgres
# Or change the port in postgresql.conf
```

**pg_hint_plan load failure**
```bash
# Check if .so file exists
ls methods/SafeBound/lib/pg_hint_plan.so
# Check PG logs
tail -f <PGDATA>/logfile
```

**IMDB variant creation failure**
Ensure the full imdb database has been created and is accessible; variants are generated via `CREATE DATABASE ... TEMPLATE imdb`.

**IMDB CSV import error: `extra data after last expected column`**
IMDB CSV uses backslash-escaped quotes (`\"`), but PostgreSQL's default CSV mode has ESCAPE equal to QUOTE (both `"`), so `\` escapes are not recognized. Fix: add `ESCAPE '\'` to the COPY command.
`create_imdb_db.sh` already includes this fix. If importing CSV manually, use:
```sql
\copy table_name FROM 'file.csv' WITH CSV DELIMITER ',' ESCAPE '\';
```
