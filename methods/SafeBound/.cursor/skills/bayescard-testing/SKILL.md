---
name: bayescard-testing
description: Use BayesCard for Bayesian Network training and cardinality estimation on STATS-CEB, JOBLight, JOBLightRanges, and JOBM benchmarks. Provides a unified script entry point, four benchmark types, data preprocessing, and model training/inference workflows. Use when needing test_benchmark.py, BayesCard cardinality estimation, JOBLightRanges preprocessing, model loading, or subquery inference.
---

# BayesCard Test Script

## Quick Start

BayesCard performs cardinality estimation via Bayesian Networks. The `test_benchmark.py` script provides a unified training and inference entry point.

### Basic Command Structure

```bash
cd methods/SafeBound # Must run from project root

# Train model
python test_benchmark.py train --benchmark <BENCHMARK> \
 --csv_path <CSV_PATH_TEMPLATE> \
 --hdf_path <HDF_DIR> \
 --model_dir <MODEL_DIR>

# Run inference
python test_benchmark.py infer --benchmark <BENCHMARK> \
 --csv_path <CSV_PATH_TEMPLATE> \
 --model_dir <MODEL_DIR> \
 --query_file <QUERY_FILE> \
 --output_file <OUTPUT_FILE>
```

### Supported Benchmarks

| Benchmark | CSV Path Example | Characteristics |
|------|-----------|------|
| `stats` | `Data/Stats/{}.csv` | CSV with header, fastest |
| `joblight` | `Data/IMDB/{}.csv` | IMDB standard, no header |
| `joblightranges` | `Data/IMDB/{}.csv` | Contains range predicates, needs preprocessing |
| `jobm` | `Data/IMDB/{}.csv` | Full IMDB, most complex |

---

## Workflows

### Flow 1: Standard Benchmarks (STATS-CEB, JOBLight, JOBM)

**No special processing needed, data format is uniform**.

#### Training

```bash
python test_benchmark.py train --benchmark stats \
 --csv_path Data/Stats/{}.csv \
 --hdf_path checkpoints/stats_hdf \
 --model_dir checkpoints/stats_models
```

**Output**: Generates multiple `.pkl` files under `checkpoints/stats_models/` (one BN model per relationship)

#### Inference

```bash
python test_benchmark.py infer --benchmark stats \
 --csv_path Data/Stats/{}.csv \
 --model_dir checkpoints/stats_models \
 --query_file ../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
 --output_file result_bayescard.txt
```

**Output Format**: One floating-point number per line, representing the cardinality estimate for the corresponding input query

```
79851.00000000003
1.0
5331.335489717553
321.25077452098594
174304.99999999994
```

---

### Flow 2: JOBLightRanges (Needs Data and SQL Preprocessing)

JOBLightRanges uses range predicates (e.g., `phonetic_code` string values), while BayesCard BN only supports numeric values. Two-stage preprocessing is required.

#### Special Properties

- **phonetic_code**: string like `'A1234'` → numeric value
- **imdb_index**: roman numeral like `'III'` → numeric value
- **series_years**: range like `'2000-2010'` → year

#### Training (Includes Data Preprocessing)

```bash
python test_benchmark.py train --benchmark joblightranges \
 --csv_path Data/IMDB/{}.csv \
 --hdf_path checkpoints/joblr_hdf \
 --model_dir checkpoints/joblr_models \
 --preprocessed_dir checkpoints/joblr_preprocessed
```

**Internal Steps**:
1. Copy IMDB CSV files to `checkpoints/joblr_preprocessed/`
2. Convert three string columns in `title.csv` to integers
3. Use converted CSV to generate HDF and train models

#### Inference (Includes SQL Preprocessing)

```bash
python test_benchmark.py infer --benchmark joblightranges \
 --csv_path Data/IMDB/{}.csv \
 --model_dir checkpoints/joblr_models \
 --query_file ../../Benchmark/workloads/JOBLightRanges/subquery/subquery.sql \
 --output_file result_bayescard.txt
```

**Internal Steps**:
1. Read original SQL queries (containing string predicates like `t.phonetic_code<='A123'`)
2. Convert all string predicates to numeric predicates
3. After inference completes, clean up temporary preprocessed SQL file

---

## Key Parameters

### Training Parameters

| Parameter | Default Value | Description |
|-----|--------|------|
| `--algorithm` | `chow-liu` | BN structure learning algorithm (recommend keeping default) |
| `--max_parents` | `1` | Maximum parent count per node |
| `--sample_size` | `200000` | Structure learning sampling size |
| `--df_sample_size` | `10000000` | BN training join sample count |
| `--max_table_data` | `20000000` | HDF file max row count |
| `--preprocessed_dir` | `None` | JOBLightRanges only: preprocessed data output directory |

### Inference Parameters

No additional parameters. Input/output file paths are specified via `--query_file` and `--output_file`.

---

## Key Implementation Details

### 1. Schema Dynamic Selection

Different benchmarks use different `SchemaGraph` objects, managed in the `get_schema()` function:

- `stats`: `gen_stats_light_schema()`
- `joblight`: `gen_job_light_imdb_schema()`
- `joblightranges`: **Special** `gen_job_light_ranges_schema()` — keeps `phonetic_code`, `imdb_index`, `series_years` as relevant attributes
- `jobm`: `gen_imdb_schema()`

