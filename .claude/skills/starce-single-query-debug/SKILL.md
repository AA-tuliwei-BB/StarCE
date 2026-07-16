---
name: starce-single-query-debug
description: 特化单条查询调参测试：running_space 配置、参数速查（PredMethod/CompressPrecision/AdjustRate/UseSingleTableCard）、对照实验（DuckDB 原生/TrueCard 注入/RecordingSubquery）、切换统计信息精度、误差分析工作流。当用户提到单查询测试、调参对比、config.json 参数、RecordingSubquery、UseSubqueryCard、UseSingleTableCard、PredMethod、CompressPrecision 切换时使用。
---

# StarCE 单查询特化测试方法

## 目的

将 running_space 配置为只跑一条（或少数几条）查询，快速迭代调参，观察执行时间和估计值的变化。

---

## 基本步骤

### 1. 提取目标查询

```bash
# 以下命令在项目根目录下运行
cd experiment/running_space

# 从 queries.sql 提取第 N 行（查询编号从 1 开始）
sed -n '58p' ../../Benchmark/workloads/STATS-CEB/queries.sql > q58_only.sql

# 也可以手动写入多条查询
cat > my_queries.sql << 'EOF'
select count(*) FROM ...;
select count(*) FROM ...;
EOF
```

### 2. 修改 config.json

关键字段：

```json
{
    "EnableStarCE": 1,
    "UseSubqueryCard": 0,
    "UseSingleTableCard": 1,
    "RefreshStatistics": 0,
    "PredMethod": 1,
    "CompressPrecision": 1.5,
    "DB_PATH": "Benchmark/duckdb/stats.db",
    "SCHEMA_PATH": "../../Benchmark/STATS/schema_stats.json",
    "STATS_PATH": "statistics_stats.json",
    "SQL_PATH": "q58_only.sql",
    "SUBQUERY_PATH": "../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql",
    "SUBQUERY_RESULT_PATH": "dummy_result.txt",
    "SINGLE_QUERY_PATH": "../../Benchmark/workloads/STATS-CEB/single_query/single_query.sql",
    "SINGLE_QUERY_RESULT_PATH": "../../Benchmark/workloads/STATS-CEB/single_query/pg_est.txt",
    "ADJUST_RATE": 1,
    "PREDICATE_ADJUST_RATE": 1
}
```

### 3. 运行并计时

```bash
cd experiment/running_space
time ./starce
```

输出中 `runtime: XXXX ms` 是 DuckDB 实际执行时间，`time` 命令的 total 包含进程启动开销。

---

## 可调参数速查

| 参数 | 含义 | 典型值 |
|------|------|--------|
| `EnableStarCE` | 是否启用 StarCE 估计 | 0=DuckDB原生（对照），1=StarCE |
| `PredMethod` | 谓词处理方式 | 0=调整率，1=均匀假设 |
| `CompressPrecision` | 度序列分桶精度 | 1.1/1.2/1.5/2.0 |
| `ADJUST_RATE` | Merge 后向均值收缩比例 | 0.1~1.0 |
| `PREDICATE_ADJUST_RATE` | 谓词过滤时的收缩比例 | 0.1~1.0 |
| `UseAssignedAdjustRate` | 是否使用手动指定的 AdjustRate | 0=从统计文件读取，1=用上面两个值 |
| `EnableStarSplit` | 是否拆分大 EqualSet | 0/1 |
| `UseSingleTableCard` | 是否用外部单表基数 | 0=DuckDB估计，1=注入 |

### 切换统计信息精度（无需重新收集）

running_space 中已有不同 CompressPrecision 的预计算文件：

```
statistics_STATS_cp1.1.json   # 最精细
statistics_STATS_cp1.2.json
statistics_STATS_cp1.5.json
statistics_STATS_cp2.json     # 最粗糙
statistics_stats.json         # 默认（cp2.0）
```

修改 `STATS_PATH` 直接切换，无需改 `CompressPrecision`（CompressPrecision 只在收集阶段生效）。

---

## 常用对照实验

### 对照1：关闭 StarCE，看 DuckDB 原生性能

