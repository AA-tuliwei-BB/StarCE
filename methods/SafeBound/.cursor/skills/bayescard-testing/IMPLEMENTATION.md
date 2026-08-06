---
name: bayescard-implementation-details
description: BayesCard script internal implementation details, data flow, error handling, logging mechanism. Use when needing to understand how the script handles Pgmpy imports, data preprocessing, model persistence, query parsing, and inference algorithms.
---

# BayesCard Implementation Details

## File Structure

```
methods/SafeBound/
├── test_benchmark.py # Main script (training + inference entry point)
├── bayescard/
│ ├── Schemas/
│ │ ├── stats/schema.py # STATS benchmark schema
│ │ └── imdb/schema.py # IMDB database column schema (including JOBLightRanges)
│ ├── DataPrepare/
│ │ ├── prepare_single_tables.py # CSV → HDF conversion (including stats parameter)
│ │ ├── join_data_preparation.py # Join sampling preparation
│ │ └── query_prepare_BayesCard.py # Subquery generation
│ ├── Models/
│ │ ├── Bayescard_BN.py # Core BN model (including Pgmpy import fix)
│ │ └── BN_ensemble_model.py # BN ensemble management
│ ├── DeepDBUtils/ # Query parsing, inference
│ └── pgympy/ # Local Pgmpy copy (with fixed imports)
└── logs/
 └── bayescard_*.log # Timestamped runtime logs
```

---

## Data Flow

### Training Flow

```
Input CSV → prepare_all_tables() → HDF File
 ↓
meta_data.pkl (table metadata)
 ↓
JoinDataPreparator.generate_n_samples() → Join Sampling Data
 ↓
Bayescard_BN.build_from_data() → Chow-Liu Structure Learning
 ↓
pickle.dump() → .pkl Model Files
```

### Inference Flow

```
Input SQL File → parse_query() → Query Object
 ↓
_greedily_select_first_cardinality_bn() → Select First BN
 ↓
generate_factors() → Probability Factors
 ↓
factor_refine() → Factor Merge Optimization
 ↓
parse_query_all() → Standardized Format
 ↓
bn_ensemble.cardinality() → Final Estimate Value
```

---

## Key Classes and Functions

### SchemaGraph Manager

```python
def get_schema(benchmark, csv_path):
 """
 Returns the SchemaGraph object for the given benchmark.
 
 Parameters:
 benchmark: "stats" | "joblight" | "joblightranges" | "jobm"
 csv_path: CSV path template, e.g. "Data/Stats/{}.csv"
 
 Returns:
 SchemaGraph object defining tables, attributes, relationships, indexes
 
 Notes:
 - Stats: gen_stats_light_schema()
 - JOBLight/JOBM: gen_job_light_imdb_schema() / gen_imdb_schema()
 - JOBLightRanges: gen_job_light_ranges_schema() 
 (Special: keeps phonetic_code/imdb_index/series_years as relevant attributes)
 """
```

### Deterministic Model Loading

```python
def load_ensemble_sorted(schema, model_dir):
 """
 Load BN ensemble in deterministic order (critical!).
 
 Steps:
 1. Sort all .pkl files in model_dir
 2. Load in order, append to bn_ensemble.bns list
 3. Set inference algorithm to "exact-jit"
 4. Initialize inference engine
 
 Returns:
 BN_ensemble object, with bn.bns = [bn1, bn2, ..., bnN]
 
 Notes:
 - File order must be consistent, otherwise bn_index will be wrong
 - Each BN index = position in bns list
 """
```

### JOBLightRanges Data Preprocessing

```python
def preprocess_joblr_csv(src_csv_path_template, dst_dir):
 """
 Copy IMDB CSV and convert title table string columns to integers.
 
 Conversions:
 - col 2 (imdb_index): roman numeral → integer (_roman_to_int)
 - col 6 (phonetic_code): letter+number → integer (_convert_phonetic_code_to_int)
 - col 10 (series_years): year range → year (_parse_series_years)
 
 Output:
 New CSV path template pointing to converted CSV directory
 
 Key Steps:
 1. Read original CSV (header=None, IMDB has no header)
 2. Apply conversion functions per column
 3. Write output CSV (preserving original format)
 """

def _convert_phonetic_code_to_int(code):
 """
 'A1234' → (A-A)*100000 + 1234 = 1234
 'B5678' → (B-A)*100000 + 5678 = 105678
 
 Design rationale: preserve ordering for <= / >= operations.
 """

def _roman_to_int(s):
 """
 'I' → 1, 'III' → 3, 'IV' → 4, 'IX' → 9, etc.
 
 Uses standard roman numeral rules (subtractive notation).
 """

def _parse_series_years(val):
 """
 '2000-2010' → 2000
 '????-????' → 0
 
 Approximates year ranges as numerical proxies.
 """
```

