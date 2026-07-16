---
name: fspn-usage
description: FSPN/FLAT method description: the relationship between the FSPN probabilistic graphical model (Factorized Sum-Product Network) and the FLAT cardinality estimation system, architectural principles, node types, learning algorithms, and inference modes. This repository is the FSPN model implementation, not the full FLAT system. Use when the user mentions FSPN, FLAT, Factorized SPN, multivariate histogram leaf nodes, RDC dependency detection, Factorize nodes.
---

# FSPN (FLAT) Method Research Summary

## Overview

### Relationship Between FSPN and FLAT

> **FSPN is the model, FLAT is the system.** FSPN is the core engine of FLAT.

| Name | Full Name | Nature | Paper |
|------|------|------|------|
| **FSPN** | **F**actorize-**S**plit-Sum-**P**roduct **N**etwork | **Probabilistic graphical model** | *FSPN: A New Class of Probabilistic Graphical Model* (Wu et al., arXiv 2020) |
| **FLAT** | **F**ast, **L**ightweight and **A**ccurate method for cardinality es**T**imation | **Cardinality estimation system** | *FLAT: Fast, Lightweight and Accurate Method for Cardinality Estimation* (Zhu et al., VLDB 2021) |

FLAT consists of three major modules:
1. **Offline model construction** — Uses FSPN to recursively decompose data and learn the joint distribution
2. **Online probability computation** — Recursively computes query probabilities on the FSPN tree in near-linear time
3. **Incremental updates** — Incrementally adjusts the model when data changes

**This repository is FSPN** (the model implementation), not the complete FLAT system. It provides general probabilistic graphical model training and inference capabilities, usable for cardinality estimation but does not include FLAT system components such as database connections, SQL parsing, or query optimizer integration.

