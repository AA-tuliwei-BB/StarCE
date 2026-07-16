---
name: bayescard-implementation-details
description: BayesCard 脚本的内部实现细节、数据流、错误处理、日志机制。当需要理解脚本如何处理 Pgmpy 导入、数据预处理、模型持久化、查询解析、推理算法时使用。
---

# BayesCard 实现细节

## 文件结构

```
methods/SafeBound/
├── test_benchmark.py              # 主脚本（训练 + 推理入口）
├── bayescard/
│   ├── Schemas/
│   │   ├── stats/schema.py         # Stats 基准 schema
│   │   └── imdb/schema.py          # IMDB 系列 schema（含 JOBLightRanges）
│   ├── DataPrepare/
│   │   ├── prepare_single_tables.py    # CSV → HDF 转换（含 stats 参数）
│   │   ├── join_data_preparation.py    # Join 采样准备
│   │   └── query_prepare_BayesCard.py  # 查询因子生成
│   ├── Models/
│   │   ├── Bayescard_BN.py         # 核心 BN 模型（含 Pgmpy 导入修复）
│   │   └── BN_ensemble_model.py    # BN 集合管理
│   ├── DeepDBUtils/                # 查询解析、推理工具
│   └── pgympy/                     # 本地 Pgmpy 副本（已修复导入）
└── logs/
    └── bayescard_*.log             # 按时间戳的运行日志
```

---

## 数据流

### 训练流程

```
输入 CSV → prepare_all_tables() → HDF 文件
    ↓
meta_data.pkl (表元数据)
    ↓
JoinDataPreparator.generate_n_samples() → Join 采样数据
    ↓
Bayescard_BN.build_from_data() → Chow-Liu 结构学习
    ↓
pickle.dump() → .pkl 模型文件
```

### 推理流程

```
输入 SQL 文件 → parse_query() → Query 对象
    ↓
_greedily_select_first_cardinality_bn() → 选择首个 BN
    ↓
generate_factors() → 概率因子
    ↓
factor_refine() → 因子合并优化
    ↓
parse_query_all() → 标准化格式
    ↓
bn_ensemble.cardinality() → 最终估计值
```

---

## 关键类和函数

### SchemaGraph 管理

```python
def get_schema(benchmark, csv_path):
    """
    返回对应基准的 SchemaGraph 对象。
    
    Parameters:
      benchmark: "stats" | "joblight" | "joblightranges" | "jobm"
      csv_path: CSV 路径模板，如 "Data/Stats/{}.csv"
    
    Returns:
      SchemaGraph 对象，定义表、属性、关系、索引
    
    注意:
      - Stats: gen_stats_light_schema()
      - JOBLight/JOBM: gen_job_light_imdb_schema() / gen_imdb_schema()
      - JOBLightRanges: gen_job_light_ranges_schema() 
        (特殊：phonetic_code/imdb_index/series_years 保持相关)
    """
```

### 确定性模型加载

```python
def load_ensemble_sorted(schema, model_dir):
    """
    以确定性顺序加载 BN 集合（关键！）。
    
    步骤:
      1. 排序 model_dir 中的所有 .pkl 文件
      2. 按顺序加载，append 到 bn_ensemble.bns 列表
      3. 设置推理算法为 "exact-jit"
      4. 初始化推理方法
    
    返回:
      BN_ensemble 对象，with bn.bns = [bn1, bn2, ..., bnN]
    
    注意:
      - 文件顺序必须一致，否则 bn_index 会错位
      - 每个 BN 的索引 = bns 列表中的位置
    """
```

### JOBLightRanges 数据预处理

```python
def preprocess_joblr_csv(src_csv_path_template, dst_dir):
    """
    复制 IMDB CSV 并转换 title 表的字符串列为整数。
    
    转换:
      - col 2 (imdb_index): 罗马数字 → 整数 (_roman_to_int)
      - col 6 (phonetic_code): 字母+数字 → 整数 (_convert_phonetic_code_to_int)
      - col 10 (series_years): 年份范围 → 起始年份 (_parse_series_years)
    
    输出:
      新的 CSV 路径模板，指向转换后的 CSV 目录
    
    关键步骤:
      1. 读取原始 CSV (header=None, IMDB 无表头)
      2. 按列应用转换函数
      3. 写回 CSV (保留原始格式)
    """

def _convert_phonetic_code_to_int(code):
    """
    'A1234' → (A-A)*100000 + 1234 = 1234
    'B5678' → (B-A)*100000 + 5678 = 105678
    
    设计原理: 保持序序关系，允许比较操作 <= / >= 等
    """

def _roman_to_int(s):
    """
    'I' → 1, 'III' → 3, 'IV' → 4, 'IX' → 9, etc.
    
    使用标准罗马数字规则（减法原则）
    """

def _parse_series_years(val):
    """
    '2000-2010' → 2000
    '????-????' → 0
    
    只提取起始年份作为 numerical 代理
    """
```

