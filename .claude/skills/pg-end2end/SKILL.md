---
name: pg-end2end
description: StarCE / SafeBound → PostgreSQL 端对端测试 Pipeline：将外部基数估计按内容匹配注入 PostgreSQL 优化器，评估对执行计划的影响。支持多 estimator 对比、key-value 注入对齐、STATS-CEB 和 JOBM 数据集。当用户提到 PG 端对端测试、基数注入、EXPLAIN ANALYZE 对比、执行计划变更、key-value 注入、内容匹配 时使用。
---

# StarCE / SafeBound → PostgreSQL 端对端测试

## 快速参考

### 运行命令

```bash
# 以下命令在项目根目录下运行
cd experiment/pg_end2end
conda activate TestEnv

# 全流程（estimate + safebound + test + PG native baseline）
python run.py all --native

# 分步
python run.py estimate          # Phase 2: StarCE 估计
python run.py safebound         # Phase 2b: SafeBound 估计
python run.py test              # Phase 3: PG 测试 (StarCE + SafeBound)
python run.py test --native     # 含 PG native baseline
python run.py all --force       # 强制重跑全部

# Phase 1: JOBM 子查询生成
python gen_jobm_subqueries.py   # 从 join_est_record_job.txt 生成子查询 SQL
```

### 文件结构

```
experiment/pg_end2end/
├── configs.yaml                 # 配置入口（含 safebound 模型路径）
├── run.py                       # 主入口
├── gen_jobm_subqueries.py       # JOBM 子查询 SQL 生成器
├── gen_stats_subqueries.py      # STATS-CEB 子查询 SQL 生成器
├── gen_truecard_stats.py        # STATS-CEB 真实基数生成（canonical key 匹配 + PG 执行）
├── lib/
│   ├── config.py                # 配置管理 & StarCE config.json 生成
│   ├── estimate.py              # Phase 2: StarCE 估计（key-value 格式）
│   ├── safebound_estimate.py    # Phase 2b: SafeBound 估计
│   ├── test.py                  # Phase 3: PG 端对端 EXPLAIN ANALYZE
│   └── extract.py               # Phase 1: PG 子查询提取
├── estimates/<benchmark>/       # 估计结果（key\tvalue 格式）
│   ├── true_card.txt            # STATS-CEB 真实基数（gen_truecard_stats.py 生成）
│   ├── default.txt
│   ├── pm0_ar1_par1.txt
│   ├── pm1_ar0.1_par0.1.txt
│   ├── safebound.txt
│   └── single_query/            # 单表估计（UseSingleTableCard 用）
├── pg_results/<benchmark>/      # PG EXPLAIN ANALYZE 结果
│   ├── pg_native/               # PG 原生基线
│   ├── default/                 # StarCE 默认配置
│   ├── pm0_ar1_par1/
│   ├── pm1_ar0.1_par0.1/
│   └── safebound/
└── data/
    ├── stats_ceb_sub_queries.sql # STATS-CEB PG 子查询（gen_stats_subqueries.py 生成）
    ├── jobm_sub_queries.sql     # JOBM PG 子查询（gen_jobm_subqueries.py 生成）
    ├── jobm_sub_queries_old.sql # 旧版备份
    └── jobm_sub_queries_new.sql # 临时版本
```

### configs.yaml 关键配置

```yaml
benchmarks:
  jobm:
    pg_database: imdbm
    pg_data_dir: /mnt/sdb1/tlw/pgdata          # PG 数据目录（临时估计文件写入处）
    pg_subqueries: .../data/jobm_sub_queries.sql
    pg_original: .../Benchmark/workloads/JOBM/queries.sql
    db_path: .../Benchmark/duckdb/imdb.db
    schema_path: .../Benchmark/IMDB/schema_imdb.json
    stats_path: .../experiment/checkpoint/StarCE/statistics_imdb.json
    single_query_path: .../estimates/jobm/single_query/single_query.sql
    single_query_result_path: .../estimates/jobm/single_query/pg_est.txt

  stats_ceb:
    pg_database: stats
    pg_data_dir: /mnt/sdb1/tlw/pgdata
    pg_subqueries: .../stats_CEB_sub_queries.sql
    pg_original: .../stats_CEB.sql
    ...

test_queries: []                   # 空 = 全部

starce_configs:
  - name: default
    PredMethod: 0
    ADJUST_RATE: 1.0
    PREDICATE_ADJUST_RATE: 1.0
  - name: pm0_ar1_par1
    ...
  - name: pm1_ar0.1_par0.1
    ...

safebound:                         # SafeBound 模型路径
  stats_ceb:
    model_path: .../checkpoint/SafeBound/SafeBound_3_Stats.pkl
  jobm:
    model_path: .../checkpoint/SafeBound/SafeBound_3_JOBM.pkl
```

