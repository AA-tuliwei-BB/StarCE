---
name: fspn-usage
description: FSPN/FLAT 方法说明：FSPN 概率图模型（Factorized Sum-Product Network）与 FLAT 基数估计系统的关系、架构原理、节点类型、学习算法、推理模式。此仓库为 FSPN 模型实现，非完整 FLAT 系统。当用户提到 FSPN、FLAT、Factorized SPN、多变量直方图叶节点、RDC 依赖检测、Factorize 节点时使用。
---

# FSPN (FLAT) 方法调研总结

## 概述

### FSPN 与 FLAT 的关系

> **FSPN 是模型，FLAT 是系统。** FSPN 是 FLAT 的核心引擎。

| 名称 | 全称 | 性质 | 论文 |
|------|------|------|------|
| **FSPN** | **F**actorize-**S**plit-Sum-**P**roduct **N**etwork | **概率图模型** | *FSPN: A New Class of Probabilistic Graphical Model* (Wu et al., arXiv 2020) |
| **FLAT** | **F**ast, **L**ightweight and **A**ccurate method for cardinality es**T**imation | **基数估计系统** | *FLAT: Fast, Lightweight and Accurate Method for Cardinality Estimation* (Zhu et al., VLDB 2021) |

FLAT 由三大模块组成：
1. **离线模型构建** — 使用 FSPN 递归分解数据，学习联合分布
2. **在线概率计算** — 在 FSPN 树上以近线性时间递归计算查询概率
3. **增量更新** — 数据变化时增量调整模型

**此仓库是 FSPN**（模型实现），不是完整的 FLAT 系统。它提供通用的概率图模型训练和推理能力，可用于基数估计但本身不含数据库连接、SQL 解析、查询优化器集成等 FLAT 系统组件。

