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

```bash
cd Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1

./configure --prefix=/usr/local/pgsql/13.1
make -j$(nproc)
sudo make install
```

Add to PATH:

```bash
export PATH="/usr/local/pgsql/13.1/bin:$PATH"
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
