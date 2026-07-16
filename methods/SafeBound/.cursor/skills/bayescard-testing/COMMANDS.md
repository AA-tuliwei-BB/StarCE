# BayesCard 快速命令参考

## 环境准备

```bash
# 激活虚拟环境
conda activate TestEnv

# 验证依赖
python -c "import numpy, pandas, pgmpy; print('OK')"
```

---

## 快速命令模板

### STATS-CEB

```bash
cd methods/SafeBound  # 需要在项目根目录下运行

# 训练
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf \
  --model_dir checkpoints/stats_models

# 推理
python test_benchmark.py infer --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --model_dir checkpoints/stats_models \
  --query_file ../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/STATS-CEB/subquery/result/bayescard.txt
```

### JOBLight

```bash
# 训练
python test_benchmark.py train --benchmark joblight \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/imdb_light_hdf \
  --model_dir checkpoints/joblight_models

# 推理
python test_benchmark.py infer --benchmark joblight \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/joblight_models \
  --query_file ../../Benchmark/workloads/JOBLight/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/JOBLight/subquery/result/bayescard.txt
```

### JOBLightRanges

```bash
# 训练（含数据预处理）
python test_benchmark.py train --benchmark joblightranges \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/joblr_hdf \
  --model_dir checkpoints/joblr_models \
  --preprocessed_dir checkpoints/joblr_preprocessed

# 推理（含 SQL 预处理）
python test_benchmark.py infer --benchmark joblightranges \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/joblr_models \
  --query_file ../../Benchmark/workloads/JOBLightRanges/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/JOBLightRanges/subquery/result/bayescard.txt
```

### JOBM

```bash
# 训练
python test_benchmark.py train --benchmark jobm \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/imdb_full_hdf \
  --model_dir checkpoints/jobm_models

# 推理
python test_benchmark.py infer --benchmark jobm \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/jobm_models \
  --query_file ../../Benchmark/workloads/JOBM/subquery/subquery.sql \
  --output_file ../../Benchmark/workloads/JOBM/subquery/result/bayescard.txt
```

---

## 自定义参数示例

```bash
# 快速实验（降低样本数）
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf_quick \
  --model_dir checkpoints/stats_models_quick \
  --df_sample_size 1000000 \
  --sample_size 50000

# 高精度模型（增加样本数）
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf_hi \
  --model_dir checkpoints/stats_models_hi \
  --df_sample_size 50000000 \
  --sample_size 500000

# 使用不同的结构学习算法
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf \
  --model_dir checkpoints/stats_models_alt \
  --algorithm pc \
  --max_parents 2
```

---

## 日志查看

```bash
# 查看最新日志
tail -f logs/bayescard_*.log

# 查看特定时间的日志
cat logs/bayescard_20260207-120000.log

# 统计推理错误
grep "failed" logs/bayescard_*.log | wc -l
```

---

## 调试单个查询

```python
# 在 Python REPL 中测试
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

## 性能检查

```bash
# 查看模型文件大小
du -sh checkpoints/stats_models/

# 查看 HDF 文件大小
du -sh checkpoints/stats_hdf/

# 计数模型数量
ls -1 checkpoints/stats_models/*.pkl | wc -l
```

---

## 清理旧文件

```bash
# 删除特定基准的中间文件（保留模型）
rm -rf checkpoints/stats_hdf/

# 删除所有临时预处理文件
find . -name "_bayescard_preprocessed_*.sql" -delete

# 完整清理（谨慎！）
rm -rf checkpoints/ logs/
```