FSPN extends standard SPN (Sum-Product Network) by introducing **Factorize nodes** to model conditional independence relationships, compensating for dependencies that standard SPNs cannot express. The code is adapted from [SPFlow](https://github.com/SPFlow/SPFlow).

## Four Node Types

An SPN is a directed acyclic graph (DAG) that represents a joint probability distribution through a tree of nodes. FSPN introduces four node types:

### 1. Sum Node (Row Splitting / Clustering)
- **Semantics**: Weighted mixture model. Clusters data by rows, fitting a sub-model to each group.
- **Parameters**: `weights` (weight vector, sum to 1), `cluster_centers` (cluster centers, optional)
- **Probability computation**: P = Σ w_i × P_i (weighted sum of child node probabilities)
- **Trigger condition**: Data clustered by rows (KMeans / GMM / RDC)
- **Corresponding operations**: `Operation.SPLIT_ROWS`, `Operation.SPLIT_ROWS_CONDITION`

### 2. Product Node (Column Splitting / Independent Subsets)
- **Semantics**: Independence assumption. Splits variables into mutually independent groups.
- **Probability computation**: P = ∏ P_i (product of child node probabilities)
- **Trigger condition**: RDC detects independent components (connected components > 1)
- **Corresponding operations**: `Operation.SPLIT_COLUMNS`, `Operation.NAIVE_FACTORIZATION`

### 3. Factorize Node (Core FSPN Innovation)
- **Semantics**: Conditional distribution decomposition. P(A, B) = P(A) × P(B|A), where A represents weakly connected variables (independent), and B represents strongly connected variables (dependent → conditioned variables)
- **Structure**:
  - **Left child** (left_child): fits the marginal distribution P(A) of weakly connected variables
  - **Right child** (right_child): fits the conditional distribution P(B|A) of strongly connected variables given the conditioning variables
- **Probability computation**: P = P_left(condition) × P_right(scope | condition), evaluated recursively via `eval_fact_node()`
- **Trigger condition**: RDC detects coexistence of strongly connected groups (rdc > 0.75) and non-strongly connected groups
- **Corresponding operation**: `Operation.FACTORIZE`

### 4. Leaf Node (Probability Distribution)
- Leaf nodes directly fit specific probability distributions over certain variable ranges
- Supported types:
  - **Histogram**: 1D histogram (`Structure/leaves/fspn_leaves/Histograms.py`)
  - **Multi_histogram**: Multi-dimensional histogram, for strongly correlated columns (`Multi_Histograms.py`)
  - **PiecewiseLinear**: Piecewise linear, for continuous values (`leaves/piecewise/`)
  - **CLTree**: Chow-Liu Tree, for discrete dependencies (`leaves/cltree/`)
  - **Binary / Multi-binary**: Binary / multi-binary variables (`leaves/binary/`)
- Leaf nodes support two query modes:
  - **Point query** (`infer_point_query`): discrete / exact value query
  - **Range query** (`infer_range_query`): continuous range query (core of cardinality estimation)

## Learning Algorithm

### RDC (Randomized Dependence Coefficient) Dependency Detection
- Used to determine whether variables are independent
- `Learning/splitting/RDC.py`
- Key parameters:
  - `threshold` (default 0.3): RDC values below this are treated as independent
  - `rdc_strong_connection_threshold` (default 0.75): RDC values above this are treated as strongly dependent

### Greedy Recursive Partitioning (`structureLearning.py`)

The core of the learning algorithm is `get_next_operation()`, which selects the highest-priority operation at each step:

| Priority | Operation | Description |
|--------|------|------|
| 1 | `REMOVE_UNINFORMATIVE_FEATURES` | Remove columns with zero variance |
| 2 | `REMOVE_CONDITION` | Remove condition variables independent of scope |
| 3 | `SPLIT_COLUMNS` | Split into Product node by independent components |
| 4 | `FACTORIZE` | Decompose into Factorize node (strong dependencies → conditioned variables) |
| 5 | `SPLIT_ROWS` / `SPLIT_ROWS_CONDITION` | Cluster rows to produce Sum node |
| 6 | `CREATE_LEAF` | Stop splitting, fit a leaf distribution |
| 7 | `NAIVE_FACTORIZATION` | Lowest priority: assume all remaining variables are independent |

Each task in the task queue (`tasks` deque) contains:
```python
(local_data, parent, children_pos, scope, condition, cond_fanout_data,
 rect_range, no_clusters, no_independencies, no_condition, is_strong_connected, right_most_branch)
```

### Row Splitting Strategies

Selected by `get_splitting_functions()`:
- **Column splitting** (cols): `rdc` (RDC independence test) or `poisson` (Poisson stability test)
- **Row splitting** (rows): `rdc`, `kmeans`, `tsne`, `gmm`, `grid_naive`, `grid`
- Default combination: `cols="rdc"`, `rows="grid_naive"`

## Inference (Probability Query)

### Model Class (`FSPN` class in `Structure/model.py`)

Core inference methods:

1. **`probability(query, ...)`**: Computes the probability of a query range (core of cardinality estimation)
   - `query`: a tuple `(left_bounds, right_bounds)` of shape `(n, k)`, representing n range queries over k attributes
   - Recursively traverses the SPN tree, with special handling for Factorize nodes

2. **`eval_fact_node(query, node, ...)`**: Evaluates Factorize nodes
   - Computes leaf node probabilities for the scope (on the right branch's leaves)
   - Recursively computes the probability of the condition (on the left branch)
   - Combination: `prob = sum(condition_prob × scope_prob)`

3. **`likelihood(data, ...)`**: Computes the likelihood of data (optional log space)
   - Bottom-up computation, similar to `probability` but for exact values

4. **`store_factorize_as_dict()`**: Preprocesses Factorize nodes
   - Merges right-branch Product nodes into Merge_leaves
   - Precomputes `leaves_condition`, `leaves`, `leaves_range`
   - This is a necessary step before inference

### Inference Modules

- **`Inference/inference.py`**: General inference, provides `likelihood()` / `log_likelihood()` bottom-up evaluation
- **`Inference/sampling.py`**: Hierarchical sampling (bottom-up likelihood computation + top-down sampling)
- **`Inference/expectation.py`**: Computes E[1_conditions × X] (batch/single)
- **`Inference/condition.py`**: Conditions the SPN on evidence, generating a new SPN
- **`Inference/query_inference.py`**: Alternative query inference (for batch processing of Factorize nodes)

## Directory Structure

```
methods/FSPN/
├── Algorithms/                    # Algorithm utilities
│   ├── convert_conditions.py      # Range conditions to C++ parameter conversion
│   ├── expectation.py             # Expectation computation helper
│   ├── ranges.py                  # Range operations
│   └── transform_structure.py     # Structure transformation
├── Evaluation/                    # Evaluation and testing
│   ├── test_training.py           # Training test entry (toy datasets + binary datasets)
│   └── toy_dataset.py             # Synthetic data generator
├── Inference/                     # Inference modules
│   ├── inference.py               # Bottom-up likelihood evaluation
│   ├── query_inference.py         # Query inference (Factorize batch processing)
│   ├── sampling.py                # Hierarchical sampling
│   ├── expectation.py             # Expectation computation
│   ├── marginalization.py         # Marginalization
│   ├── mpe.py                     # Most probable explanation
│   ├── condition.py               # Conditioning
│   ├── em.py                      # EM algorithm
│   ├── gradient.py                # Gradient
│   └── stats/                     # Statistical computation
├── Learning/                      # Structure learning
│   ├── structureLearning.py       # Core: recursive partitioning algorithm
│   ├── structureLearning_binary.py# Binary data version
│   ├── learningWrapper.py         # learn_FSPN() entry point
│   ├── statistics.py              # Structure statistics
│   ├── transformStructure.py      # Copy/Prune operations
│   ├── update.py / update2.py     # Parameter updates
│   ├── validity.py                # SPN validity verification
│   ├── utils.py                   # Utility functions
│   └── splitting/                 # Splitting strategies
│       ├── RDC.py                 # RDC independence test
│       ├── Clustering.py          # KMeans/GMM/TSNE clustering
│       ├── Condition_Clustering.py# Conditional clustering (Grid/Grid_naive/KMeans)
│       ├── Condition_Clustering.py# Conditional clustering
│       ├── Condition.py           # Condition processing
│       ├── Grid_clustering.py     # Grid clustering
│       ├── Cover_set_clustering.py# Cover set clustering
│       ├── Rect_approaximate.py   # Rectangle approximation
│       ├── PoissonStabilityTest.py# Poisson stability test
│       └── Base.py                # Base class
├── Structure/                     # Structure definitions
│   ├── model.py                   # FSPN class / build_ds_context / core inference
│   ├── nodes.py                   # Sum/Product/Factorize/Leaf node definitions
│   ├── StatisticalTypes.py        # MetaType (REAL/DISCRETE/BINARY)
│   └── leaves/                    # Leaf node implementations
│       ├── fspn_leaves/           # Histogram / Multi_histogram / Merge_leaves
│       ├── piecewise/             # PiecewiseLinear continuous distribution
│       ├── cltree/                # Chow-Liu Tree
│       ├── binary/                # Binary variables
│       ├── range.py               # Range leaf node
│       └── get_breaks.py          # Histogram break points
└── environment.yml                # Conda environment (fspn, Python 3.7, PyTorch 1.3.1)
```

## Model Training and Usage

### Standard Training Pipeline (reference `test_training.py`)

```python
import numpy as np
import sys
sys.path.append('methods/FSPN')  # Assuming current working directory is project root

from Learning.learningWrapper import learn_FSPN
from Structure.model import FSPN, build_ds_context
from Structure.nodes import Context
from Structure.StatisticalTypes import MetaType

# 1. Prepare data: numpy array (n_samples, n_features)
data = np.loadtxt("data.csv", delimiter=",")

# 2. Create Context (specify data type for each column)
meta_types = [MetaType.REAL, MetaType.DISCRETE, ...]
ds_context = build_ds_context(column_names, meta_types,
                               null_values, table_meta_data, data)

# 3. Train model
fspn = learn_FSPN(data, ds_context,
                  cols="rdc", rows="grid_naive",
                  threshold=0.3,
                  rdc_sample_size=50000,
                  rdc_strong_connection_threshold=0.75,
                  multivariate_leaf=True)

# 4. Wrap as FSPN object
model = FSPN()
model.model = fspn
model.ds_context = ds_context
model.store_factorize_as_dict()  # Required! Preprocess Factorize nodes
```

### Cardinality Estimation (Probability Queries)

```python
# Query: n range queries over k attributes
# query = (left_bounds, right_bounds), shape (n, k)
# query_attr = [0, 1, 2, ...]  the list of queried attributes

probability = model.probability(query, query_attr=query_attr)
# probability shape: (n,)
# cardinality = probability * num_rows
```

Query format:
- **Exact value query**: left = right = value (handled as point query in Histogram)
- **Range query**: left < right, probability = CDF(right) - CDF(left)
- **Mixed query**: some columns exact, some columns range

## Relationship to Other Cardinality Estimation Methods

As a baseline method in this project, FSPN can be compared with the following:

| Method | Type | Location in this repo |
|------|------|-----------|
| **FactorJoin** | Bayesian network + factorization | `methods/FactorJoin/` |
| **SafeBound** | Upper bound estimation | `methods/SafeBound/` |
| **StarCE** | Degree sequence estimation | Embedded in DuckDB |
| **FLAT (FSPN)** | FSPN probabilistic graphical model-driven cardinality estimation | `methods/FSPN/` (new, model only) |

## Key Dependencies

- **Python 3.7** (specified in environment file, may conflict with project TestEnv's Python 3.10)
- **PyTorch 1.3.1** (CUDA 10.0)
- **pgmpy 0.1.10** (Bayesian network)
- **pomegranate 0.11.1** (Probabilistic models)
- **SPFlow 0.0.34** (SPN base framework)
- Others: numpy, scipy, scikit-learn, networkx, statsmodels

## Known Issues and Caveats

1. **Python version conflict**: environment.yml requires Python 3.7, but the project TestEnv uses Python 3.10. Options:
   - Create a separate conda environment
   - Or port the code to Python 3.10

2. **Outdated PyTorch**: Requires PyTorch 1.3.1 (CUDA 10.0), incompatible with the project's other methods using PyTorch 2.10.0

3. **Original environment path**: The prefix in environment.yml points to `/home/ziniu.wzn/anaconda3/envs/deepdb`, which is the original author's machine path

4. **Linux compatibility**: README mentions "some packages might not support Linux", needs verification

5. **Multi_histogram dimension limit**: `infer_range_query()` hardcodes support for d=2..7 dimensions, errors out beyond 7 dimensions

6. **Factorize node inference complexity**: `eval_fact_node` uses `get_overlap()` to compute the Cartesian product of condition ranges, which may cause performance issues on large attribute sets

7. **Code not yet adapted**: Currently the original clone, not yet adapted to this project's workload format and evaluation pipeline
