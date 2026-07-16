---
name: starce-overview
description: StarCE 项目总览：系统架构、config.json 所有参数含义、核心数据结构（EqualSet/DegreeSequence/DSStatistic/StatisticManager）、主要运行模式，以及如何将 FactorJoin/SafeBound/PostgreSQL 等外部基数估计注入 DuckDB 的完整数据流。当用户提到 StarCE 整体架构、config 参数含义、基数注入机制、注入数据流、统计信息收集、运行模式时使用。
---

# StarCE 总览

StarCE 是一个**内嵌于 DuckDB 的基数估计器**，通过修改 Join Order Optimizer 拦截并替换默认的基数估计，支持自身统计算法与外部估计器（FactorJoin、SafeBound、PostgreSQL 等）的对比实验。

## 项目结构

| 路径 | 作用 |
|------|------|
| `main.cpp` | 入口：解析 config、驱动统计收集、执行 SQL、输出结果 |
| `duckdb/src/include/duckdb/starce/starce.hpp` | **全部核心逻辑**（头文件内联实现），`StatisticManager` 单例 |
| `duckdb/src/include/duckdb/starce/statistic.hpp` | `DegreeSequence`、`DSStatistic` 数据结构 |
| `duckdb/src/include/duckdb/starce/equalset.hpp` | `EqualSet`、`TableColumn` 数据结构 |
| `duckdb/src/optimizer/join_order/query_graph_manager.cpp` | 注入点：注册表信息、替换单表基数 |
| `duckdb/src/optimizer/join_order/cardinality_estimator.cpp` | 注入点：替换多表连接基数估计 |
| `duckdb/src/optimizer/join_order/relation_manager.cpp` | `ResetCardinality()`：改写 `LogicalGet.estimated_cardinality` |
| `experiment/running_space/` | 工作目录，所有相对路径均以此为基准 |

---

## config.json 参数说明

所有配置均在 `experiment/running_space/config.json` 中，程序启动时读取。

### 运行模式开关（0/1）

| 字段 | 含义 |
|------|------|
| `EnableStarCE` | 是否启用 StarCE 估计器；0 时退化为 DuckDB 原生估计 |
| `RecordingSubquery` | 录制每条 SQL 估计过程中产生的多表子查询 SQL 及其 StarCE 估计基数，执行完后写出到 `SUBQUERY_PATH` 和 `SUBQUERY_RESULT_PATH` |
| `RecordingSingleQuery` | 录制单表过滤查询 SQL（无基数）到 `SINGLE_QUERY_PATH`，供外部工具（PG/DuckDB）计算基数后回填 |
| `SubqueryOutputGroupByMain` | `RecordingSubquery` 输出时是否按主查询分组（`=== N ===` 分隔行） |
| `UseSubqueryCard` | 从文件注入多表子查询预计算基数，**完全绕过** StarCE 自身算法 |
| `UseSingleTableCard` | 从文件注入单表过滤预计算基数（如 PostgreSQL 估计值），StarCE 自身仍参与连接估计 |
| `UseAssignedAdjustRate` | 使用 config 中手动指定的 `ADJUST_RATE` / `PREDICATE_ADJUST_RATE`，而非自动计算 |
| `RefreshStatistics` | 强制重新收集统计信息，忽略 `STATS_PATH` 缓存 |
| `EnableStarSplit` | 启用大 EqualSet 拆分优化（按 `MaxStarSize` 切块），执行后打印 eset 大小分布 |
| `IsCollectingRelErr` | 读入真实基数（`REAL_CARD_PATH`），执行后输出子查询相对误差到 `REL_ERR_PATH` |

### 算法参数

| 字段 | 类型 | 含义 |
|------|------|------|
| `PredMethod` | int | 谓词估计方法：`0`=调整率法（DS 合并），`1`=均匀假设法（缩放系数） |
| `CollectParallel` | int | 统计信息收集并行线程数（上限为硬件线程数） |
| `CompressPrecision` | double | DegreeSequence 对数桶精度，默认 `1.2`，影响统计缓存文件名后缀（如 `statistics_STATS_cp1.2.json`） |
| `ADJUST_RATE` | double | join 估计全局调整率（`UseAssignedAdjustRate=1` 时生效） |
| `PREDICATE_ADJUST_RATE` | double | 谓词过滤调整率（`UseAssignedAdjustRate=1` 时生效） |

