---
name: factorjoin-usage
description: FactorJoin 方法在本仓库的使用说明：两种工作模式（BN 模式和采样模式）、训练和评估流程、为 STATS-CEB/JOBM/JOBLight 获取子查询基数估计的完整步骤。当用户提到 FactorJoin、子查询基数估计、BN 模式、采样模式时使用。
---

# FactorJoin 使用指南

## 概述

FactorJoin 是一个基于因子分解的连接查询基数估计框架，支持两种工作模式：
1. **BN 模式**：使用贝叶斯网络学习数据分布（适用于 STATS-CEB、JOBLight）
2. **采样模式**：使用 PostgreSQL 采样（适用于 JOBM 等包含复杂谓词的场景）

## 核心概念

### 两种工作模式的区别

| 特性 | BN 模式 | 采样模式 |
|------|---------|----------|
| **适用场景** | 简单数据类型，可离散化 | 复杂谓词（LIKE），环形连接 |
| **训练函数** | `train_one_stats()` | `train_one_imdb()` |
| **Bound_ensemble** | `bns=all_bns` | `ground_truth_factors_no_filter` (无 `bns`) |
| **依赖** | CSV 数据文件 | CSV + PostgreSQL 数据库 |
| **n_dim_dist** | 支持 1 或 2 | 仅支持 1 |
| **评估方式** | 从 BN 查询 | 从 PostgreSQL 采样 |
| **Benchmark** | STATS-CEB, JOBLight | JOBM, 完整 IMDB-JOB |

**代码识别**:
- BN 模式: `Bound_ensemble(table_buckets, schema, n_dim_dist, bns=all_bns, ...)`
- 采样模式: `Bound_ensemble(table_buckets, schema, n_dim_dist, ground_truth_factors_no_filter)`

### Benchmark 数据集特点

| Benchmark | 子查询数 | 工作模式 | 数据库 | 特点 |
|-----------|---------|----------|--------|------|
| **STATS-CEB** | 2471 | BN 模式 | `stats` | Stack Overflow，8 表，简单谓词 |
| **JOBM** | 6424 | 采样模式 | `imdbm` | IMDB 子集（17 表），包含 LIKE、IS NOT NULL |
| **JOBLight** | 451 | BN 模式 | `imdblight` | IMDB 最小子集（6 表），仅简单谓词 |

**数据集层次**:
- IMDB (完整) > JOBM (中等子集) > JOBLight (最小子集)
- JOBLight: 仅保留 6 个核心表
- JOBM: 删除 4 个表 (name, person_info, role_type, aka_name)，删除部分列

## 环境配置

### 文件位置

```
# 以下路径均为项目根目录下的相对路径
├── methods/FactorJoin/              # FactorJoin 源代码
│   ├── run_experiment.py            # 主运行脚本
│   ├── Evaluation/
│   │   ├── training.py              # train_one_stats(), train_one_imdb()
│   │   └── testing.py               # test_on_stats(), test_on_imdb()
│   ├── Join_scheme/bound.py         # Bound_ensemble 核心类
│   ├── Schemas/
│   │   ├── stats/schema.py          # gen_stats_light_schema()
│   │   └── imdb/schema.py           # gen_job_light_imdb_schema(), gen_imdb_schema()
│   └── checkpoints/                 # 模型和采样数据存储
├── methods/SafeBound/Data/
│   ├── Stats/*.csv                  # STATS 数据文件
│   └── IMDB/*.csv                   # IMDB 数据文件
├── benchmark/                       # 小写目录（本地测试用）
│   ├── stats-ceb/subquery/subquery.sql
│   └── jobm/subqueries/subquery.sql
└── Benchmark/workloads/             # 大写目录（标准位置）
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

### PostgreSQL 配置

```bash
# 数据目录
PGDATA=/mnt/sdb1/tlw/pgdata

# psql 路径
/usr/local/pgsql/13.1/bin/psql

# 已有数据库
stats        # STATS-CEB 数据
imdblight    # JOBLight 数据
imdbm        # JOBM 数据
imdb         # 完整 IMDB 数据

# 用户
liwei (owner: imdblight, imdbm)
postgres (owner: stats, imdb)
```

### Python 环境

- **要求**: Python 3.7 (README 要求)
- **实际**: Python 3.12.7 (需要确认兼容性)
- **依赖**: numpy, pandas, pickle (需要安装)

```bash
# 在项目根目录下运行，进入 FactorJoin 目录
cd methods/FactorJoin