FSPN 扩展了标准 SPN (Sum-Product Network)，引入 **Factorize 节点**来建模条件独立关系，弥补标准 SPN 无法表达的依赖性。代码基于 [SPFlow](https://github.com/SPFlow/SPFlow) 改编。

## 四种节点类型

SPN 是一种有向无环图（DAG），通过节点树表示联合概率分布。FSPN 引入四种节点类型：

### 1. Sum 节点（行分裂 / 聚类）
- **语义**：加权混合模型。将数据按行聚类，每组拟合一个子模型。
- **参数**：`weights`（权重向量，和为 1）、`cluster_centers`（聚类中心，可选）
- **概率计算**：P = Σ w_i × P_i（子节点概率的加权和）
- **触发条件**：数据按 row 聚类（KMeans / GMM / RDC）
- **对应操作**：`Operation.SPLIT_ROWS`、`Operation.SPLIT_ROWS_CONDITION`

### 2. Product 节点（列分裂 / 独立子集）
- **语义**：独立性假设。将变量拆分为互不依赖的组。
- **概率计算**：P = ∏ P_i（子节点概率的乘积）
- **触发条件**：RDC 检测到独立成分（connected components > 1）
- **对应操作**：`Operation.SPLIT_COLUMNS`、`Operation.NAIVE_FACTORIZATION`

### 3. Factorize 节点（FSPN 的核心创新）
- **语义**：条件分布分解。P(A, B) = P(A) × P(B|A)，其中 A 是弱连接变量（独立），B 是强连接变量（依赖 → 条件变量）
- **结构**：
  - **左子节点** (left_child)：拟合弱连接变量的边缘分布 P(A)
  - **右子节点** (right_child)：拟合强连接变量在条件上的条件分布 P(B|A)
- **概率计算**：P = P_left(condition) × P_right(scope | condition)，通过 `eval_fact_node()` 递归求值
- **触发条件**：RDC 检测到强连接组（rdc > 0.75）和非强连接组共存
- **对应操作**：`Operation.FACTORIZE`

### 4. Leaf 节点（概率分布）
- 叶节点直接对某些变量范围拟合具体的概率分布
- 支持的类型：
  - **Histogram**：一维直方图 (`Structure/leaves/fspn_leaves/Histograms.py`)
  - **Multi_histogram**：多维直方图，用于强相关列 (`Multi_Histograms.py`)
  - **PiecewiseLinear**：分段线性，用于连续值 (`leaves/piecewise/`)
  - **CLTree**：Chow-Liu Tree，用于离散依赖 (`leaves/cltree/`)
  - **Binary / Multi-binary**：二值 / 多二值变量 (`leaves/binary/`)
- 叶节点支持两种查询模式：
  - **点查询** (`infer_point_query`)：离散/精确值查询
  - **范围查询** (`infer_range_query`)：连续范围查询（基数估计的核心）

## 学习算法

### RDC (Randomized Dependence Coefficient) 依赖检测
- 用于判断变量间是否独立
- `Learning/splitting/RDC.py`
- 关键参数：
  - `threshold`（默认 0.3）：RDC 值低于此视为独立
  - `rdc_strong_connection_threshold`（默认 0.75）：RDC 值高于此视为强依赖

### 贪婪递归分区（`structureLearning.py`）

学习算法的核心是 `get_next_operation()`，每次选择优先级最高的操作：

| 优先级 | 操作 | 说明 |
|--------|------|------|
| 1 | `REMOVE_UNINFORMATIVE_FEATURES` | 移除方差为零的列 |
| 2 | `REMOVE_CONDITION` | 移除与 scope 独立的条件变量 |
| 3 | `SPLIT_COLUMNS` | 按独立成分拆分为 Product 节点 |
| 4 | `FACTORIZE` | 分解为 Factorize 节点（强依赖→条件变量） |
| 5 | `SPLIT_ROWS` / `SPLIT_ROWS_CONDITION` | 聚类行产生 Sum 节点 |
| 6 | `CREATE_LEAF` | 停止分裂，拟合叶子分布 |
| 7 | `NAIVE_FACTORIZATION` | 最低优先：假设所有剩余变量独立 |

任务队列 (`tasks` deque) 中每个任务包含：
```python
(local_data, parent, children_pos, scope, condition, cond_fanout_data,
 rect_range, no_clusters, no_independencies, no_condition, is_strong_connected, right_most_branch)
```

### 行分裂策略

由 `get_splitting_functions()` 选择：
- **列分裂**（cols）: `rdc`（RDC 独立性测试）或 `poisson`（泊松稳定性测试）
- **行分裂**（rows）: `rdc`、`kmeans`、`tsne`、`gmm`、`grid_naive`、`grid`
- 默认组合: `cols="rdc"`, `rows="grid_naive"`

## 推理（概率查询）

### 模型类 (`Structure/model.py` 中的 `FSPN` 类)

核心推理方法：

1. **`probability(query, ...)`**：计算查询范围的概率（基数估计核心）
   - `query`: 一个 tuple `(left_bounds, right_bounds)`，形状 `(n, k)`，表示 k 个属性的 n 条范围查询
   - 递归遍历 SPN 树，按 Factorize 节点特殊处理

2. **`eval_fact_node(query, node, ...)`**：评估 Factorize 节点
   - 计算 scope 的叶节点概率（在右分支的 leaves 上）
   - 递归计算 condition 的概率（在左分支上）
   - 组合：`prob = sum(condition_prob × scope_prob)`

3. **`likelihood(data, ...)`**：计算数据的似然（可选的 log 空间）
   - 自底向上计算，类似 `probability` 但对精确值

4. **`store_factorize_as_dict()`**：预处理 Factorize 节点
   - 将右分支 Product 节点合并为 Merge_leaves
   - 预计算 `leaves_condition`、`leaves`、`leaves_range`
   - 这是推理前的必要步骤

### 推理模块

- **`Inference/inference.py`**：通用推理，提供 `likelihood()` / `log_likelihood()` 自底向上评估
- **`Inference/sampling.py`**：层次化抽样（自底向上计算似然 + 自顶向下采样）
- **`Inference/expectation.py`**：计算 E[1_conditions × X]（批量/单条）
- **`Inference/condition.py`**：将 SPN 条件化到证据上，生成新的 SPN
- **`Inference/query_inference.py`**：另一种查询推理（用于 Factorize 节点批量处理）

## 目录结构

```
methods/FSPN/
├── Algorithms/                    # 算法辅助工具
│   ├── convert_conditions.py      # 范围条件到 C++ 参数转换
│   ├── expectation.py             # 期望计算辅助
│   ├── ranges.py                  # 范围操作
│   └── transform_structure.py     # 结构转换
├── Evaluation/                    # 评估和测试
│   ├── test_training.py           # 训练测试入口（toy datasets + binary datasets）
│   └── toy_dataset.py             # 合成数据生成器
├── Inference/                     # 推理模块
│   ├── inference.py               # 自底向上似然评估
│   ├── query_inference.py         # 查询推理（Factorize 批量处理）
│   ├── sampling.py                # 层次化抽样
│   ├── expectation.py             # 期望计算
│   ├── marginalization.py         # 边缘化
│   ├── mpe.py                     # 最可能解释
│   ├── condition.py               # 条件化
│   ├── em.py                      # EM 算法
│   ├── gradient.py                # 梯度
│   └── stats/                     # 统计计算
├── Learning/                      # 结构学习
│   ├── structureLearning.py       # 核心：递归分区算法
│   ├── structureLearning_binary.py# 二值数据版本
│   ├── learningWrapper.py         # learn_FSPN() 入口
│   ├── statistics.py              # 结构统计
│   ├── transformStructure.py      # Copy/Prune 操作
│   ├── update.py / update2.py     # 参数更新
│   ├── validity.py                # SPN 有效性验证
│   ├── utils.py                   # 工具函数
│   └── splitting/                 # 分裂策略
│       ├── RDC.py                 # RDC 独立性测试
│       ├── Clustering.py          # KMeans/GMM/TSNE 聚类
│       ├── Condition_Clustering.py# 条件聚类（Grid/Grid_naive/KMeans）
│       ├── Condition_Clustering.py# 条件聚类
│       ├── Condition.py           # 条件处理
│       ├── Grid_clustering.py     # 网格聚类
│       ├── Cover_set_clustering.py# 覆盖集聚类
│       ├── Rect_approaximate.py   # 矩形近似
│       ├── PoissonStabilityTest.py# 泊松稳定性测试
│       └── Base.py                # 基类
├── Structure/                     # 结构定义
│   ├── model.py                   # FSPN 类 / build_ds_context / 核心推理
│   ├── nodes.py                   # Sum/Product/Factorize/Leaf 节点定义
│   ├── StatisticalTypes.py        # MetaType (REAL/DISCRETE/BINARY)
│   └── leaves/                    # 叶节点实现
│       ├── fspn_leaves/           # Histogram / Multi_histogram / Merge_leaves
│       ├── piecewise/             # PiecewiseLinear 连续分布
│       ├── cltree/                # Chow-Liu Tree
│       ├── binary/                # 二值变量
│       ├── range.py               # 范围叶节点
│       └── get_breaks.py          # 直方图分界点
└── environment.yml                # Conda 环境 (fspn, Python 3.7, PyTorch 1.3.1)
```

## 模型训练和使用

### 标准训练流程（参考 `test_training.py`）

```python
import numpy as np
import sys
sys.path.append('methods/FSPN')  # 假设当前工作目录为项目根目录

from Learning.learningWrapper import learn_FSPN
from Structure.model import FSPN, build_ds_context
from Structure.nodes import Context
from Structure.StatisticalTypes import MetaType

# 1. 准备数据：numpy 数组 (n_samples, n_features)
data = np.loadtxt("data.csv", delimiter=",")

# 2. 创建 Context（指定每列的数据类型）
meta_types = [MetaType.REAL, MetaType.DISCRETE, ...]
ds_context = build_ds_context(column_names, meta_types,
                               null_values, table_meta_data, data)

# 3. 训练模型
fspn = learn_FSPN(data, ds_context,
                  cols="rdc", rows="grid_naive",
                  threshold=0.3,
                  rdc_sample_size=50000,
                  rdc_strong_connection_threshold=0.75,
                  multivariate_leaf=True)

# 4. 包装为 FSPN 对象
model = FSPN()
model.model = fspn
model.ds_context = ds_context
model.store_factorize_as_dict()  # 必需！预处理 Factorize 节点
```

### 基数估计（概率查询）

```python
# 查询：对 k 个属性的 n 条范围查询
# query = (left_bounds, right_bounds)，形状 (n, k)
# query_attr = [0, 1, 2, ...] 查询的属性列表

probability = model.probability(query, query_attr=query_attr)
# probability 形状: (n,)
# cardinality = probability * num_rows
```

查询格式：
- **精确值查询**：left = right = value（在 Histogram 中作为点查询处理）
- **范围查询**：left < right，概率 = CDF(right) - CDF(left)
- **混合查询**：部分列精确，部分列范围

## 与其他基数估计方法的关系

作为项目的对照方法，FSPN 可与以下方法比较：

| 方法 | 类型 | 本仓库位置 |
|------|------|-----------|
| **FactorJoin** | 贝叶斯网络+因子分解 | `methods/FactorJoin/` |
| **SafeBound** | 上界估计 | `methods/SafeBound/` |
| **StarCE** | 度序列估计 | DuckDB 内嵌 |
| **FLAT (FSPN)** | FSPN 概率图模型驱动的基数估计 | `methods/FSPN/` (新增，仅模型部分) |

## 关键依赖

- **Python 3.7** (环境文件指定，可能与项目 TestEnv 的 Python 3.10 冲突)
- **PyTorch 1.3.1** (CUDA 10.0)
- **pgmpy 0.1.10** (贝叶斯网络)
- **pomegranate 0.11.1** (概率模型)
- **SPFlow 0.0.34** (SPN 基础框架)
- 其他：numpy, scipy, scikit-learn, networkx, statsmodels

## 已发现的问题和注意事项

1. **Python 版本冲突**：environment.yml 要求 Python 3.7，但项目 TestEnv 使用 Python 3.10。需要考虑：
   - 创建独立的 conda 环境
   - 或将代码移植到 Python 3.10

2. **PyTorch 版本老旧**：要求 PyTorch 1.3.1 (CUDA 10.0)，与项目其他方法的 PyTorch 2.10.0 不兼容

3. **原环境路径**：environment.yml 中 prefix 指向 `/home/ziniu.wzn/anaconda3/envs/deepdb`，是原作者机器的路径

4. **Linux 兼容性**：README 指出"some packages might not support Linux"，需验证

5. **Multi_histogram 维度限制**：`infer_range_query()` 中硬编码支持 d=2..7 维，超过 7 维报错

6. **Factorize 节点推理复杂度**：`eval_fact_node` 中使用 `get_overlap()` 计算条件范围的笛卡尔积，可能在大属性集上产生性能问题

7. **代码未做适配**：当前是原始克隆，尚未适配本项目的 workload 格式和评估流程