---

## 核心注入机制：A 方案（Key-Value 内容匹配）

> **这是 2026-05 完成的重大改造，替代了原有的顺序注入机制。**

### 旧机制的问题

原有 `benchmark.patch` 在 `costsize.c` 中按 `join_est_no++` **顺序读取**估计值。StarCE 估计值按 DuckDB 的子查询顺序排列，但 PG 在优化阶段按自己的 join 枚举顺序调用 `set_joinrel_size_estimates`。两者 join 顺序不同导致**估计值被注入到错误的 join 上**。

典型案例：JOBM Q19 的一个 join（实际 648K 行）被注入了 est=1 的估计值，导致 PG 选 NLJ 执行 194 万次，执行时间 17.8s vs PG native 1.6s（11 倍退化）。

### 新机制：按 join 表集合做内容匹配

#### C 代码（costsize.c，约 80 行）

1. **Key 生成**：`join_to_key(root, inner_rel, outer_rel, key, ...)` — 从 inner/outer `RelOptInfo` 的 `relids` 遍历基表，从 `root->simple_rte_array` 取别名，排序生成 `{alias1,alias2,...}` 格式
2. **Key-Value 结构**：`JoinEstKV {char key[256]; double value;}`，最大 2000 条/查询
3. **文件读取**：`read_from_fspn_join_estimate()` 解析 `{key}\t{value}\n` 格式
4. **查找**：`lookup_join_estimate(key)` 线性搜索
5. **注入点**：`join_to_key()` → `lookup_join_estimate()` 替代 `join_card_ests[join_est_no++]`
6. **错位检测**：key 找不到时 `ereport(ERROR)` 直接退出，避免静默得到错误结论

核心注入代码（costsize.c 约行 5340）：
```c
if (ml_joinest_enabled) {
    if (join_est_no == 0) join_est_entry_count = 0;
    if (join_est_entry_count == 0)
        read_from_fspn_join_estimate(ml_joinest_fname);

    char key[JOIN_EST_KEY_MAX];
    join_to_key(root, inner_rel, outer_rel, key, sizeof(key));
    double join_est = lookup_join_estimate(key);
    join_est_no++;

    if (join_est < 0)
        ereport(ERROR, ...);  // 错位直接退出

    return clamp_row_est(join_est);
}
```

#### Python 侧（estimate.py / test.py）

1. **`_subquery_join_key(sql)`**：从子查询 SQL 的 FROM 子句提取别名，生成 `{alias1,alias2,...}` key
2. **估计文件格式**：`{key}\t{value}\n`（替代纯 float 列表）
3. **`_extract_query_estimates()`**：支持解析 `key\tvalue` 和纯 `value` 两种格式
4. **临时注入文件**：按 query 写 key-value 格式到 PG 数据目录

#### Key 格式约定

- 别名统一**小写**（Python `.lower()`，C `tolower()`）
- 别名按**字母序**排列
- 格式：`{alias1,alias2,...}`（逗号分隔，无空格）
- 示例：`{at,t}` = aka_title 与 title 的 join

---

## PG C 代码编译与部署

修改 `costsize.c` 后：

```bash
# 在项目根目录下运行
cd Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1
make -j4
cd src/backend
sudo make install
/usr/local/pgsql/13.1/bin/pg_ctl restart -D /mnt/sdb1/tlw/pgdata
```

关键 C 常量：
- `JOIN_EST_MAX_ENTRIES = 2000` — 每条查询最大 join 组合数（11 表查询约需 ~2000）
- `JOIN_EST_KEY_MAX = 256` — key 字符串最大长度

---

## FROM 缺表子查询的 Ratio 修复

### 问题

PG 生成的子查询中，WHERE 子句引用了 FROM 未声明的表别名（来自外层查询块），如：
```sql
-- FROM 只有 c, u，WHERE 引用了 b（badges）
SELECT COUNT(*) FROM comments as c, users as u
WHERE b.UserId = u.Id AND c.Score=0 AND ...
```

### SafeBound 侧（safebound_estimate.py）

`_estimate_via_ratio()`：
1. 构建完整 join（FROM 表 + 缺失表）→ `card_full`
2. 从 SafeBound 模型 `tableStatsDict[table].numRows` 取驱动表行数 → `card_drive`
3. 返回 `card_full / card_drive`