### JOBLightRanges SQL Preprocessing

```python
def preprocess_joblr_subquery_sql(src_sql_path, dst_sql_path):
 """
 Convert SQL string predicates to numeric predicates.
 
 Processing patterns:
 - t.phonetic_code<='A123' → t.phonetic_code<=1234
 - t.imdb_index<='III' → t.imdb_index<=3
 - t.series_years<='2000-2010' → t.series_years<=2000
 
 Special Handling:
 - Encoding P/G single letters (around lines 267-268)
 - Preserves all SQL structure
 
 Output:
 Converted SQL file path (temporary file, deleted after inference)
 """
```

### Single Query Inference

```python
def _estimate_one_query(bn_ensemble, schema, query_str):
 """
 Estimate cardinality for a single query.
 
 Parameters:
 bn_ensemble: Loaded BN ensemble
 schema: SchemaGraph
 query_str: SQL string
 
 Returns:
 Float cardinality estimate
 
 Internal Flow:
 1. parse_query(): string → Query object (attributes, tables, joins, predicates)
 2. _greedily_select_first_cardinality_bn(): Select first BN
 3. generate_factors(): Decompose into probability factors (indicator expectations etc.)
 4. factor_refine(): Merge factors
 5. parse_query_all(): Convert to standard format (list of dicts with bn_index, inverse, query, expectation)
 6. bn_ensemble.cardinality(): Combine all factor probabilities → final estimate
 
 Exception Handling:
 - Any exception, return None
 - Post-processing: None or <= 0 → default to 1.0
 - Logs record warnings
 """
```

---

## Pgmpy Import Issue Fix

### Issue

BayesCard contains a local `pgmpy` copy (directory `bayescard/pgympy/`), but internal imports use **uppercase** `Pgmpy`:

```python
# Incorrect imports
from Pgmpy.inference import VariableEliminationJIT
import Pgmpy.models
```

The module name is lowercase `pgympy`, causing `ModuleNotFoundError`.

### Fix Solution

**Directly modify all Python files** (bypassing alias approach):

1. **~28 files in `bayescard/pgympy/`**: Global replace
 - `from Pgmpy.` → `from pgympy.`
 - `import Pgmpy.` → `import pgympy.`

2. **`bayescard/Models/Bayescard_BN.py`**: 6 import fixes

3. **`bayescard/pgympy/factors/discrete/DiscreteFactor.py`**: Commented out unused `import numba`

### Alias Approach (Attempted and Rejected)

Initially tried a `bayescard/Pgmpy.py` alias module:

```python
# Non-viable approach
import pgympy as Pgmpy # in sys.modules
sys.modules['Pgmpy'] = pgympy
```

**Why it failed**: `pgmpy` submodules internally perform recursive imports `from Pgmpy.XXX`. The alias is not visible within submodule import contexts, causing circular dependency and import failure.

**Conclusion**: Directly modifying source code is the only reliable solution.

---

## CSV Header Processing

### Stats vs IMDB Differences

| Property | Stats | IMDB |
|------|-------|------|
| Header | ✅ Yes | ❌ No |
| prepare_all_tables() param | `stats=True` | `stats=False` |
| read_table_csv() behavior | `header=0` (read header) | `header=None` (no header) |
| Data rows | 2 rows | 1 row |

### Key Function

```python
def prepare_single_table(schema_graph, table, path, stats=False):
 """
 Read single table data from CSV and generate HDF file.
 
 Parameters:
 stats: True for Stats, False for IMDB
 
 Flow:
 1. read_table_csv(table_obj, csv_seperator=',', stats=stats)
 - stats=True: header=0 (skip header row)
 - stats=False: header=None (no header)
 2. Add multiplier column (for JOIN sampling)
 3. Process NULL values
 4. Save to HDF
 
 Notes:
 - Must correctly set the stats parameter, otherwise data rows are misaligned
 - The stats parameter must also be passed through to read_table_csv
 """
```