# 检查依赖
python -c "import pickle, numpy, pandas; print('OK')"
```

## 使用流程

### 1. STATS-CEB (BN 模式)

#### 步骤 1.1: 训练贝叶斯网络模型

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

**参数说明**:
- `--dataset stats`: STATS 数据集，使用 BN 模式
- `--n_dim_dist 2`: 二维分布，树宽为 2
- `--n_bins 200`: 每个键组分 200 个桶
- `--bucket_method greedy`: 贪婪分桶算法（最优但慢）

**输出**: `checkpoints/model_stats_greedy_200.pkl` (预计训练 20-30 分钟)

#### 步骤 1.2: 评估子查询

```bash
python run_experiment.py --dataset stats \
       --evaluate \
       --model_path checkpoints/model_stats_greedy_200.pkl \
       --query_file_location ../../benchmark/stats-ceb/subquery/subquery.sql \
       --save_folder ../../Benchmark/workloads/STATS-CEB/subquery/result/
```

**输出**: 
- 文件名: `Benchmark/workloads/STATS-CEB/subquery/result/stats_CEB_sub_queries_model_stats_greedy_200.txt`
- 重命名为: `factorjoin.txt`

```bash
cd ../../Benchmark/workloads/STATS-CEB/subquery/result/
mv stats_CEB_sub_queries_model_stats_greedy_200.txt factorjoin.txt
```

**输出格式**: 每行一个浮点数（估计基数），与 `subquery.sql` 逐行对应

### 2. JOBLight (BN 模式)

#### 步骤 2.1: 训练模型

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

**参数说明**:
- `--dataset imdb-light`: JOBLight 子集，使用 BN 模式
- `--bucket_method fixed_start_key`: 快速分桶（推荐用于 IMDB）
- `--get_bin_means`: 使用分桶的均值

**输出**: `checkpoints/model_imdb-light_fixed_start_key_200.pkl`

#### 步骤 2.2: 评估子查询

```bash
python run_experiment.py --dataset imdb-light \
       --evaluate \
       --model_path checkpoints/model_imdb-light_fixed_start_key_200.pkl \
       --query_file_location ../../Benchmark/workloads/JOBLight/subquery/subquery.sql \
       --save_folder ../../Benchmark/workloads/JOBLight/subquery/result/
```

**输出**: 重命名为 `factorjoin.txt`

### 3. JOBM (采样模式)

#### 步骤 3.1: 训练模型并准备采样表

```bash
cd methods/FactorJoin

python run_experiment.py --dataset imdb \
       --generate_models \
       --data_path ../../methods/SafeBound/Data/IMDB/{}.csv \
       --model_path checkpoints/ \
       --n_dim_dist 1 \
       --bucket_method fixed_start_key \
       --db_conn_kwargs "dbname=imdbm user=liwei host=localhost port=5432" \
       --prepare_sample \
       --sampling_percentage 1.0 \
       --sampling_type ss
```

**参数说明**:
- `--dataset imdb`: IMDB 数据集，使用采样模式
- `--n_dim_dist 1`: 独立分布（采样模式仅支持 1）
- `--prepare_sample`: 在 PostgreSQL 中创建采样用临时表
- `--db_conn_kwargs`: PostgreSQL 连接字符串（使用 `imdbm` 数据库）

**输出**: `checkpoints/model_imdb_default.pkl`

**重要**: 此步骤会在 `imdbm` 数据库中创建临时表用于采样

#### 步骤 3.2: 评估子查询

**问题**: JOBM 子查询包含 `LIKE` 和 `IS NOT NULL` 等复杂谓词，需要确认 FactorJoin 是否支持。

**可能的评估方式**:

**方式 A**: 如果支持直接评估
```bash
python run_experiment.py --dataset imdb \
       --evaluate \
       --model_path checkpoints/model_imdb_default.pkl \
       --query_file_location ../../benchmark/jobm/subqueries/subquery.sql \
       --save_folder ../../Benchmark/workloads/JOBM/subquery/result/
```

**方式 B**: 如果需要子计划查询（类似完整 JOB）
- 需要生成 `derived_query_file.pkl`（子计划查询字典）
- 参考 `methods/FactorJoin/checkpoints/derived_query_file.pkl`

**方式 C**: 如果需要预物化采样
```bash
# 先物化采样
python run_experiment.py --dataset imdb \
       --generate_models \
       --materialize_sample \
       --query_file_location ../../benchmark/jobm/subqueries/subquery.sql \
       ... (其他参数同步骤 3.1)

# 再评估
python run_experiment.py --dataset imdb \
       --evaluate \
       --model_path checkpoints/model_imdb_default.pkl \
       --query_sample_location checkpoints/binned_cards_{}/
       --save_folder ../../Benchmark/workloads/JOBM/subquery/result/