### 路径配置

| 字段 | 用途 |
|------|------|
| `SCHEMA_PATH` | Schema JSON，定义各表的等值连接关系（EqualSets），用于统计收集 |
| `DB_PATH` | DuckDB 数据库文件（如 `imdb.db`、`stats.db`） |
| `STATS_PATH` | 统计信息缓存 JSON，首次运行后生成，后续直接加载 |
| `SQL_PATH` | 主输入 SQL 文件，每行一条，StarCE 依次执行 |
| `SUBQUERY_PATH` | 子查询 SQL 文件：`RecordingSubquery=1` 时写出；`UseSubqueryCard=1` 时读入 |
| `SUBQUERY_RESULT_PATH` | 子查询基数文件，与 `SUBQUERY_PATH` 行对行对应 |
| `SINGLE_QUERY_PATH` | 单表查询 SQL 文件：`RecordingSingleQuery=1` 时写出；`UseSingleTableCard=1` 时读入 |
| `SINGLE_QUERY_RESULT_PATH` | 单表查询基数文件（如 `pg_est_subquery_order.txt`） |
| `REAL_CARD_PATH` | 真实子查询基数文件，`IsCollectingRelErr=1` 时读入 |
| `REL_ERR_PATH` | 相对误差输出文件，`IsCollectingRelErr=1` 时写出 |

---

## 核心数据结构

### EqualSet（`equalset.hpp`）

一组通过等值连接相互关联的 `(表名, 列名)` 对，例如 `posts.Id = votes.PostId` 构成含两个元素的 EqualSet。统计信息以 EqualSet 为单位收集和存储。

### DegreeSequence（`statistic.hpp`）

对数桶压缩的度序列：记录"有多少个 key 的度（连接度数）≤ maxDegree[i]"。
- `dot(other)` — 按最坏匹配策略合并两个 DS，计算连接基数上界
- `GetCard()` — 返回总基数（Σ count[i] × maxDegree[i]）
- `GetNDV()` — 返回 NDV（Σ count[i]）

### DSStatistic（`statistic.hpp`）

一个 EqualSet 的完整统计，包含：
- `centralDs` — 中心度序列（join 结果的联合度）
- `ds[table]` — 每张表的边度序列
- `card` — 真实基数

关键操作：
- `Merge(other, commonTable)` — 沿公共表合并两个 DSStatistic（核心连接估计）
- `AdjustToAverage(ndv, k)` — 按调整率 k 向均匀分布靠拢
- `ApplyFilterCoefficient(coeff)` — 按系数整体缩放（PredMethod=1 时用）

### StatisticManager（`starce.hpp`）

全局单例（`starce::StatisticManager::GetInstance()`），持有：
- `statistics: map<EqualSet, DSStatistic*>` — 所有 EqualSet 的统计信息
- `subqueryCard: map<string, int64_t>` — 注入的多表子查询基数
- `singleQueryCard: map<string, int64_t>` — 注入的单表过滤基数
- `filterString: map<idx_t, string>` — 每个 relation 的谓词过滤条件

---

## main.cpp 运行流程

```
ReadConfig("config.json")
    │
    ▼
初始化 StatisticManager，同步配置参数
    │
    ▼
TryReadStatistics(STATS_PATH)
    ├── 成功 → 反序列化统计缓存（跳过收集）
    └── 失败 → CollectStatistics(DB_PATH, SCHEMA_PATH)
               │  按 EqualSet 执行聚合 SQL，多线程并行
               └→ 序列化写入 STATS_PATH
    │
    ▼
sm.EnableStarCE = EnableStarCE   ← 统计收集完后才启用估计器
    │
    ▼
按开关读入外部基数：
    UseSubqueryCard    → ReadSubqueryCard()    加载 subqueryCard map
    UseSingleTableCard → ReadSingleQueryCard() 加载 singleQueryCard map
    IsCollectingRelErr → ReadRealCard()        加载 realCard map
    │
    ▼
ExecuteSql(con, SQL_PATH)
    对每条 SQL：sm.ParsePredicate(sql) → con.Query(sql)
    DuckDB 执行时 StarCE Hook 触发（见下方注入机制）
    │
    ▼
执行后输出：
    RecordingSubquery    → OutputSubquery()    写子查询 SQL + 基数
    RecordingSingleQuery → OutputSingleQuery() 写单表查询 SQL
    IsCollectingRelErr   → OutputRelErr()      写相对误差
```

