---
name: bayescard-testing
description: 使用 BayesCard 在 STATS-CEB、JOBLight、JOBLightRanges、JOBM 基准上进行贝叶斯网络训练和基数估计。提供统一脚本入口、四种基准支持、数据预处理、模型训练/推理工作流。当需要使用 test_benchmark.py、BayesCard 基数估计、JOBLightRanges 预处理、模型加载、子查询推理时使用。
---

# BayesCard 测试脚本

## 快速开始

BayesCard 通过贝叶斯网络（Bayesian Network）进行基数估计。脚本 `test_benchmark.py` 提供统一的训练和推理入口。

### 基本命令结构

```bash
cd methods/SafeBound  # 需要在项目根目录下运行

# 训练模型
python test_benchmark.py train --benchmark <BENCHMARK> \
  --csv_path <CSV_PATH_TEMPLATE> \
  --hdf_path <HDF_DIR> \
  --model_dir <MODEL_DIR>

# 推理估计
python test_benchmark.py infer --benchmark <BENCHMARK> \
  --csv_path <CSV_PATH_TEMPLATE> \
  --model_dir <MODEL_DIR> \
  --query_file <QUERY_FILE> \
  --output_file <OUTPUT_FILE>
```

### 支持的基准

| 基准 | CSV 路径示例 | 特点 |
|------|-----------|------|
| `stats` | `Data/Stats/{}.csv` | 包含表头的 CSV，最快 |
| `joblight` | `Data/IMDB/{}.csv` | IMDB 标准子集，无表头 |
| `joblightranges` | `Data/IMDB/{}.csv` | 包含范围谓词，需要预处理 |
| `jobm` | `Data/IMDB/{}.csv` | 完整 IMDB，最复杂 |

---

## 工作流

### 流程 1：标准基准（STATS-CEB、JOBLight、JOBM）

**无需特殊处理，数据格式统一**。

#### 训练

```bash
python test_benchmark.py train --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --hdf_path checkpoints/stats_hdf \
  --model_dir checkpoints/stats_models
```

**输出**: `checkpoints/stats_models/` 下生成多个 `.pkl` 文件（每个关系一个 BN 模型）

#### 推理

```bash
python test_benchmark.py infer --benchmark stats \
  --csv_path Data/Stats/{}.csv \
  --model_dir checkpoints/stats_models \
  --query_file ../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
  --output_file result_bayescard.txt
```

**输出格式**: 每行一个浮点数，对应输入查询的基数估计值

```
79851.00000000003
1.0
5331.335489717553
321.25077452098594
174304.99999999994
```

---

### 流程 2：JOBLightRanges（需要数据和 SQL 预处理）

JOBLightRanges 使用范围谓词（如 `phonetic_code` 的字符串值），而 BayesCard 的 BN 只支持数值。需要两层预处理。

#### 特殊性质

- **phonetic_code**: 字符串如 `'A1234'` → 数值
- **imdb_index**: 罗马数字如 `'III'` → 数值
- **series_years**: 范围如 `'2000-2010'` → 起始年份

#### 训练（包含数据预处理）

```bash
python test_benchmark.py train --benchmark joblightranges \
  --csv_path Data/IMDB/{}.csv \
  --hdf_path checkpoints/joblr_hdf \
  --model_dir checkpoints/joblr_models \
  --preprocessed_dir checkpoints/joblr_preprocessed
```

**内部步骤**:
1. 复制 IMDB CSV 文件到 `checkpoints/joblr_preprocessed/`
2. 转换 `title.csv` 的三个字符串列为整数
3. 使用转换后的 CSV 生成 HDF 和训练模型

#### 推理（包含 SQL 预处理）

```bash
python test_benchmark.py infer --benchmark joblightranges \
  --csv_path Data/IMDB/{}.csv \
  --model_dir checkpoints/joblr_models \
  --query_file ../../Benchmark/workloads/JOBLightRanges/subquery/subquery.sql \
  --output_file result_bayescard.txt
```

**内部步骤**:
1. 读取原始 SQL 查询（包含字符串谓词如 `t.phonetic_code<='A123'`）
2. 自动转换所有字符串谓词为数值谓词
3. 推理完成后，清理临时预处理的 SQL 文件

---

## 高级参数

### 训练参数

| 参数 | 默认值 | 说明 |
|-----|--------|------|
| `--algorithm` | `chow-liu` | BN 结构学习算法（建议保留默认） |
| `--max_parents` | `1` | 每个节点的最大父节点数 |
| `--sample_size` | `200000` | 结构学习的子采样大小 |
| `--df_sample_size` | `10000000` | BN 训练的 join 采样数 |
| `--max_table_data` | `20000000` | HDF 文件的最大行数 |
| `--preprocessed_dir` | `None` | JOBLightRanges 专用：预处理数据输出目录 |

### 推理参数

无额外参数。输入/输出文件路径由 `--query_file` 和 `--output_file` 指定。

---

## 关键实现细节

### 1. Schema 动态选择

不同基准使用不同的 `SchemaGraph` 对象，已通过 `get_schema()` 函数集中管理：

- `stats`: `gen_stats_light_schema()`
- `joblight`: `gen_job_light_imdb_schema()`
- `joblightranges`: **特殊** `gen_job_light_ranges_schema()` — 保留 `phonetic_code`, `imdb_index`, `series_years` 为相关属性
- `jobm`: `gen_imdb_schema()`

**重要**: JOBLightRanges 的 schema 在 `title` 表中**不**将这些列标记为 `irrelevant_attributes`，保证 BN 模型能够学习这些列的分布。