---

## Logging and Monitoring

### Log Output

The script generates log files in the `logs/` directory. Filename format: `bayescard_YYYYMMDD-HHMMSS.log`

### Log Levels

| Level | Purpose | Example |
|------|------|------|
| INFO | Normal progress | "Loaded BN model: 0_chow-liu_1.pkl" |
| WARNING | Expected errors | "Query 5 failed: ..." |
| ERROR | Critical errors | (usually causes process termination) |

### Key Log Checkpoints

#### Training

```
Generating HDF files in ...
HDF generation complete.
Training BN ensemble on N relationships:
 Relationship 1
 Relationship 2
Training BN 1/N on rel1 ...
Model saved: path/0_chow-liu_1.pkl
Training completed in X.X seconds.
```

#### Inference

```
Loading BN ensemble from ...
Loaded BN model: 0_chow-liu_1.pkl
...
Loaded 11 BN models from checkpoints/stats_models
Running inference on N queries from ...
 processed 500 / 5000 (avg latency: 0.0024s)
Results saved to ...
Total time: X.XXs | Avg latency: 0.0024s | Errors: N
```

---

## Performance Optimization Suggestions

### 1. Model Training Acceleration

- Lower `--df_sample_size` (default 10M)
- Increase `--max_parents` (learn more complex dependency structures)
- Reduce `--sample_size` (structure learning sampling)

### 2. Inference Acceleration

- Use `exact-jit` inference algorithm (already set)
- Batch process queries (avoids repeated model loading)
- Use smaller query files for testing

### 3. Cache Optimization

- Increase `--max_table_data` to reduce HDF chunk count
- Use SSD storage for HDF files
- Clean up old `.hdf` and `.pkl` files

---

## Common Error Diagnosis

### Error: `ValueError: bn_index out of range`

**Cause**: `bn_index` value exceeds the number of loaded BNs

**Root cause**: Inconsistent model loading order causes `bn_index` mapping errors

**Fix**: Ensure using `load_ensemble_sorted()` rather than `load_ensemble()`

### Error: `Query parsing failed: NameError`

**Cause**: SQL table name or column name not defined in schema

**Check**:
- SQL matches the benchmark (do not mix STATS and IMDB SQL)
- Column names are correctly capitalized
- Table aliases are defined in FROM clause

### Error: `Estimate is 1.0 for all queries`

**Cause**: Query parsing silently failed, using default value 1.0

**Debug**:
1. Check logs for "failed" warning count
2. Test a single query
3. Verify schema is loaded correctly
4. For JOBLightRanges, confirm SQL preprocessing is executing

---

## Extension and Modification

### Adding a New Benchmark

1. Create a new schema file in `bayescard/Schemas/`
2. Add a new `elif` branch in `get_schema()`
3. Set whether header processing is needed in `is_stats_benchmark()`
4. Add necessary data preprocessing in `cmd_train()`
5. Add necessary SQL preprocessing in `cmd_infer()`
6. Add the new benchmark name to the argument parser `choices` list

### Modifying the Inference Algorithm

```python
# In load_ensemble_sorted()
bn.infer_algo = "exact-jit" # change algorithm here
# Options: "exact", "belief-propagation", "map", etc.
```

### Adding Custom Predicate Processing

For benchmarks needing SQL/data conversion, add regex patterns and replacements in the appropriate preprocessing function.

---

## Debugging Suggestions

### 1. Minimal Test

Create a simple query test file with 3-5 queries for quick verification.

### 2. Log Analysis

```bash
tail -f logs/bayescard_*.log
```

Monitor progress in real time and quickly identify errors.

### 3. Single-Step Debugging

```python
# Add to script
import pdb
pdb.set_trace() # Pause at key point
```

### 4. Schema Verification

```python
# Verify schema
schema = get_schema("stats", "Data/Stats/{}.csv")
print(schema.tables)
print(schema.relationships)
```

### 5. Query Parsing Test

```python
from DeepDBUtils.evaluation.utils import parse_query

query = parse_query("SELECT COUNT(*) FROM badges", schema)
print(query.table_set)
print(query.column_set)
```