```json
"EnableStarCE": 0
```

### 对照2：注入真实子查询基数（TrueCard 上界）

```json
"UseSubqueryCard": 1,
"UseSingleTableCard": 0,
"SUBQUERY_PATH": "../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql",
"SUBQUERY_RESULT_PATH": "../../Benchmark/workloads/STATS-CEB/subquery/result/real.txt"
```

**重要**：`SUBQUERY_PATH` 的行数必须与 `SUBQUERY_RESULT_PATH` 一致，否则基数对应关系错乱，会注入错误的基数导致计划更差。

- JOBLight：`subquery.sql` 有 836 行，`real.txt` 有 451 行，**不匹配**，需确认用哪个版本
- 注入后务必先跑 EXPLAIN 验证计划是否合理，再执行实际查询

### 对照3：记录 StarCE 对每条子查询的估计值

```json
"RecordingSubquery": 1,
"SQL_PATH": "explain_q58.sql",
"SUBQUERY_RESULT_PATH": "q58_starce_cards.txt"
```

先生成 explain 版本：
```bash
echo "EXPLAIN $(cat q58_only.sql)" > explain_q58.sql
```

---

## 典型工作流：调参对比

```bash
cd experiment/running_space

# 基准：StarCE 当前配置
time ./starce 2>&1 | grep runtime

# 改一个参数
sed -i 's/"PredMethod": 1/"PredMethod": 0/' config.json
time ./starce 2>&1 | grep runtime

# 换统计文件
sed -i 's/statistics_stats.json/statistics_STATS_cp1.1.json/' config.json
time ./starce 2>&1 | grep runtime

# 恢复
git checkout config.json  # 或手动改回
```

---

## 注意事项

- `SQL_PATH` 填相对路径时，相对于 `running_space/` 目录
- `STATS_PATH` 填相对路径时，相对于 `running_space/` 目录；`SCHEMA_PATH`、`SUBQUERY_PATH` 等相对于 `running_space/` 目录
- `RefreshStatistics: 1` 会重新收集统计信息（耗时），调参时保持为 0
- `UseAssignedAdjustRate: 0` 时，`ADJUST_RATE` 和 `PREDICATE_ADJUST_RATE` 从统计文件中读取，手动设置无效
- STATS benchmark 对应 `stats.db`；JOBM/JOBLight 对应 `imdb.db`
- **config.json 会被实验框架（EvaluatePerformanceBreakdown 等 notebook）频繁覆盖**，每次跑前先 `cat config.json` 确认内容正确
- **query_idx 是 1-indexed**，报告中的 Q59 对应 `queries.sql` 第 59 行（`sed -n '59p'`）
- running_space 里单次执行时间（~100ms 量级）与实验框架测出的时间（秒级）差距巨大，是因为实验框架每条查询独立启动进程（无 page cache 预热），running_space 里连续跑有缓存。**两者不可直接比较**，要对比两个方案的相对差异需在同等条件下跑

---

## 误差分析工作流（针对特定查询）

当发现某条查询性能异常时，推荐以下步骤：

### 1. 确认查询内容

```bash
# query_idx=59 对应第 60 行
sed -n '60p' /path/to/queries.sql
```

### 2. 用 RecordingSubquery 记录 StarCE 的子查询估计

```json
"RecordingSubquery": 1,
"SQL_PATH": "explain_q59.sql",          // 必须是 EXPLAIN 版本
"SUBQUERY_RESULT_PATH": "q59_starce_cards.txt"
```

运行后 `q59_starce_cards.txt` 前半部分是估计值，后半部分是对应 SQL。

### 3. 对比真实基数

用 duckdb 跑每条子查询的真实基数，与 StarCE 估计对比，找出 Q-Error 最大的子查询。

### 4. 注入真实基数看最优计划

```json
"UseSubqueryCard": 1,
"UseSingleTableCard": 0,
"SUBQUERY_PATH": "...",        // 行数必须与 real.txt 一致
"SUBQUERY_RESULT_PATH": "..."  // real.txt
```

先跑 EXPLAIN 对比两个计划的结构差异，再执行确认时间差。
