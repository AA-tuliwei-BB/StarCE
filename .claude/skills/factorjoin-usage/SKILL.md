---
name: factorjoin-usage
description: FactorJoin method usage guide for this repository: two working modes (BN mode and sampling mode), training and evaluation workflows, complete steps for obtaining subquery cardinality estimates for STATS-CEB/JOBM/JOBLight. Use when the user mentions FactorJoin, subquery cardinality estimation, BN mode, sampling mode.
---

# FactorJoin Usage Guide

## Overview

FactorJoin is a factorization-based join query cardinality estimation framework that supports two working modes:
1. **BN Mode**: Uses Bayesian networks to learn data distributions (suitable for STATS-CEB, JOBLight)
2. **Sampling Mode**: Uses PostgreSQL sampling (suitable for JOBM and scenarios with complex predicates)

## Core Concepts

### Differences Between the Two Working Modes

| Feature | BN Mode | Sampling Mode |
|------|---------|----------|
| **Applicable scenarios** | Simple data types, discretizable | Complex predicates (LIKE), cyclic joins |
| **Training function** | `train_one_stats()` | `train_one_imdb()` |
| **Bound_ensemble** | `bns=all_bns` | `ground_truth_factors_no_filter` (no `bns`) |
| **Dependencies** | CSV data files | CSV + PostgreSQL database |
| **n_dim_dist** | Supports 1 or 2 | Only supports 1 |
| **Evaluation method** | Query from BN | Sample from PostgreSQL |
| **Benchmark** | STATS-CEB, JOBLight | JOBM, full IMDB-JOB |

**Code identification**:
- BN mode: `Bound_ensemble(table_buckets, schema, n_dim_dist, bns=all_bns, ...)`
- Sampling mode: `Bound_ensemble(table_buckets, schema, n_dim_dist, ground_truth_factors_no_filter)`

### Benchmark Dataset Characteristics

| Benchmark | Subquery Count | Working Mode | Database | Characteristics |
|-----------|---------|----------|--------|------|
| **STATS-CEB** | 2471 | BN mode | `stats` | Stack Overflow, 8 tables, simple predicates |
| **JOBM** | 6424 | Sampling mode | `imdbm` | IMDB subset (17 tables), contains LIKE, IS NOT NULL |
| **JOBLight** | 451 | BN mode | `imdblight` | IMDB minimal subset (6 tables), simple predicates only |

**Dataset hierarchy**:
- IMDB (full) > JOBM (medium subset) > JOBLight (minimal subset)
- JOBLight: keeps only 6 core tables
- JOBM: removes 4 tables (name, person_info, role_type, aka_name), removes some columns

## Environment Configuration

### File Locations

```
# All paths below are relative to the project root
├── methods/FactorJoin/              # FactorJoin source code
│   ├── run_experiment.py            # Main execution script
│   ├── Evaluation/
│   │   ├── training.py              # train_one_stats(), train_one_imdb()
│   │   └── testing.py               # test_on_stats(), test_on_imdb()
│   ├── Join_scheme/bound.py         # Bound_ensemble core class
│   ├── Schemas/
│   │   ├── stats/schema.py          # gen_stats_light_schema()
│   │   └── imdb/schema.py           # gen_job_light_imdb_schema(), gen_imdb_schema()
│   └── checkpoints/                 # Model and sample data storage
├── methods/SafeBound/Data/
│   ├── Stats/*.csv                  # STATS data files
│   └── IMDB/*.csv                   # IMDB data files
├── benchmark/                       # Lowercase directory (for local testing)
│   ├── stats-ceb/subquery/subquery.sql
│   └── jobm/subqueries/subquery.sql
└── Benchmark/workloads/             # Uppercase directory (standard location)
    ├── STATS-CEB/subquery/
    │   ├── subquery.sql
    │   └── result/factorjoin.txt
    ├── JOBM/subquery/
    │   ├── subquery.sql
    │   └── result/
    └── JOBLight/subquery/
        ├── subquery.sql
        └── result/
```