```

## 查询文件格式

### STATS-CEB 格式

```sql
SELECT COUNT(*) FROM badges AS badges1,comments AS comments1 WHERE comments1.UserId=badges1.UserId AND badges1.Date<='2014-08-02 12:24:29'::timestamp AND comments1.CreationDate<='2014-09-11 13:42:51'::timestamp AND comments1.CreationDate>='2010-08-01 19:11:47'::timestamp;
```

**特点**:
- 每行一条 SQL，以分号结尾
- 表别名: `table AS table1`
- 日期格式: `'...'::timestamp`
- 谓词: 等值、范围比较

### JOBM 格式

```sql
SELECT COUNT(*) FROM aka_title AS aka_title1,company_name AS company_name1,company_type AS company_type1,keyword AS keyword1,movie_companies AS movie_companies1,movie_info AS movie_info1,movie_keyword AS movie_keyword1 WHERE aka_title1.movie_id=movie_companies1.movie_id AND company_name1.id=movie_companies1.company_id AND company_type1.id=movie_companies1.company_type_id AND keyword1.id=movie_keyword1.keyword_id AND movie_companies1.movie_id=movie_info1.movie_id AND movie_info1.movie_id=movie_keyword1.movie_id AND company_name1.country_code = '[us]' AND company_name1.name = 'YouTube' AND movie_companies1.note LIKE '%(200%)%' AND movie_companies1.note LIKE '%(worldwide)%' AND movie_info1.info LIKE 'USA:% 200%' AND movie_info1.note LIKE '%internet%';
```

**特点**:
- 包含 `LIKE` 谓词（复杂模式匹配）
- 包含 `IS NOT NULL`
- 字符串相等匹配
- 需要采样模式支持

### JOBLight 格式

```sql
SELECT COUNT(*) FROM cast_info AS cast_info1,movie_companies AS movie_companies1 WHERE cast_info1.movie_id=movie_companies1.movie_id AND cast_info1.role_id=1;
```

**特点**:
- 简单等值谓词
- 整数比较
- 表更少、查询更简单

## 代码解析

### 核心类: Bound_ensemble

```python
# 位置: methods/FactorJoin/Join_scheme/bound.py

class Bound_ensemble:
    def __init__(self, table_buckets, schema, n_dim_dist=1, 
                 ground_truth_factors_no_filter=None, 
                 SPERCENTAGE=None, query_sample_location=None, 
                 bns=None, null_value=None, db_conn_kwargs=None):
        """
        :param bns: 贝叶斯网络字典（BN 模式）。None 表示采样模式
        :param ground_truth_factors_no_filter: 无过滤器的真实因子（采样模式）
        :param query_sample_location: 预物化采样位置（采样模式）
        """
        self.bns = bns
        # ...
    
    def parse_query_simple(self, query):
        """解析查询"""
        if self.bns is None:
            # 采样模式：简单解析（不解析谓词）
            tables_all, join_cond, join_keys = parse_query_all_join(query)
            table_filters = dict()
            return tables_all, table_filters, join_cond, join_keys
        else:
            # BN 模式：完整解析（包括谓词）
            # ... 解析 WHERE 子句中的谓词
```

### 训练函数对比

```python
# BN 模式 (training.py)
def train_one_stats(dataset, data_path, model_folder, n_dim_dist=2, ...):
    # 1. 处理数据
    data, null_values, key_attrs, table_buckets, ... = process_stats_data(...)
    
    # 2. 为每个表训练贝叶斯网络
    all_bns = dict()
    for table in schema.tables:
        bn = Bayescard_BN(...)
        bn.build_from_data(data[t_name])
        all_bns[t_name] = bn
    
    # 3. 创建 Bound_ensemble（带 bns）
    be = Bound_ensemble(table_buckets, schema, n_dim_dist, 
                        bns=all_bns, null_value=null_values)
    
    # 4. 保存模型
    pickle.dump(be, open(model_path, 'wb'))

# 采样模式 (training.py)
def train_one_imdb(data_path, model_folder, n_dim_dist=1, ...):
    # 1. 处理数据（生成分桶信息）
    schema, table_buckets, ground_truth_factors_no_filter, ... = process_imdb_data(...)
    
    # 2. 创建 Bound_ensemble（无 bns，有 ground_truth_factors_no_filter）
    be = Bound_ensemble(table_buckets, schema, n_dim_dist, 
                        ground_truth_factors_no_filter)
    
    # 3. 可选：在 PostgreSQL 中创建采样表
    if prepare_sample:
        create_binned_cols(db_conn_kwargs, bins, ...)
    
    # 4. 保存模型
    pickle.dump(be, open(model_path, 'wb'))