**Important**: The JOBLightRanges schema does NOT mark these columns as `irrelevant_attributes` in the `title` table, ensuring the BN model can learn their distributions.

### 2. CSV Header Processing

STATS benchmark CSV has headers, while IMDB benchmark CSVs do not. `prepare_all_tables()` controls this via the `stats` parameter:

```python
prepare_all_tables(schema, hdf_path, stats=True) # Stats
prepare_all_tables(schema, hdf_path, stats=False) # IMDB
```

**Key**: Passing the wrong `stats` value causes data row misalignment or field name corruption.

### 3. Deterministic Model Loading Order

`load_ensemble_sorted()` uses **sorted** file listing to load models, unlike `os.listdir()`:

```python
pkl_files = sorted(f for f in os.listdir(model_dir) if f.endswith(".pkl"))
```

**Critical**: Each BN index (`bn_index`) in the ensemble is crucial for inference. Inconsistent ordering causes `bn_index` errors and inference failure.

### 4. JOBLightRanges Preprocessing

#### Data Preprocessing (`preprocess_joblr_csv`)

Three conversion functions:

- `_convert_phonetic_code_to_int(code)`: `'A1234'` → `(letter_index) * 100000 + 1234`
- `_roman_to_int(s)`: `'III'` → `3`
- `_parse_series_years(val)`: `'2000-2010'` → `2000`

Conversions target `title.csv` original data (column indices are fixed).

#### SQL Preprocessing (`preprocess_joblr_subquery_sql`)

Uses regex patterns to replace predicate values in SQL:

```python
# at SQL middleto t.phonetic_code<='A123' combineReplaceas t.phonetic_code<=NUMBER
pattern = r"t\.phonetic_code\s*(<=|>=|=|<|>)\s*'([A-Z]\d+)'"
```

**Key**: SQL preprocessing executes before inference starts; temporary files are deleted after completion.

### 5. Inference Flow (`_estimate_one_query`)

Single query estimation steps:

1. **Parse**: `parse_query(query_str, schema)` → structured Query object
2. **Select BN**: `bn_ensemble._greedily_select_first_cardinality_bn()`
3. **Generate Factors**: `generate_factors()` → probability factor list
4. **Optimize Factors**: `factor_refine()` → merge and optimize
5. **Convert Format**: map indicator expectation factors to `parse_result` items
6. **Inference**: `bn_ensemble.cardinality()` → final estimate value

**Key**: `bn_index` must correctly map to the corresponding BN in the loaded ensemble (resolved via `bn_ensemble.bns.index(factor.spn)`).

---

## Troubleshooting

### Issue 1: `ModuleNotFoundError: No module named 'pgmpy'`

**Cause**: Missing dependency in environment

**Solution**:
```bash
conda activate TestEnv # or your virtual environment
pip install numpy==1.22.0 pandas==1.5.3 pgmpy==1.0.0 sqlparse tables
```

### Issue 2: `ValueError: numpy.dtype size changed`

**Cause**: numpy/pandas version incompatibility

**Solution**: Ensure compatible version combinations are installed (common after upgrades). Do not upgrade pgmpy.

### Issue 3: Inference Returns All 1.0 (Cannot Estimate)

**Cause**: Query parsing failed or schema configuration error

**Check**:
- SQL syntax is correct (matches benchmark schema)
- JOBLightRanges queries are preprocessed
- Log warnings for details

### Issue 4: bn_index Out of Range

**Cause**: Inconsistent model loading order

**Solution**: Ensure using `load_ensemble_sorted()` rather than `load_ensemble()`.

---

## Performance Metrics

### Typical Performance (Stats Benchmark, 5 Queries)

| Metric | Value |
|-----|-----|
| Models Loaded | 11 |
| Avg Inference Latency | 0.0024 sec |
| Total Inference Time | 0.01 sec |
| Success Rate | ~80-100% |

### Influencing Factors

- **Query Complexity**: More JOIN tables means slower parsing and inference
- **Sample Size**: Larger `--df_sample_size` means slower training but more accurate models
- **BN Count**: Depends on schema relationship count (Stats ~11, JOBM ~50)

---

## Output File Descriptions

### Model Directory (`model_dir`)

```
checkpoints/stats_models/
├── 0_chow-liu_1.pkl # BN model for relationship 1
├── 1_chow-liu_1.pkl # BN model for relationship 2
└── ... # additional model files
```

Each `.pkl` file is a complete `Bayescard_BN` object containing a trained Bayesian Network with optimized parameters.

### HDF Directory (`hdf_path`)

```
checkpoints/stats_hdf/
├── meta_data.pkl # Table sizes, attribute types metadata
├── table_name.hdf # HDF5 data file per table
└── ...
```

HDF files are generated by `prepare_all_tables()` for BN training. Not needed during inference.

### Result File (`output_file`)

Plain text file, one floating-point number per line:

```
79851.00000000003
1.0
5331.335489717553
...
```

Line count equals input query count (including skipped lines and comments).

---

## References

Detailed technical documentation:
- [../PGMPY_FIX_EXPLANATION.md](../PGMPY_FIX_EXPLANATION.md) — Complete Pgmpy import fix explanation
- [../README_CN.md](../README_CN.md) — Chinese project guide
- `bayescard/` — BayesCard source code (adapted from DeepDB/OpenCE)