### 2. CSV 表头处理

Stats 基准的 CSV 有表头，而 IMDB 基准无表头。`prepare_all_tables()` 通过 `stats` 参数控制：

```python
prepare_all_tables(schema, hdf_path, stats=True)   # Stats
prepare_all_tables(schema, hdf_path, stats=False)  # IMDB
```

**关键**: 传入错误的 `stats` 值会导致数据行错位或字段名混乱。

### 3. 模型加载的确定性顺序

`load_ensemble_sorted()` 使用**排序**的文件列表加载模型，而非 `os.listdir()` 的随机顺序：

```python
pkl_files = sorted(f for f in os.listdir(model_dir) if f.endswith(".pkl"))
```

**为什么重要**: BN ensemble 中每个 BN 的索引（`bn_index`）用于推理时的因子关联。顺序不一致会导致 `bn_index` 错误和推理失败。

### 4. JOBLightRanges 预处理

#### 数据预处理 (`preprocess_joblr_csv`)

三个转换函数：

- `_convert_phonetic_code_to_int(code)`: `'A1234'` → `(A字的编号) * 100000 + 1234`
- `_roman_to_int(s)`: `'III'` → `3`
- `_parse_series_years(val)`: `'2000-2010'` → `2000`

转换应用于 `title.csv` 的原始数据（按列号指定）。

#### SQL 预处理 (`preprocess_joblr_subquery_sql`)

使用正则表达式在 SQL 中替换谓词值：

```python
# 在 SQL 中找到 t.phonetic_code<='A123' 并替换为 t.phonetic_code<=NUMBER
pattern = r"t\.phonetic_code\s*(<=|>=|=|<|>)\s*'([A-Z]\d+)'"
```

**关键**: SQL 预处理在推理开始前执行，完成后临时文件被删除。

### 5. 推理流程（`_estimate_one_query`）

单个查询的估计步骤：

1. **解析**: `parse_query(query_str, schema)` → 结构化 Query 对象
2. **选择首个 BN**: `bn_ensemble._greedily_select_first_cardinality_bn()`
3. **生成因子**: `generate_factors()` → 概率因子列表
4. **精化因子**: `factor_refine()` → 合并和优化
5. **转换格式**: 映射每个 IndicatorExpectation 因子到 `parse_result` 项
6. **推理**: `bn_ensemble.cardinality()` → 最终估计值

**关键**: `bn_index` 必须正确映射到加载的 BN ensemble 中的对应 BN（通过 `bn_ensemble.bns.index(factor.spn)` 获取）。

---

## 故障排除

### 问题 1：`ModuleNotFoundError: No module named 'pgmpy'`

**原因**: 环境缺少依赖

**解决**:
```bash
conda activate TestEnv  # 或你的虚拟环境
pip install numpy==1.22.0 pandas==1.5.3 pgmpy==1.0.0 sqlparse tables
```

### 问题 2：`ValueError: numpy.dtype size changed`

**原因**: numpy/pandas 版本不兼容

**解决**: 确保安装兼容的版本组合（见上文）。不要升级 pgmpy。

### 问题 3：推理返回全 1.0（无法估计）

**原因**: 查询解析失败或 schema 配置错误

**检查**:
- SQL 语法是否正确（与基准的 schema 匹配）
- JOBLightRanges 查询是否已预处理
- 日志中的警告信息

### 问题 4：bn_index 超出范围

**原因**: 模型加载顺序不一致

**解决**: 确保使用 `load_ensemble_sorted()` 而非直接 `load_ensemble()`。

---

## 性能指标

### 典型性能（Stats 基准，5 查询）

| 指标 | 值 |
|-----|-----|
| 加载模型数 | 11 |
| 平均推理延迟 | 0.0024 秒 |
| 总推理时间 | 0.01 秒 |
| 成功率 | ~80-100% |

### 影响因素

- **查询复杂度**: JOIN 表数越多，解析和推理越慢
- **样本大小**: `--df_sample_size` 越大，训练越慢但模型越精确
- **BN 数量**: 取决于 schema 的关系数（Stats ~11 个，JOBM ~50 个）

---

## 输出文件说明

### 模型目录 (`model_dir`)

```
checkpoints/stats_models/
├── 0_chow-liu_1.pkl      # 第 1 个关系的 BN 模型
├── 1_chow-liu_1.pkl      # 第 2 个关系的 BN 模型
└── ...                   # 更多模型文件
```

每个 `.pkl` 文件是一个完整的 `Bayescard_BN` 对象，包含参数化的贝叶斯网络。

### HDF 目录 (`hdf_path`)

```
checkpoints/stats_hdf/
├── meta_data.pkl         # 表大小、属性类型等元数据
├── table_name.hdf        # 每个表的 HDF5 数据文件
└── ...
```

HDF 文件由 `prepare_all_tables()` 生成，用于 BN 训练。推理时不需要。

### 结果文件 (`output_file`)

纯文本，每行一个浮点数：

```
79851.00000000003
1.0
5331.335489717553
...
```

行数等于输入查询数（含跳过的空行和注释）。

---

## 附加资源

详细技术细节见:
- [../PGMPY_FIX_EXPLANATION.md](../PGMPY_FIX_EXPLANATION.md) — Pgmpy 导入修复的完整说明
- [../README_CN.md](../README_CN.md) — 中文项目指南
- `bayescard/` — BayesCard 源代码（DeepDB/OpenCE 改进版）
