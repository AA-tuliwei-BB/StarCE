---
name: postgresql-env
description: PostgreSQL database environment configuration for the StarCE project: data directory, connection parameters, existing databases (stats/imdb/imdblight/imdbm), table schemas, and data file locations. Use when mentioning database connection, PostgreSQL, psql, database table structure.
---

# StarCE PostgreSQL Environment Configuration

## Quick Reference

### Basic Connection Info

```bash
# Data directory
PGDATA=~/pgdata

# psql path
/usr/local/pgsql/13.1/bin/psql

# PostgreSQL version
13.1

# Connection example
PGDATA=~/pgdata /usr/local/pgsql/13.1/bin/psql -d stats
```

### Existing Databases

| Database | Owner | Purpose | Table Count | Corresponding Benchmark |
|--------|------|------|--------|---------------|
| `stats` | postgres | STATS-CEB data | 8 | STATS-CEB |
| `imdb` | postgres | Full IMDB data | 21+ | IMDB-JOB |
| `imdblight` | postgres | JOBLight subset | 6 | JOBLight |
| `imdbm` | postgres | JOBM subset | 17 | JOBM |

## Database Details

### stats Database

**Purpose**: Stack Overflow dataset, used for STATS-CEB benchmark

**Table Structure**:
```
badges      (79,851 rows)
comments    (174,305 rows)
posthistory (303,187 rows)
postlinks   (11,102 rows)
posts       (91,976 rows)
tags        (1,032 rows)
users       (40,325 rows)
votes       (328,064 rows)
```

**Data File Location**: `methods/SafeBound/Data/Stats/*.csv`

**Connection Example**:
```bash
PGDATA=~/pgdata /usr/local/pgsql/13.1/bin/psql -d stats -c "\dt"
```

### imdblight Database

**Purpose**: JOBLight benchmark (smallest IMDB subset)

**Table Structure**:
```
cast_info       (36,244,344 rows)
movie_companies (2,609,129 rows)
movie_info      (14,835,720 rows)
movie_info_idx  (1,380,035 rows)
movie_keyword   (4,523,930 rows)
title           (2,528,312 rows)
```

**Characteristics**: Most reference tables and string columns removed

**Creation Script**: `methods/SafeBound/Data/IMDB/CreateJOBLightDB.sql`

### imdbm Database

**Purpose**: JOBM benchmark (medium IMDB subset)

**Table Structure** (17 tables):
```
aka_title       cast_info       char_name
comp_cast_type  company_name    company_type
complete_cast   info_type       keyword
kind_type       link_type       movie_companies
movie_info      movie_info_idx  movie_keyword
movie_link      title
```

**Removed Tables**: name, person_info, role_type, aka_name

**Creation Script**: `methods/SafeBound/Data/IMDB/CreateJOBMDB.sql`

### imdb Database

**Purpose**: Full IMDB dataset

**Table Count**: 21+ tables (includes all movie, actor, company, etc. info)

**Data File Location**: `methods/SafeBound/Data/IMDB/*.csv`

### PG Configuration Parameters

```bash
# View current config
/usr/local/pgsql/13.1/bin/psql -U postgres -c "SHOW shared_buffers;"
/usr/local/pgsql/13.1/bin/psql -U postgres -c "SHOW max_parallel_workers_per_gather;"

# Set config (use ALTER SYSTEM + restart for params requiring restart)
/usr/local/pgsql/13.1/bin/psql -U postgres -c "ALTER SYSTEM SET max_parallel_workers_per_gather = 6;"
/usr/local/pgsql/13.1/bin/psql -U postgres -c "SELECT pg_reload_conf();"
```

**Key Parameters** (SafeBound recommended + project tuning):

| Parameter | Value | Description |
|------|-----|------|
| `shared_buffers` | 4GB | |
| `work_mem` | 2GB | |
| `effective_cache_size` | 32GB | |
| `max_parallel_workers_per_gather` | 6 | Parallel query worker count, affects plan selection |
| `random_page_cost` | default | |
| `seq_page_cost` | default | |

## Common Operations

### List All Databases

```bash
PGDATA=~/pgdata /usr/local/pgsql/13.1/bin/psql -l
```

### View Table Structure

