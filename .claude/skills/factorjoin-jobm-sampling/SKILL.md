---
name: factorjoin-jobm-sampling
description: FactorJoin 在 JOBM 上的采样模式实现细节：数据流、关键修复、已知限制与改进方向。当用户提到 JOBM 评估、FactorJoin 采样模式 bug、PDF 量纲、alias 映射、子查询对齐、binned_cards、get_cardinality_bound_one 时使用。
---

# FactorJoin JOBM 采样模式实现

## 整体数据流

```
queries.sql（主查询）
  ↓ parse_jobm_grouped（training.py）
subquery_grouped.sql         ← 由训练/物化脚本生成，不提交
  ├── === N === 头部行
  ├── EXPLAIN SELECT ... （主查询行，带 EXPLAIN）
  └── SELECT COUNT(*) ...（子查询行）
  ↓ 过滤掉头部和 EXPLAIN 行
subquery_from_grouped.sql    ← 生成文件，不提交（9472 行 SELECT）
  ↓ 每行对应一个 mapping[i] = 主查询 ID
jobm_sub_to_main.pkl         ← checkpoint，不提交
  ↓ 评估：get_cardinality_bound_one(sql, query_name=f"{main_id}.pkl")
factorjoin.txt（grouped 对齐，9472 行）← 中间结果，不提交
  ↓ remap_factorjoin_jobm.py
factorjoin_remapped.txt（subquery.sql 对齐，6424 行）← 最终结果，提交
```

## 文件位置

```
Benchmark/workloads/JOBM/subquery/
├── subquery.sql              # 标准子查询文件（6424 行，无重复）← 已提交
├── subquery_grouped.sql      # 分组格式（头+EXPLAIN+子查询）← .gitignore
├── subquery_from_grouped.sql # 仅 SELECT 行（9472 行）← .gitignore
└── result/
    ├── real.txt              # 真实基数（6424 行，对齐 subquery.sql）
    ├── duckdb.txt            # DuckDB 估计（6424 行）
    ├── factorjoin.txt        # grouped 格式估计（9472 行）← .gitignore
    └── factorjoin_remapped.txt  # 最终估计（6424 行）← 已提交

methods/FactorJoin/
├── checkpoints/
│   ├── binned_cards_1.0/    # 物化样本（已跟踪 JOB 文件，JOBM 数字文件不提交）
│   │   ├── {N}{letter}.pkl  # JOB 样本（如 10a.pkl）← 已跟踪
│   │   └── {N}.pkl          # JOBM 样本（如 1.pkl, 113.pkl）← .gitignore
│   ├── jobm/                # JOBM 模型目录 ← .gitignore
│   ├── jobm_sub_to_main.pkl # 映射文件 ← .gitignore
│   └── model_jobm_default.pkl ← .gitignore
└── scripts/
    └── remap_factorjoin_jobm.py  # 格式转换脚本 ← 已提交
```

## 关键修复（已合入代码）

### 1. PDF 量纲问题（load_sample.py）

**问题**：`eliminate_one_key_group` 要求 `factors[table].pdfs` 与 `oned_bin_modes` 量纲一致（均为 raw counts）。原代码在 `load_sample_imdb_one_query` 中将 pdfs 除以 table_len 归一化为概率，导致与 `oned_bin_modes`（raw counts，如 2.5M）量纲不匹配，`np.minimum(bin_modes, pdfs)` 始终返回概率值（< 1），最终估计结果全在 0-1 区间。

**修复**：
- 一维 pdf：保持 raw counts（不除以 table_len）
- 二维 pdf：`outer = np.outer(pdf1, pdf2) / filter_size`（联合密度，sum = filter_size）
- `_get_pdf_for_key` 从 gt_factor 取值时乘以 `gt_factor.table_len` 得到 raw counts

```python
# 错误写法（已修复）
pdfs /= table_len  # 归一化成概率 → 与 oned_bin_modes 量纲不符

# 正确写法
# 保持 raw counts，不归一化
source_pdfs[subquery_alias][key] = pdfs  # sum ≈ filter_size

# 2D 外积：sum = filter_size（而非 1 或 filter_size²）
outer = np.outer(pdf1, pdf2) / fs
```

