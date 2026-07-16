# BayesCard QuickCommand Reference

## Environment Setup

```bash
# ActivateVirtualEnvironment
conda activate TestEnv

# VerificationDependency
python -c "import numpy, pandas, pgmpy; print('OK')"
```

---

## Quick Command Template

### STATS-CEB

```bash
cd methods/SafeBound  # Needin the project root directorydownrunning

# Training
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf \
  --model_dir checkpoints/stats_models

# Inference
python test_benchmark.py infer --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --model_dir checkpoints/stats_models \
  --query_file ../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/STATS-CEB/subquery/result/bayescard.txt
```

### JOBLight

```bash
# Training
python test_benchmark.py train --benchmark joblight \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/imdb_light_hdf \
  --model_dir checkpoints/joblight_models

# Inference
python test_benchmark.py infer --benchmark joblight \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/joblight_models \
  --query_file ../../Benchmark/workloads/JOBLight/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/JOBLight/subquery/result/bayescard.txt
```

### JOBLightRanges

```bash
# Training (with Data Preprocessing)
python test_benchmark.py train --benchmark joblightranges \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/joblr_hdf \
  --model_dir checkpoints/joblr_models \
  --preprocessed_dir checkpoints/joblr_preprocessed

# Inference (with SQL Preprocessing)
python test_benchmark.py infer --benchmark joblightranges \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/joblr_models \
  --query_file ../../Benchmark/workloads/JOBLightRanges/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/JOBLightRanges/subquery/result/bayescard.txt
```

### JOBM

```bash
# Training
python test_benchmark.py train --benchmark jobm \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/imdb_full_hdf \
  --model_dir checkpoints/jobm_models

# Inference
python test_benchmark.py infer --benchmark jobm \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/jobm_models \
  --query_file ../../Benchmark/workloads/JOBM/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/JOBM/subquery/result/bayescard.txt
```

---

## Custom Parameter Exampless

```bash
# Quick Experiment（lower sample count）
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf_quick \
  --model_dir checkpoints/stats_models_quick \
  --df_sample_size 1000000 \
  --sample_size 50000

# High Accuracy Model（Increase Sample count）
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf_hi \
  --model_dir checkpoints/stats_models_hi \
  --df_sample_size 50000000 \
  --sample_size 500000

# Use different structure learning algorithm
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf \
  --model_dir checkpoints/stats_models_alt \
  --algorithm pc \
  --max_parents 2
```

---

## LogsView

```bash
# View latest Logs
tail -f logs/bayescard_*.log

# View specific timestamped Logs
cat logs/bayescard_20260207-120000.log

# StatisticsInferenceError
grep "failed" logs/bayescard_*.log | wc -l
```

---

## Debug Single Query

```python
# at Python REPL middleTest
import sys
sys.path.insert(0, 'bayescard')

from Schemas.stats.schema import gen_stats_light_schema
from DeepDBUtils.evaluation.utils import parse_query

schema = gen_stats_light_schema("Data/Stats/{}.csv")
query = parse_query("SELECT COUNT(*) FROM badges", schema)
print(f"Tables: {query.table_set}")
print(f"Columns: {query.column_set}")
```

---

## PerformanceCheck

```bash
# ViewModel FilesSize
du -sh checkpoints/stats_models/

# View HDF File Size
du -sh checkpoints/stats_hdf/

# CountModelCount
ls -1 checkpoints/stats_models/*.pkl | wc -l
```

---

## CleanoldFile

```bash
# DeleteSpecificBenchmarkIntermediate Files（PreserveModel）
rm -rf checkpoints/stats_hdf/

# DeleteAllTemporaryPreprocessingFile
find . -name "_bayescard_preprocessed_*.sql" -delete

# Complete Clean (Caution!)
rm -rf checkpoints/ logs/
```