依赖 `_STATS_ALIAS_TO_TABLE` 映射（如 `{'b': 'badges', 'c': 'comments', ...}`）。

### StarCE 侧（estimate.py）

`_patch_starce_zeros()`：
1. 对零值子查询检测 `_detect_missing_from()`
2. `_build_full_join_sql()` 构造完整 join SQL
3. Batch 跑 StarCE → `_extract_cardinality()` 递归处理 CROSS_PRODUCT
4. 从 PG 查询驱动表行数 → ratio 修正

---

## STATS-CEB 子查询生成

### gen_stats_subqueries.py

对每条原始查询，通过 PG 的 `print_sub_queries` 机制提取 join 枚举顺序，生成与 PG 优化器一致的子查询 SQL。

输出格式：`{alias_set}||SELECT COUNT(*) FROM ... WHERE ...;||query_id`

核心逻辑：

1. **`parse_query(query)`** — 解析 SQL 获取表别名、过滤条件、join 条件
2. **`convert_to_PK_join()`** — 将 join 条件按 PK-FK 关系归类到 `connect_to_u`（users hub）和 `connect_to_p`（posts hub）
3. **`match_join_condition()`** — 为给定表集合生成 join 条件，注入必要的 hub 表
4. **`generate_subquery_sql()`** — 组装最终 SQL

### FK-FK 直接 Join 优化（2026-05 修复）

**问题**：当两个非 hub 表共享同一个 hub（如 badges 和 posts 都通过 users 的 UserId/OwnerUserId 连接），原逻辑注入 `users as u` 做 FK-PK-FK join，导致 3 表 join 极慢。

**修复**：生成直接 FK-FK join（如 `b.UserId = p.OwnerUserId`），只在 hub 表有 filter 谓词时才注入 hub。通过 `_fkfk_join()` 函数从 `connect_to_u`/`connect_to_p` 提取 FK 列并直接配对。

**示例**：
```sql
-- 修复前（慢，3 表 join）
FROM badges as b, posts as p, users as u
WHERE b.UserId = u.Id AND p.OwnerUserId = u.Id AND ...

-- 修复后（快，2 表 join）  
FROM badges as b, posts as p
WHERE b.UserId = p.OwnerUserId AND ...
```

### 连通性后处理（`_ensure_connectivity`）

对生成的 join 条件做 BFS 连通性检查。如果存在断开连接的组件（如 `{b,u}` 和 `{p,v}` 分离），自动注入缺失的 hub 连接或 FK-FK join 将其连通。确保**不会生成笛卡尔积**。

### 重新生成命令

```bash
cd experiment/pg_end2end
conda activate TestEnv
python gen_stats_subqueries.py
# 输出: data/stats_ceb_sub_queries.sql (2603 条子查询)
```

---

## true_card.txt 生成

### gen_truecard_stats.py

为 STATS-CEB 的每条 PG 子查询获取真实 COUNT(*) 基数，用于：
1. **Bug 零值检测**（`estimate.py`）：区分 StarCE 产出的合法零值和 bug 零值
2. **TrueCard 注入**（`run.py test`）：将真实基数注入 PG 优化器作为理论上界

### 禁止规则

**🔴 绝对禁止通过 PostgreSQL 直接执行 `SELECT COUNT(*)` 来获取真实基数。** 原因：
- 大表 join 的 COUNT(*) 极慢（单个查询可达数分钟甚至超时）
- 2603 条子查询 × 每条数秒到数分钟 = 不可接受的耗时
- 必须通过 canonical key 匹配 benchmark 的 `real.txt`（已有预计算的真值）

### 匹配策略：Hub 表剥离

STATS-CEB 的 PG 子查询中 **76.8% 注入了 hub 表（users `u`、posts `p`）** 将 FK-FK join 转为 PK-FK join。Benchmark 子查询使用直接 FK-FK join，表集合不同。

匹配时需剥离 hub 表：
1. 检测 PG 子查询的 FROM 中是否包含 hub 别名（u, p）
2. 若包含，将 hub 表从表集合中移除
3. 移除与 hub 表的 PK-FK join 条件（`alias.ForeignKey = hub.Id`）
4. 用剥离后的表集合和剩余 filter 做 canonicalize
5. 在 benchmark `real.txt` 中匹配

### Canonical Key 机制