```

### 评估函数对比

```python
# BN 模式评估 (testing.py)
def test_on_stats(model_path, query_file, save_res=None):
    # 1. 加载模型
    bound_ensemble = pickle.load(open(model_path, "rb"))
    
    # 2. 初始化每个 BN 的推断方法
    for table in bound_ensemble.bns:
        bn = bound_ensemble.bns[table]
        bn.init_inference_method()
    
    # 3. 逐条查询估计
    queries = open(query_file, "r").readlines()
    pred = []
    for query_str in queries:
        query = query_str.split("||")[0][:-1]  # 支持 SQL 或 SQL||true_card
        res = bound_ensemble.get_cardinality_bound_one(query)
        pred.append(res)
    
    # 4. 保存结果
    with open(save_res, "w") as f:
        for p in pred:
            f.write(str(p) + "\n")

# 采样模式评估 (testing.py)
def test_on_imdb(model_path, derived_query_file=None, 
                 query_sample_location=None, save_res=None):
    # 1. 加载模型
    bound_ensemble = pickle.load(open(model_path, "rb"))
    
    # 2. 设置采样参数
    if query_sample_location:
        bound_ensemble.query_sample_location = query_sample_location
    
    # 3. 加载查询和子计划
    all_queries, all_sub_plan_queries_str = pickle.load(open(derived_query_file, "rb"))
    
    # 4. 逐条查询估计（使用采样）
    res = dict()
    for q_name in all_queries:
        temp = bound_ensemble.get_cardinality_bound_all(...)
        res[q_name] = temp
    
    # 5. 保存结果
    # ...
```

## 常见问题

### Q1: FactorJoin 是否支持 LIKE 谓词？

**观察**: `bound.py` 第 54 行，采样模式下 `parse_query_simple()` 不解析谓词：
```python
if self.bns is None:
    # 采样模式：只解析 join 条件，谓词由 PostgreSQL 采样处理
    tables_all, join_cond, join_keys = parse_query_all_join(query)
```

**结论**: 采样模式通过 PostgreSQL 处理复杂谓词，理论上支持 LIKE。但需要验证。

### Q2: 如何选择 bucket_method？

| 方法 | 速度 | 精度 | 推荐场景 |
|------|------|------|---------|
| greedy | 慢 | 最优 | STATS（小数据集） |
| fixed_start_key | 快 | 接近最优 | IMDB（大数据集） |
| sub_optimal | 中 | 中等 | 折衷方案 |
| naive | 最快 | 最差 | 仅用于消融实验 |

### Q3: 为什么 IMDB 采样模式只支持 n_dim_dist=1？

**原因**: IMDB 包含大量字符串列，无法捕捉两个字符串属性间的相关性（无法离散化用于 LIKE）。

**解决**: README 提到 "optimization branch" 在探索 n_dim_dist=2 的新算法。

### Q4: 查询格式 `SQL` 还是 `SQL||true_card`？

**两种格式都支持**:
```python
query = query_str.split("||")[0][:-1]  # 自动分割，取第一部分
```

项目中的格式: `SQL;` （仅 SQL，无真实基数）

### Q5: JOBM 评估可能遇到的问题

**潜在问题**:
1. **复杂谓词**: `LIKE`, `IS NOT NULL` 是否完全支持
2. **查询格式**: 是否需要转换为特定格式
3. **子计划**: 是否需要 `derived_query_file.pkl`

**建议**: 先尝试直接评估，如遇错误再调整策略。

## 验证结果

### 数据文件 ✓
- STATS: 8 个 CSV，总计 ~1M 行
- IMDB: 20+ 个 CSV，cast_info 1.4GB

### 数据库 ✓
- stats: 8 表（badges, comments, postHistory, postLinks, posts, tags, users, votes）
- imdblight: 6 表（cast_info, movie_companies, movie_info, movie_info_idx, movie_keyword, title）
- imdbm: 17 表（完整 IMDB 子集）

### 子查询文件 ✓
- STATS-CEB: 2471 行，简单谓词
- JOBM: 6424 行，包含 LIKE
- JOBLight: 451 行，简单谓词

### 代码结构 ✓
- 所有核心文件存在
- Schema 定义完整

## 推荐执行顺序

1. **STATS-CEB** (最简单，BN 模式)
   - 训练快 (~20min)
   - 无复杂依赖
   - 可验证流程

2. **JOBLight** (中等难度，BN 模式)
   - IMDB 子集
   - 测试 imdb-light dataset

3. **JOBM** (最复杂，采样模式)
   - 需要 PostgreSQL
   - 包含复杂谓词
   - 可能需要调试

## 参考资料

- FactorJoin 论文: SIGMOD 2023
- 原始 README: `methods/FactorJoin/README.md`
- 代码仓库: https://github.com/Nathaniel-Han/End-to-End-CardEst-Benchmark