### 2. 别名重映射（bound.py）

**问题**：子查询使用 `table1` 风格别名（如 `title1`），而 `table_buckets` 和 `equivalent_keys` 使用真实表名（如 `title`）。直接查找会触发 `KeyError`。

**修复**：在 `get_cardinality_bound_one` 采样模式分支中，通过 `tables_all`（alias→table 映射）将 `join_keys` 和 `conditional_factors` 重映射为真实表名：

```python
join_keys = {tables_all[alias]: keys for alias, keys in join_keys.items() if alias in tables_all}
conditional_factors = {tables_all[alias]: factor for alias, factor in conditional_factors.items() if alias in tables_all}
```

### 3. equivalent_variables 补全（bound.py）

**问题**：采样模式下 `Factor` 对象没有 `equivalent_variables`（None），而 `eliminate_one_key_group` 要求 `key_group in factors[table].equivalent_variables`。

**修复**：根据 `equivalent_group`（从 `get_join_hyper_graph` 获得）动态补全：

```python
key_to_group = {k: PK for PK, keys in equivalent_group.items() for k in keys}
for factor in conditional_factors.values():
    if factor.equivalent_variables is None:
        new_equiv = [key_to_group[var] for var in factor.variables if var in key_to_group]
        for var, equiv_pk in zip(factor.variables, new_equiv):
            if equiv_pk not in factor.cardinalities:
                factor.cardinalities[equiv_pk] = factor.cardinalities[var]
        factor.equivalent_variables = new_equiv
```

### 4. 超过 2 个 join key 的表（bound.py）

**问题**：`eliminate_one_key_group` 只支持 2D 因子（每表最多 2 个 join key）。JOBM 中 `movie_companies` 有 3 个 join key（company_id, company_type_id, movie_id），会触发 `ValueError`。

**修复**：在 `get_cardinality_bound_one` 中截断 join keys，取字母序前 2 个：

```python
for alias in join_keys:
    if len(join_keys[alias]) > 2:
        join_keys[alias] = set(sorted(join_keys[alias])[:2])
```

同时，`eliminate_one_key_group` 中若 `twod_bin_modes` 不存在（因为表有 3+ 个 schema join keys），用 1D 模式近似（独立性假设）：

```python
if actual_key in self.table_buckets[table].twod_bin_modes:
    bin_modes = self.table_buckets[table].twod_bin_modes[actual_key]
    modes_slice = np.minimum(bin_modes[:, i] if idx_b == 0 else bin_modes[i, :], pdfs_slice)
else:
    bm_1d = self.table_buckets[table].oned_bin_modes[actual_key]
    modes_slice = np.minimum(bm_1d, pdfs_slice)
```

### 5. pkl 格式（create_binned_cols.py）

物化时 pkl 中需存储 `alias_to_table` 字段（主查询别名→表名的映射），供 `load_sample_imdb_one_query` 在子查询评估时正确识别表名：

```python
data = {
    "all_aliases": all_aliases,
    "all_columns": all_columns,
    "all_sqls": all_sqls,
    "results": results,
    "alias_to_table": alias_to_table,  # 必须！
}
```

### 6. subquery_from_grouped.sql → subquery.sql 对齐

`subquery_from_grouped.sql`（9472 行）中同一 SQL 在不同主查询分组中会重复出现。`subquery.sql`（6424 行，唯一）是最终 benchmark 标准。

转换脚本：`methods/FactorJoin/scripts/remap_factorjoin_jobm.py`

```python
# 同一 SQL 多次估计取均值
sql_to_preds = defaultdict(list)
for sql, pred in zip(grouped_sqls, grouped_preds):
    sql_to_preds[sql].append(pred)
remapped = [np.mean(sql_to_preds[sql]) for sql in target_sqls]
```

## 已知限制与改进方向

### 限制 1：空采样的 fallback 处理（已修复）

**原始 bug**：`load_sample.py` 空采样时 `table_len = gt.table_len`（全表行数，如 234K），导致极高选择性谓词（如 `country_code = '[sm]'`，全库仅 1 行）的估计值高达 3600 万，比真实值（0~2）高出 7 个数量级。