### PostgreSQL Configuration

```bash
# Data directory
PGDATA=~/pgdata

# psql path
/usr/local/pgsql/13.1/bin/psql

# Existing databases
stats        # STATS-CEB data
imdblight    # JOBLight data
imdbm        # JOBM data
imdb         # Full IMDB data

# Users
postgres (owner: imdblight, imdbm)
postgres (owner: stats, imdb)
```

### Python Environment

- **Required**: Python 3.7 (per README)
- **Actual**: Python 3.12.7 (compatibility needs verification)
- **Dependencies**: numpy, pandas, pickle (need to be installed)

```bash
# Run from project root, then enter FactorJoin directory
cd methods/FactorJoin

# Check dependencies
python -c "import pickle, numpy, pandas; print('OK')"
```

## Usage Workflow

### 1. STATS-CEB (BN Mode)

#### Step 1.1: Train Bayesian Network Model

```bash
cd methods/FactorJoin

python run_experiment.py --dataset stats \
       --generate_models \
       --data_path ../../methods/SafeBound/Data/Stats/{}.csv \
       --model_path checkpoints/ \
       --n_dim_dist 2 \
       --n_bins 200 \
       --bucket_method greedy
```

**Parameter descriptions**:
- `--dataset stats`: STATS dataset, uses BN mode
- `--n_dim_dist 2`: 2D distribution, treewidth of 2
- `--n_bins 200`: 200 buckets per key group
- `--bucket_method greedy`: Greedy bucketing algorithm (optimal but slow)

**Output**: `checkpoints/model_stats_greedy_200.pkl` (estimated training time 20-30 minutes)

#### Step 1.2: Evaluate Subqueries

```bash
python run_experiment.py --dataset stats \
       --evaluate \
       --model_path checkpoints/model_stats_greedy_200.pkl \
       --query_file_location ../../benchmark/stats-ceb/subquery/subquery.sql \
       --save_folder ../../Benchmark/workloads/STATS-CEB/subquery/result/
```

**Output**: 
- Filename: `Benchmark/workloads/STATS-CEB/subquery/result/stats_CEB_sub_queries_model_stats_greedy_200.txt`
- Rename to: `factorjoin.txt`

```bash
cd ../../Benchmark/workloads/STATS-CEB/subquery/result/
mv stats_CEB_sub_queries_model_stats_greedy_200.txt factorjoin.txt
```

**Output format**: One float per line (estimated cardinality), line-by-line aligned with `subquery.sql`

### 2. JOBLight (BN Mode)

#### Step 2.1: Train Model

```bash
cd methods/FactorJoin

python run_experiment.py --dataset imdb-light \
       --generate_models \
       --data_path ../../methods/SafeBound/Data/IMDB/{}.csv \
       --model_path checkpoints/ \
       --n_dim_dist 2 \
       --n_bins 200 \
       --bucket_method fixed_start_key \
       --get_bin_means
```

**Parameter descriptions**:
- `--dataset imdb-light`: JOBLight subset, uses BN mode
- `--bucket_method fixed_start_key`: Fast bucketing (recommended for IMDB)
- `--get_bin_means`: Use bin means

**Output**: `checkpoints/model_imdb-light_fixed_start_key_200.pkl`

#### Step 2.2: Evaluate Subqueries

```bash
python run_experiment.py --dataset imdb-light \
       --evaluate \
       --model_path checkpoints/model_imdb-light_fixed_start_key_200.pkl \
       --query_file_location ../../Benchmark/workloads/JOBLight/subquery/subquery.sql \
       --save_folder ../../Benchmark/workloads/JOBLight/subquery/result/
```

**Output**: Rename to `factorjoin.txt`

### 3. JOBM (Sampling Mode)

#### Step 3.1: Train Model and Prepare Sample Tables