```bash
# View tables in stats database
psql -d stats -c "\dt"

# View detailed table info
psql -d stats -c "\d+ badges"

# Count rows
psql -d stats -c "SELECT COUNT(*) FROM badges;"
```

### Execute Queries

```bash
# Single query
psql -d stats -c "SELECT COUNT(*) FROM badges WHERE Date >= '2014-01-01'::timestamp;"

# Execute SQL file
psql -d stats -f query.sql

# Output as CSV
psql -d stats -c "SELECT * FROM badges LIMIT 10;" --csv
```

### Data Import/Export

```bash
# Export data
psql -d stats -c "COPY badges TO '/path/to/badges.csv' CSV HEADER;"

# Import data
psql -d stats -c "COPY badges FROM '/path/to/badges.csv' CSV HEADER;"
```

## Dataset File Locations

### STATS Dataset

```
methods/SafeBound/Data/Stats/
├── badges.csv        (2.4M, 79,852 rows)
├── comments.csv      (6.6M, 174,306 rows)
├── postHistory.csv   (12M, 303,188 rows)
├── postLinks.csv     (452K, 11,103 rows)
├── posts.csv         (4.0M, 91,977 rows)
├── tags.csv          (12K, 1,033 rows)
├── users.csv         (1.4M, 40,326 rows)
└── votes.csv         (12M, 328,065 rows)
```

**Loading Scripts**:
- `stats.sql` - Create table definitions
- `stats_load.sql` - Load data
- `stats_index.sql` - Create indexes

### IMDB Dataset

```
methods/SafeBound/Data/IMDB/
├── title.csv              (307M)
├── cast_info.csv          (1.4G)
├── movie_companies.csv    (89M)
├── movie_info.csv         (920M)
├── movie_info_idx.csv     (34M)
├── movie_keyword.csv      (90M)
├── company_name.csv       (17M)
├── keyword.csv            (3.7M)
└── ... (other reference tables)
```

**Database Creation Scripts**:
- `imdb_create.sql` - Create full IMDB tables
- `CreateJOBLightDB.sql` - Create imdblight from imdb
- `CreateJOBMDB.sql` - Create imdbm from imdb

## Connection String Formats

### Python psycopg2

```python
import psycopg2

# Basic connection
conn = psycopg2.connect(
    dbname="stats",
    user="postgres",
    host="localhost",
    port=5432
)

# Using connection string
conn_str = "dbname=stats user=postgres host=localhost port=5432"
conn = psycopg2.connect(conn_str)
```

### FactorJoin Format

```bash
# STATS (no DB connection needed)
--data_path ../../methods/SafeBound/Data/Stats/{}.csv

# IMDB sampling mode (requires database)
--db_conn_kwargs "dbname=imdbm user=postgres host=localhost port=5432"
```

### SafeBound Format

See specific config in `methods/SafeBound/`

## Environment Variables

```bash
# Set PGDATA (if needed)
export PGDATA=~/pgdata

# Add psql to PATH
export PATH=/usr/local/pgsql/13.1/bin:$PATH

# Set default user
export PGUSER=postgres
```

## Troubleshooting

### Connection Failure

```bash
# Check if PostgreSQL is running
ps aux | grep postgres

# Check process
pgrep -a postgres

# View data directory
ls -la ~/pgdata
```

### Permission Issues

```bash
# Check user permissions
psql -d postgres -c "\du"

# Check database owner
psql -l
```

### Port Conflict

```bash
# Check port 5432
netstat -tulpn | grep 5432
# or
ss -tulpn | grep 5432
```

## Benchmark to Database Mapping

| Benchmark | Database | Subquery File | Row Count |
|-----------|--------|-----------|------|
| STATS-CEB | `stats` | `benchmark/stats-ceb/subquery/subquery.sql` | 2471 |
| JOBM | `imdbm` | `benchmark/jobm/subqueries/subquery.sql` | 6424 |
| JOBLight | `imdblight` | `Benchmark/workloads/JOBLight/subquery/subquery.sql` | 451 |

## Related Skills

- [factorjoin-usage](../factorjoin-usage/SKILL.md) - FactorJoin usage requires these databases
- [starce-usage](../starce-usage/SKILL.md) - StarCE usage requires these databases