### JOBLightRanges SQL 预处理

```python
def preprocess_joblr_subquery_sql(src_sql_path, dst_sql_path):
    """
    将 SQL 中的字符串谓词转换为数值谓词。
    
    处理的模式:
      - t.phonetic_code<='A123' → t.phonetic_code<=1234
      - t.imdb_index<='III' → t.imdb_index<=3
      - t.series_years<='2000-2010' → t.series_years<=2000
    
    特殊处理:
      - 硬编码 P/G 单字母情况 (见行 267-268)
      - 保留所有其他 SQL 结构
    
    输出:
      转换后的 SQL 文件路径（临时文件，推理后删除）
    """
```

### 单查询推理

```python
def _estimate_one_query(bn_ensemble, schema, query_str):
    """
    估计单个查询的基数。
    
    参数:
      bn_ensemble: 加载的 BN 集合
      schema: SchemaGraph
      query_str: SQL 字符串
    
    返回:
      浮点数估计基数
    
    内部流程:
      1. parse_query(): 字符串 → Query 对象（属性、表、联接、谓词）
      2. _greedily_select_first_cardinality_bn(): 选择首个 BN
      3. generate_factors(): 分解为概率因子（IndicatorExpectation 等）
      4. factor_refine(): 合并相邻因子
      5. parse_query_all(): 转换为标准格式 (list of dicts with bn_index, inverse, query, expectation)
      6. bn_ensemble.cardinality(): 乘以所有因子概率 → 最终估计
    
    异常处理:
      - 捕获所有异常，返回 None
      - 调用处理: None 或 <= 0 → 默认为 1.0
      - 日志记录警告
    """
```

---

## Pgmpy 导入问题及修复

### 问题背景

BayesCard 包含本地 `pgmpy` 副本（目录 `bayescard/pgympy/`），但内部导入使用**大写** `Pgmpy`:

```python
# 错误：导入语句
from Pgmpy.inference import VariableEliminationJIT
import Pgmpy.models
```

实际模块名是小写 `pgympy`，导致 `ModuleNotFoundError`。

### 修复方案

**直接修改所有 Python 文件**（不使用别名模块）：

1. **`bayescard/pgympy/` 内 ~28 个文件**: 全局替换
   - `from Pgmpy.` → `from pgympy.`
   - `import Pgmpy.` → `import pgympy.`

2. **`bayescard/Models/Bayescard_BN.py`**: 6 处导入语句修复

3. **`bayescard/pgympy/factors/discrete/DiscreteFactor.py`**: 注释掉未使用的 `import numba`

### 为什么不使用别名

初期尝试过 `bayescard/Pgmpy.py` 别名模块：

```python
# 不可行的方案
import pgympy as Pgmpy  # 在 sys.modules 中注册
sys.modules['Pgmpy'] = pgympy
```

**失败原因**: `pgympy` 子模块内部会进行递归导入 `from Pgmpy.XXX`，别名在子模块的导入上下文中无效，导致循环依赖和导入失败。

**结论**: 直接修改源代码是唯一可靠的解决方案。

---

## CSV 和表头处理

### Stats vs IMDB 差异

| 特性 | Stats | IMDB |
|------|-------|------|
| 表头 | ✅ 有 | ❌ 无 |
| prepare_all_tables() 参数 | `stats=True` | `stats=False` |
| read_table_csv() 行为 | `header=0`（读取表头） | `header=None`（无表头） |
| 数据起始行 | 第 2 行 | 第 1 行 |

### 关键函数