```bash
cd methods/FactorJoin

python run_experiment.py --dataset imdb \
       --generate_models \
       --data_path ../../methods/SafeBound/Data/IMDB/{}.csv \
       --model_path checkpoints/ \
       --n_dim_dist 1 \
       --bucket_method fixed_start_key \
       --db_conn_kwargs "dbname=imdbm user=postgres host=localhost port=5432" \
       --prepare_sample \
       --sampling_percentage 1.0 \
       --sampling_type ss
```

**Parameter descriptions**:
- `--dataset imdb`: IMDB dataset, uses sampling mode
- `--n_dim_dist 1`: Independent distribution (sampling mode only supports 1)
- `--prepare_sample`: Create temporary tables in PostgreSQL for sampling
- `--db_conn_kwargs`: PostgreSQL connection string (uses `imdbm` database)

**Output**: `checkpoints/model_imdb_default.pkl`

**Important**: This step creates temporary tables in the `imdbm` database for sampling

#### Step 3.2: Evaluate Subqueries

**Issue**: JOBM subqueries contain complex predicates like `LIKE` and `IS NOT NULL`. Need to confirm whether FactorJoin supports them.

**Possible evaluation approaches**:

**Approach A**: If direct evaluation is supported
```bash
python run_experiment.py --dataset imdb \
       --evaluate \
       --model_path checkpoints/model_imdb_default.pkl \
       --query_file_location ../../benchmark/jobm/subqueries/subquery.sql \
       --save_folder ../../Benchmark/workloads/JOBM/subquery/result/
```

**Approach B**: If sub-plan queries are needed (similar to full JOB)
- Need to generate `derived_query_file.pkl` (sub-plan query dictionary)
- Reference: `methods/FactorJoin/checkpoints/derived_query_file.pkl`

**Approach C**: If pre-materialized sampling is needed
```bash
# First materialize samples
python run_experiment.py --dataset imdb \
       --generate_models \
       --materialize_sample \
       --query_file_location ../../benchmark/jobm/subqueries/subquery.sql \
       ... (other parameters same as Step 3.1)

# Then evaluate
python run_experiment.py --dataset imdb \
       --evaluate \
       --model_path checkpoints/model_imdb_default.pkl \
       --query_sample_location checkpoints/binned_cards_{}/
       --save_folder ../../Benchmark/workloads/JOBM/subquery/result/
```

## Query File Formats

### STATS-CEB Format

```sql
SELECT COUNT(*) FROM badges AS badges1,comments AS comments1 WHERE comments1.UserId=badges1.UserId AND badges1.Date<='2014-08-02 12:24:29'::timestamp AND comments1.CreationDate<='2014-09-11 13:42:51'::timestamp AND comments1.CreationDate>='2010-08-01 19:11:47'::timestamp;
```

**Characteristics**:
- One SQL per line, terminated with semicolon
- Table aliases: `table AS table1`
- Date format: `'...'::timestamp`
- Predicates: equality, range comparisons

### JOBM Format

```sql
SELECT COUNT(*) FROM aka_title AS aka_title1,company_name AS company_name1,company_type AS company_type1,keyword AS keyword1,movie_companies AS movie_companies1,movie_info AS movie_info1,movie_keyword AS movie_keyword1 WHERE aka_title1.movie_id=movie_companies1.movie_id AND company_name1.id=movie_companies1.company_id AND company_type1.id=movie_companies1.company_type_id AND keyword1.id=movie_keyword1.keyword_id AND movie_companies1.movie_id=movie_info1.movie_id AND movie_info1.movie_id=movie_keyword1.movie_id AND company_name1.country_code = '[us]' AND company_name1.name = 'YouTube' AND movie_companies1.note LIKE '%(200%)%' AND movie_companies1.note LIKE '%(worldwide)%' AND movie_info1.info LIKE 'USA:% 200%' AND movie_info1.note LIKE '%internet%';
```