---

## 外部基数注入机制

### 注入点：DuckDB Join Order Optimizer

StarCE 通过修改 4 个文件集成到 DuckDB 优化器中，每条查询执行时触发：

```
JoinOrderOptimizer::Optimize()
    │
    ├── QueryGraphManager::Build()
    │       ├── sm.PrepareEstimate()               ← 清空查询上下文
    │       ├── sm.AddTable(i, name, cols, card)   ← 注册每个 relation
    │       ├── sm.AddPredicate(t1,t2,c1,c2)       ← 构建 EqualSet
    │       └── [UseSingleTableCard]
    │           RelationManager::ResetCardinality(sm)
    │               └── LogicalGet.estimated_cardinality = sm.GetTableCard(i)
    │
    ├── CardinalityEstimator::EstimateCardinalityWithSet()
    │       └── [use_starce=true]
    │           result = sm.EstimateCardinality(rels)
    │               ├── [UseSubqueryCard] → subqueryCard[sql]（短路返回）
    │               └── [否则] StarCE DS 统计算法
    │
    └── sm.FinishEstimate()
```

### 模式 A：UseSingleTableCard — 单表基数替换

适用场景：用 PostgreSQL 等外部工具的单表估计值替换 DuckDB 默认统计，StarCE 自身仍负责连接估计。

```
single_query.sql + pg_est.txt
    │
    ReadSingleQueryCard() → sm.singleQueryCard: map<string, int64_t>
    │
    QueryGraphManager::Build() → ResetCardinality(sm)
    │   GetTableCard(i) → GetSingleQuery(i) 重建 SELECT COUNT(*) SQL
    │                   → singleQueryCard[sql]
    └→ LogicalGet.estimated_cardinality 被覆盖
       StarCE DS 算法用注入的单表基数参与连接估计
```

### 模式 B：UseSubqueryCard — 多表子查询基数短路

适用场景：将 FactorJoin/SafeBound/真实基数等完整结果注入，完全替代 StarCE 算法，在相同 DuckDB 框架下对比代价。

```
subquery.sql + factorjoin.txt（或 safebound.txt / real.txt）
    │
    ReadSubqueryCard() → sm.subqueryCard: map<string, int64_t>
    │
    EstimateCardinality(rels)
    │   GetSubquery(rels) 规范化生成 SQL 字符串（表/列排序）
    └→ subqueryCard[sql] → 直接返回，跳过 StarCE 所有算法
```

**关键设计**：SQL 字符串作为 map 的 key，由 `GetSubquery()` / `GetSingleQuery()` 规范化生成（表名、列名排序），确保不同调用路径下字符串一致。

---

## 主要运行模式汇总

| 模式 | 关键开关组合 | 典型用途 |
|------|-------------|---------|
| 正常估计 | `EnableStarCE=1`，其余注入/录制为 0 | StarCE 自身估计效果评测 |
| 录制单表查询 | `RecordingSingleQuery=1` | 生成单表 SQL，供外部工具计算基数 |
| 注入单表基数 | `UseSingleTableCard=1` | 用 PG 估计替换单表，对比对连接估计的影响 |
| 录制子查询 | `RecordingSubquery=1` | 生成 StarCE 估计的多表子查询及基数 |
| 注入子查询基数 | `UseSubqueryCard=1` | 注入 FactorJoin/SafeBound/真实基数做对比实验 |
| 收集误差 | `IsCollectingRelErr=1` + `UseSubqueryCard=1` | 计算某估计器相对于真实基数的 Q-Error |
| DuckDB 原生 | `EnableStarCE=0` | 作为基线 baseline |