```python
def prepare_single_table(schema_graph, table, path, stats=False):
    """
    从 CSV 读取单表数据，生成 HDF 文件。
    
    参数:
      stats: True if Stats, False if IMDB
    
    流程:
      1. read_table_csv(table_obj, csv_seperator=',', stats=stats)
         - stats=True: header=0（跳过表头行）
         - stats=False: header=None（无表头）
      2. 添加 multiplier 列（用于 JOIN 采样）
      3. 处理 NULL 值
      4. 保存到 HDF
    
    注意:
      - 必须正确设置 stats 参数，否则数据行错位
      - 相邻表的 read_table_csv 调用也需传入 stats 参数
    """
```

---

## 日志和监控

### 日志输出

脚本在 `logs/` 目录下生成日志文件，文件名格式: `bayescard_YYYYMMDD-HHMMSS.log`

### 日志级别

| 级别 | 用途 | 例子 |
|------|------|------|
| INFO | 正常进度 | "Loaded BN model: 0_chow-liu_1.pkl" |
| WARNING | 预期的错误 | "Query 5 failed: ..." |
| ERROR | 严重错误 | （通常导致程序中止） |

### 关键日志检查点

#### 训练

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

#### 推理

```
Loading BN ensemble from ...
Loaded BN model: 0_chow-liu_1.pkl
...
Loaded 11 BN models from checkpoints/stats_models
Running inference on N queries from ...
  processed 500 / 5000  (avg latency: 0.0024s)
Results saved to ...
Total time: X.XXs | Avg latency: 0.0024s | Errors: N
```

---

## 性能优化建议

### 1. 模型训练加速

- 降低 `--df_sample_size` (默认 10M)
- 增加 `--max_parents` (学习更复杂的依赖结构)
- 减少 `--sample_size` (结构学习子采样)

### 2. 推理加速

- 使用 `exact-jit` 推理算法（已设置）
- 批量处理查询（避免多次模型加载）
- 使用更小的查询文件进行测试

### 3. 内存优化

- 增加 `--max_table_data` 以减少 HDF 分片数量
- 使用 SSD 存储 HDF 文件
- 清理旧的 `.hdf` 和 `.pkl` 文件

---

## 常见错误详解

### Error: `ValueError: bn_index out of range`

**原因**: `bn_index` 值超过加载的 BN 数量

**根源**: 模型加载顺序不一致导致 `bn_index` 错位

**修复**: 确保调用 `load_ensemble_sorted()` 而非直接 `load_ensemble()`

### Error: `Query parsing failed: NameError`

**原因**: SQL 中的表名或列名未在 schema 中定义

**检查**:
- SQL 是否与基准匹配（不要混用 STATS 和 IMDB SQL）
- 列名是否拼写正确
- 表别名是否在 FROM 子句中定义

### Error: `Estimate is 1.0 for all queries`

**原因**: 查询解析全部失败，使用默认值 1.0

**调试**:
1. 检查日志中的 "failed" 警告数量
2. 手动测试单个查询
3. 检查 schema 是否正确加载
4. 对 JOBLightRanges，确认 SQL 预处理是否执行

---

## 扩展和修改

### 添加新基准

1. 在 `bayescard/Schemas/` 下创建新的 schema 文件
2. 在 `get_schema()` 中添加新的 elif 分支
3. 在 `is_stats_benchmark()` 中决定是否需要表头处理
4. 在 `cmd_train()` 中添加任何必要的数据预处理
5. 在 `cmd_infer()` 中添加任何必要的 SQL 预处理
6. 在 argument parser 中的 `choices` 列表中添加新基准名

### 修改推理算法

```python
# 在 load_ensemble_sorted() 中
bn.infer_algo = "exact-jit"  # 改为其他算法
# 其他选项: "exact", "belief-propagation", "map" 等
```

### 添加自定义谓词处理

对于其他需要 SQL/数据转换的基准，在相应的预处理函数中添加正则表达式和替换逻辑。

---

## 调试建议

### 1. 最小化测试

创建包含 3-5 条简单查询的测试文件进行快速验证。

### 2. 日志分析

```bash
tail -f logs/bayescard_*.log
```

实时监控进度，快速定位错误。

### 3. 单步调试

```python
# 添加到脚本中
import pdb
pdb.set_trace()  # 在关键点暂停
```

### 4. Schema 验证

```python
# 手动验证 schema
schema = get_schema("stats", "Data/Stats/{}.csv")
print(schema.tables)
print(schema.relationships)
```

### 5. 查询解析测试

```python
from DeepDBUtils.evaluation.utils import parse_query

query = parse_query("SELECT COUNT(*) FROM badges", schema)
print(query.table_set)
print(query.column_set)
```