**Characteristics**:
- Contains `LIKE` predicates (complex pattern matching)
- Contains `IS NOT NULL`
- String equality matching
- Requires sampling mode support

### JOBLight Format

```sql
SELECT COUNT(*) FROM cast_info AS cast_info1,movie_companies AS movie_companies1 WHERE cast_info1.movie_id=movie_companies1.movie_id AND cast_info1.role_id=1;
```

**Characteristics**:
- Simple equality predicates
- Integer comparisons
- Fewer tables, simpler queries

## Code Analysis

### Core Class: Bound_ensemble

```python
# Location: methods/FactorJoin/Join_scheme/bound.py

class Bound_ensemble:
    def __init__(self, table_buckets, schema, n_dim_dist=1, 
                 ground_truth_factors_no_filter=None, 
                 SPERCENTAGE=None, query_sample_location=None, 
                 bns=None, null_value=None, db_conn_kwargs=None):
        """
        :param bns: Bayesian network dictionary (BN mode). None means sampling mode
        :param ground_truth_factors_no_filter: Ground truth factors without filter (sampling mode)
        :param query_sample_location: Pre-materialized sample location (sampling mode)
        """
        self.bns = bns
        # ...
    
    def parse_query_simple(self, query):
        """Parse query"""
        if self.bns is None:
            # Sampling mode: simple parsing (does not parse predicates)
            tables_all, join_cond, join_keys = parse_query_all_join(query)
            table_filters = dict()
            return tables_all, table_filters, join_cond, join_keys
        else:
            # BN mode: full parsing (including predicates)
            # ... parse predicates in WHERE clause
```

### Training Function Comparison

```python
# BN mode (training.py)
def train_one_stats(dataset, data_path, model_folder, n_dim_dist=2, ...):
    # 1. Process data
    data, null_values, key_attrs, table_buckets, ... = process_stats_data(...)
    
    # 2. Train Bayesian network for each table
    all_bns = dict()
    for table in schema.tables:
        bn = Bayescard_BN(...)
        bn.build_from_data(data[t_name])
        all_bns[t_name] = bn
    
    # 3. Create Bound_ensemble (with bns)
    be = Bound_ensemble(table_buckets, schema, n_dim_dist, 
                        bns=all_bns, null_value=null_values)
    
    # 4. Save model
    pickle.dump(be, open(model_path, 'wb'))

# Sampling mode (training.py)
def train_one_imdb(data_path, model_folder, n_dim_dist=1, ...):
    # 1. Process data (generate bucketing info)
    schema, table_buckets, ground_truth_factors_no_filter, ... = process_imdb_data(...)
    
    # 2. Create Bound_ensemble (no bns, with ground_truth_factors_no_filter)
    be = Bound_ensemble(table_buckets, schema, n_dim_dist, 
                        ground_truth_factors_no_filter)
    
    # 3. Optional: create sampling tables in PostgreSQL
    if prepare_sample:
        create_binned_cols(db_conn_kwargs, bins, ...)
    
    # 4. Save model
    pickle.dump(be, open(model_path, 'wb'))
```

### Evaluation Function Comparison

