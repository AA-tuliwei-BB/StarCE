---
name: benchmark-datasets
description: Directory locations, structure, table definitions, data files, and query workload descriptions for benchmark datasets (STATS, IMDB/JOB). Located under methods/SafeBound and Benchmark/workloads. Includes data loading scripts, schema files, CSV data files, and query collections. Use when locating datasets, understanding benchmark database structures, viewing sample queries, or running benchmark experiments.
---

# Benchmark Datasets

## Quick Navigation

The project contains multiple benchmark datasets at the following main locations:

| Dataset | Path | Purpose |
|--------|------|------|
| STATS | `methods/SafeBound/Data/Stats/` or `Benchmark/workloads/STATS-CEB/` | Stack Overflow dataset, used for STATS-CEB benchmark |
| IMDB/JOB | `methods/SafeBound/Data/IMDB/` | Internet Movie Database, used for JOB/JOBLight benchmark |
| Workloads | `methods/SafeBound/Workloads/` | Query collections for SafeBound method |

## STATS Dataset

### Path
`methods/SafeBound/Data/Stats/` or `Benchmark/workloads/STATS-CEB/`

### Table Structure
The Stack Overflow dataset contains 7 main tables:

- **users**: user info (Id, Reputation, CreationDate, Views, UpVotes, DownVotes)
- **posts**: posts (Id, PostTypeId, CreationDate, Score, ViewCount, OwnerUserId, AnswerCount, CommentCount, FavoriteCount)
- **comments**: comments (linked to posts/users)
- **badges**: badges (linked to users)
- **postHistory**: post history (linked to posts)
- **postLinks**: post links (PostId, RelatedPostId)
- **votes**: votes

### Data Files
CSV format data files:
- `users.csv`
- `posts.csv`
- `comments.csv`
- `badges.csv`
- `postHistory.csv`
- `postLinks.csv`
- `votes.csv`
- `tags.csv`

### Loading Scripts
- `stats.sql`: creates table definitions
- `stats_load.sql`: loads data (\copy commands)
- `stats_index.sql`: creates indexes

## IMDB Dataset (JOB/JOBLight)

### Path
`methods/SafeBound/Data/IMDB/`

### Table Structure
The IMDB dataset contains 21+ tables. Main tables:

- **title**: movie titles (id, production_year)
- **movie_info**: movie info (movie_id, info_type_id)
- **movie_info_idx**: movie info index (movie_id, info_type_id)
- **movie_keyword**: movie keywords (movie_id, keyword_id)
- **movie_companies**: movie companies (movie_id, company_type_id)
- **cast_info**: cast info (movie_id, person_id, role_id)
- **aka_name**, **aka_title**, **char_name**, **name**: alias and name tables
- **company_name**, **keyword**, **kind_type**, **link_type**, **role_type**: reference tables

### Subset Variants
IMDB has multiple variants based on JOB (Job-light):
- `CreateJOBLightDB.sql`: JOBLight subset
- `CreateJOBLightRangesDB.sql`: JOBLight with ranges subset
- `CreateJOBMDB.sql`: JOBM subset

### Data Loading
- `imdb_create.sql`: creates all tables
- Data files are located in `Data/IMDB/` (CSV format)

## Workloads Query Collections

### SafeBound Workloads
Location: `methods/SafeBound/Workloads/`

#### STATS Query Collections
- `StatsQueries.sql`: basic STATS query set (~150 multi-table Join queries)
- `StatsSubQueriesBayes.sql`: STATS subquery collection
- Sample queries include multi-table Joins, complex predicates, and date range filters

#### JOB Query Collections
| File | Purpose |
|------|------|
| `JOBLightQueries.sql` | JOBLight benchmark queries |
| `JOBLightRangesQueries.sql` | JOBLight with ranges queries |
| `JOBMQueries.sql` | JOBM (full JOB) queries |
| `JOBQueries.sql` | Full JOB query set |

### Query Characteristics
- One SQL query per line
- Contains multi-table Joins (2-5 tables)
- Contains selection predicates (=, <, >, BETWEEN)
- Mostly SELECT * queries (used to compute true cardinalities)

## Results Directory

### Location
`methods/SafeBound/Data/Results/`

### File Descriptions
- `Stats_Sizes.csv`: STATS query true cardinalities and predictions from various estimators
- `JOBLight_Sizes.csv`: JOBLight query results
- `JOBLightRanges_Sizes.csv`: JOBLightRanges query results
- `JOBM_Sizes.csv`: JOBM query results
- `Postgres_Inference_Stats_subquery.csv`: PostgreSQL inference results

## Usage Examples

### Load STATS dataset into PostgreSQL
```sql
-- 1. Create tables
psql -f methods/SafeBound/Data/Stats/stats.sql

-- 2. Load data
psql -f methods/SafeBound/Data/Stats/stats_load.sql

-- 3. Create indexes
psql -f methods/SafeBound/Data/Stats/stats_index.sql
```

### View Sample Queries
```bash
# View first 10 STATS queries
head -10 methods/SafeBound/Workloads/StatsQueries.sql

# View JOBLight queries
head -10 methods/SafeBound/Workloads/JOBLightQueries.sql
```

## Related Methods and Tools

- `methods/SafeBound/README.md`: SafeBound usage guide and detailed parameters
- `methods/SafeBound/run_experiment.py`: SafeBound experiment execution script
- `methods/SafeBound/checkpoints/`: pre-trained models and cached data
  - `stats_hdf/`: STATS dataset HDF5 cache
  - `stats_models/`: STATS trained Bayesian network models

## Experiment Conventions

When running benchmark experiments, ensure:
1. Data file paths are relative to the project root
2. Use the corresponding workload file (StatsQueries.sql paired with STATS data)
3. Result files correspond to the format of the matching results directory

## More Information

- See `methods/SafeBound/README.md` for details
- See related skill documents for workload format standards