**根本原因**：与原始 `sample_on_the_fly.py` 的处理不一致。原始代码空采样时设 `table_len = 1`（保守估计），而我们的代码错误地用了全表行数。

**修复**（`load_sample.py` 第80-85行）：
```python
if table_len == 0:
    # 空采样说明过滤后数据极少，保守地设 filter_size=1（与 sample_on_the_fly.py 一致）
    gt = table_key_equivalent_group[table_name]
    table_len = 1
    pdfs = gt.pdfs[key]  # 归一化概率，sum≈1，作为极小 raw counts
```
`pdfs` 用归一化概率（sum≈1）作为极小 raw counts，在 `eliminate_one_key_group` 中与 `oned_bin_modes`（量级百万）做 `np.minimum` 后得到极小值，正确反映空采样语义。

**修复后 Q-Error**（vs real.txt，6424 条）：
- p50: 15.0x，p90: 1602x，p95: 9994x，p99: 93095x，max: 702669x
- 修复前：p50: 22.9x，p90: 5183x，p95: 27684x，p99: 446363x，max: 36292062x

仍有残余高估（p99 仍达 93K），原因是 `[sm]` 等极稀疏值在采样表中为 0 行，`table_len=1` 对应的反推行数 `1/(0.01) = 100` 仍远大于真实值（0~2）。这是采样率不足的固有限制。

### 限制 2：3 join key 表的近似
`movie_companies` 有 company_id、company_type_id、movie_id 三个 join key，但代码截断为前 2 个（字母序），第 3 个被忽略。可能导致低估或高估。

**改进方向**：支持 3D 因子，或使用更好的近似（如链式分解）。

### 限制 3：2D 外积独立性假设
两个 join key 的联合分布用外积近似（独立性假设）。对于相关性强的列（如同表的外键对），该假设会引入误差。

**改进方向**：从采样数据中直接估计联合分布（如果样本足够）。

## 运行命令

### 完整 JOBM 评估流程

```bash
cd methods/FactorJoin

# 1. 训练模型（首次）
python run_experiment.py --dataset jobm --generate_models \
    --data_path ../../methods/SafeBound/Data/IMDB/{}.csv \
    --model_path checkpoints/jobm/model_jobm_default.pkl \
    --n_dim_dist 1 --bucket_method fixed_start_key \
    --db_conn_kwargs "dbname=imdbm user=liwei host=localhost port=5432" \
    --prepare_sample --sampling_percentage 1.0 --sampling_type ss \
    --query_file_location ../../Benchmark/workloads/JOBM/queries.sql \
    --materialize_sample

# 2. 评估子查询
python run_experiment.py --dataset jobm --evaluate \
    --model_path checkpoints/jobm/model_jobm_default.pkl

# 输出：Benchmark/workloads/JOBM/subquery/result/factorjoin.txt（9472 行）

# 3. 转换为 subquery.sql 对齐格式
python scripts/remap_factorjoin_jobm.py

# 输出：Benchmark/workloads/JOBM/subquery/result/factorjoin_remapped.txt（6424 行）
```

### 关键参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| `--dataset` | `jobm` | 触发 JOBM 特定分支 |
| `--n_dim_dist` | `1` | 采样模式仅支持 1D |
| `--bucket_method` | `fixed_start_key` | IMDB 推荐（快速） |
| `--sampling_percentage` | `1.0` | 100% 采样率 |
| `--sampling_type` | `ss` | stratified sampling |

## .gitignore 规则

```gitignore
# JOBM 中间结果
methods/FactorJoin/checkpoints/jobm/
methods/FactorJoin/checkpoints/jobm_sub_to_main.pkl
methods/FactorJoin/checkpoints/model_jobm_default.pkl
Benchmark/workloads/JOBM/subquery/subquery_grouped.sql
Benchmark/workloads/JOBM/subquery/subquery_from_grouped.sql
Benchmark/workloads/JOBM/subquery/result/factorjoin.txt
methods/FactorJoin/debug_*.py
methods/FactorJoin/test_three_queries.py
```