```python
# BN mode evaluation (testing.py)
def test_on_stats(model_path, query_file, save_res=None):
    # 1. Load model
    bound_ensemble = pickle.load(open(model_path, "rb"))
    
    # 2. Initialize inference method for each BN
    for table in bound_ensemble.bns:
        bn = bound_ensemble.bns[table]
        bn.init_inference_method()
    
    # 3. Estimate for each query
    queries = open(query_file, "r").readlines()
    pred = []
    for query_str in queries:
        query = query_str.split("||")[0][:-1]  # Supports SQL or SQL||true_card
        res = bound_ensemble.get_cardinality_bound_one(query)
        pred.append(res)
    
    # 4. Save results
    with open(save_res, "w") as f:
        for p in pred:
            f.write(str(p) + "\n")

# Sampling mode evaluation (testing.py)
def test_on_imdb(model_path, derived_query_file=None, 
                 query_sample_location=None, save_res=None):
    # 1. Load model
    bound_ensemble = pickle.load(open(model_path, "rb"))
    
    # 2. Set sampling parameters
    if query_sample_location:
        bound_ensemble.query_sample_location = query_sample_location
    
    # 3. Load queries and sub-plans
    all_queries, all_sub_plan_queries_str = pickle.load(open(derived_query_file, "rb"))
    
    # 4. Estimate for each query (using sampling)
    res = dict()
    for q_name in all_queries:
        temp = bound_ensemble.get_cardinality_bound_all(...)
        res[q_name] = temp
    
    # 5. Save results
    # ...
```

## FAQ

### Q1: Does FactorJoin support LIKE predicates?

**Observation**: In `bound.py` line 54, `parse_query_simple()` does not parse predicates in sampling mode:
```python
if self.bns is None:
    # Sampling mode: only parse join conditions, predicates handled by PostgreSQL sampling
    tables_all, join_cond, join_keys = parse_query_all_join(query)
```

**Conclusion**: Sampling mode handles complex predicates via PostgreSQL, theoretically supporting LIKE. But verification is needed.

### Q2: How to choose bucket_method?

| Method | Speed | Accuracy | Recommended Scenario |
|------|------|------|---------|
| greedy | Slow | Optimal | STATS (small dataset) |
| fixed_start_key | Fast | Near-optimal | IMDB (large dataset) |
| sub_optimal | Medium | Medium | Compromise |
| naive | Fastest | Worst | Ablation study only |

### Q3: Why does IMDB sampling mode only support n_dim_dist=1?

**Reason**: IMDB contains many string columns, making it impossible to capture correlations between two string attributes (cannot discretize for LIKE).

**Solution**: The README mentions an "optimization branch" exploring new algorithms for n_dim_dist=2.

### Q4: Query format `SQL` or `SQL||true_card`?

**Both formats are supported**:
```python
query = query_str.split("||")[0][:-1]  # Auto-split, take the first part
```

Project format: `SQL;` (SQL only, no true cardinality)

### Q5: Potential issues with JOBM evaluation

**Potential issues**:
1. **Complex predicates**: Are `LIKE`, `IS NOT NULL` fully supported
2. **Query format**: Is conversion to a specific format needed
3. **Sub-plans**: Is `derived_query_file.pkl` needed

**Suggestion**: Try direct evaluation first, adjust strategy if errors occur.

## Verification Results

### Data Files ✓
- STATS: 8 CSVs, ~1M rows total
- IMDB: 20+ CSVs, cast_info 1.4GB

### Databases ✓
- stats: 8 tables (badges, comments, postHistory, postLinks, posts, tags, users, votes)
- imdblight: 6 tables (cast_info, movie_companies, movie_info, movie_info_idx, movie_keyword, title)
- imdbm: 17 tables (full IMDB subset)

### Subquery Files ✓
- STATS-CEB: 2471 lines, simple predicates
- JOBM: 6424 lines, contains LIKE
- JOBLight: 451 lines, simple predicates

### Code Structure ✓
- All core files present
- Schema definitions complete

## Recommended Execution Order

1. **STATS-CEB** (Easiest, BN mode)
   - Fast training (~20min)
   - No complex dependencies
   - Can verify the workflow

2. **JOBLight** (Medium difficulty, BN mode)
   - IMDB subset
   - Test imdb-light dataset

3. **JOBM** (Most complex, sampling mode)
   - Requires PostgreSQL
   - Contains complex predicates
   - May need debugging

## References

- FactorJoin paper: SIGMOD 2023
- Original README: `methods/FactorJoin/README.md`
- Code repository: https://github.com/Nathaniel-Han/End-to-End-CardEst-Benchmark
