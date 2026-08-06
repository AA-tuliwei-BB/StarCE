# PostgreSQL Environment Setup

> **⚠️  CRITICAL: PostgreSQL 13.1 is required. DO NOT use other versions.**
>
> Conda's `postgresql` (18.x) and `apt install postgresql` (16.x) are **incompatible** —
> SafeBound's statistics objects and FactorJoin's training output depend on PG 13.1 internals.
>
> Compile from the source included in this repo:
> `Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1/`

## 1. Prerequisites

```bash
sudo apt-get install build-essential flex bison libreadline-dev zlib1g-dev
```

## 2. Compile and Install PostgreSQL 13.1

Choose your installation prefix (examples below; adjust to your machine):

```bash
PGSQL_PREFIX=/usr/local/pgsql/13.1   # system-wide (needs sudo make install)
# or
PGSQL_PREFIX=$HOME/pgsql13           # user-local (no sudo)

cd Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1

./configure --prefix=$PGSQL_PREFIX --enable-rpath
make -j$(nproc)
make install                        # add 'sudo' if prefix is system-wide
```

`--enable-rpath` embeds the library path (`$PGSQL_PREFIX/lib`) into binaries so
they find `libpq` without extra configuration.  If you forgot `--enable-rpath`
or installed to a non-standard location, register the library path:

```bash
# Option A: ldconfig (system-wide, needs sudo)
echo "$PGSQL_PREFIX/lib" | sudo tee /etc/ld.so.conf.d/pgsql13.conf
sudo ldconfig

# Option B: per-shell environment (if no sudo)
export LD_LIBRARY_PATH="$PGSQL_PREFIX/lib:$LD_LIBRARY_PATH"
```

Add to your shell profile:

```bash
export PATH="$PGSQL_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$PGSQL_PREFIX/lib:$LD_LIBRARY_PATH"
```

## 3. Initialize and Start

```bash
export PGDATA=/path/to/your/pgdata

/usr/local/pgsql/13.1/bin/initdb -D $PGDATA
/usr/local/pgsql/13.1/bin/pg_ctl start -D $PGDATA
```

## 4. Create Databases

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

## 5. Verification

```bash
psql -U postgres -c "SELECT datname FROM pg_database WHERE datname LIKE 'imdb%' OR datname = 'stats';"
psql -U postgres -d stats -c "\dt"
psql -U postgres -d imdb -c "SELECT count(*) FROM title;"
```

## 6. pg_hint_plan Extension

SafeBound and FactorJoin require `pg_hint_plan` to be loaded. Compile it from the PG 13.1 source:

```bash
cd Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1/contrib/pg_hint_plan
make
make install
```

Then add to `postgresql.conf`:

```
shared_preload_libraries = 'pg_hint_plan'
```

Restart PG and verify:

```sql
SHOW shared_preload_libraries;
-- should include pg_hint_plan
```

## FAQ

**PG startup failure: port in use**
```bash
ps aux | grep postgres
# Or change the port in postgresql.conf
```

**IMDB variant creation failure**
Ensure the full imdb database has been created and is accessible; variants are generated via `CREATE DATABASE ... TEMPLATE imdb`.

**IMDB CSV import error: `extra data after last expected column`**
IMDB CSV uses backslash-escaped quotes (`\"`), but PostgreSQL's default CSV mode has ESCAPE equal to QUOTE (both `"`), so `\` escapes are not recognized. Fix: add `ESCAPE '\'` to the COPY command.
`create_imdb_db.sh` already includes this fix. If importing CSV manually, use:
```sql
\copy table_name FROM 'file.csv' WITH CSV DELIMITER ',' ESCAPE '\';
```