`canonicalize(sql, alias_map)` 将子查询 SQL 归一化为 `{table_set}|FILTER:sorted_filters` 格式：
- 解析 FROM 子句获取表别名，通过 `alias_map` 解析为基表名
- 拆分 WHERE 子句，剔除以 `col=col` 形式出现的 join 条件
- 剩余 filter 谓词排序后拼接
- **关键细节**：`normalize_condition` 中大小写处理必须在 alias 替换之前做 `lower()`（否则 `postHistory1` ≠ `posthistory1`）

### 错误处理

- Canonical key 匹配失败 → **抛出 RuntimeError，禁止静默 fallback**
- 禁止 PG 直接执行作为 fallback

### 运行命令

```bash
cd experiment/pg_end2end
conda activate TestEnv
python gen_truecard_stats.py
# 输出: estimates/stats_ceb/true_card.txt (2603 行, key\tvalue 格式)
```

---

## SafeBound 集成

### 新增文件：lib/safebound_estimate.py

- Stats benchmark：用自定义 `_sql_to_joingraph_stats()` 解析（仅处理 FROM/WHERE）
- JOBM benchmark：将 `SELECT COUNT(*)` 规范化为 `SELECT *`，用 SafeBound 标准 `SQLQueriesToJoinQueryGraphs()` 解析
- 对 FROM 缺表子查询自动使用 ratio 方法

### configs.yaml 新增 safebound 配置段

```yaml
safebound:
  stats_ceb:
    model_path: experiment/checkpoint/SafeBound/SafeBound_3_Stats.pkl
  jobm:
    model_path: experiment/checkpoint/SafeBound/SafeBound_3_JOBM.pkl
```

### run.py 新增 safebound 阶段

- `python run.py safebound` — 生成 SafeBound 估计
- test 阶段自动检测 `safebound.txt` 并注入测试
- `all` 阶段包含 SafeBound 估计 + 测试

---

## 实验调试与验证

### 验证注入是否正确对齐

PG 日志中不应出现 `join estimate key ... not found` 的 ERROR。若出现则表示提取/注入不一致。

### 诊断单条查询的 join 估计

```python
# 获取注入后的 EXPLAIN JSON 查看每个 join 的 Plan Rows
cur.execute("SET join_est_no = 0; SET ml_joinest_enabled = true")
cur.execute(f"SET ml_joinest_fname = '{estimate_filename}'")
cur.execute(f"EXPLAIN (FORMAT JSON) {query_sql}")
# 检查每个 Join 节点的 Plan Rows 是否正常（不应有明显错位如 est=1, actual=648K）
```

### 检查估计文件 key 覆盖

```python
from lib.estimate import _subquery_join_key
# 检查子查询 SQL 和估计文件中的 key 是否与 PG 生成的 key 一致
```

---

## 已知限制

1. **`aka_title` 别名**：PG 将 `AS AT` 转为小写 `at`，需在 alias 映射中处理大小写
2. **Nested Loop 的 join 条件**：NLJ 节点的条件在 inner child 的 `Index Cond` 中，非 `Hash Cond`/`Join Filter`
3. **单表单谓词子查询**：JOBM 有约 16 条单表空 WHERE 子查询，StarCE 返回 0.0
4. **SafeBound 单表限制**：`functionalFrequencyBound` 不支持无 join 的单表查询，需用 `tableStatsDict.numRows`
5. **PM1 配置**（AR=0.1, PAR=0.1）：估计偏差较大导致 JOBM 上 155.5% vs native，不推荐
6. **STATS-CEB 子查询 canonical key 匹配**：~2% 子查询（q63-q72、q139-q142 等复杂查询）无法通过 canonical key 匹配到 benchmark，需走 PG 直接执行。这些查询中 `posts as p` 被不必要地注入为 hub（虽然已有 FK-FK join 连通），后续可优化 `match_join_condition` 的 leftover 处理逻辑来消除
7. **FK-FK join 性能**：直接 `SELECT COUNT(*)` 在无索引 FK 列上执行大表 join 可能很慢（最慢达 79s），因此 `gen_truecard_stats.py` 中 PG 执行超时设为 120s。生产环境中这些查询依赖 benchmark 的 canonical key 匹配，不走 PG 执行

---

## 相关 Skills

- [starce-overview](../starce-overview/SKILL.md) — StarCE 架构总览
- [starce-usage](../starce-usage/SKILL.md) — StarCE 运行与 config 参数
- [postgresql-env](../postgresql-env/SKILL.md) — PostgreSQL 环境配置
- [experiment-workflow](../experiment-workflow/SKILL.md) — 实验流程总览
- [benchmark-datasets](../benchmark-datasets/SKILL.md) — 基准数据集说明
