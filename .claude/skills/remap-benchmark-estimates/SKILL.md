---
name: remap-benchmark-estimates
description: 将 End-to-End-CardEst-Benchmark 中的外部基数估计结果（flat/bayescard/deepdb/neurocard）按规范化签名映射到 Benchmark/workloads/ 目录格式，支持 STATS-CEB 和 JOBLight。当用户提到映射 FLAT 估计、导入外部方法结果、对照实验估计、benchmark 估计文件时使用。
---

# 外部基准估计结果映射

## 概述

`scripts/remap/map_benchmark_estimates.py` 将 `Stats-CEB/End-to-End-CardEst-Benchmark` 中的预计算估计结果映射到项目 `Benchmark/` 目录的标准格式。

支持的方法：flat、bayescard、deepdb、neurocard（共 4 个）。

支持的数据集：STATS-CEB（2471 条）、JOBLight（451 条）。

## 映射原理

1. **SQL 规范化**：表名按字典序排序，join 条件通过 Union-Find 建立等价类，每类用字典序最前的列做锚点生成最小不冗余 join，filter 按字典序排序
2. **桥接表推断**：直接匹配不成功时，根据 join 列名推断桥接表（STATS: userid→users, postid→posts; JOBLight: movie_id→title），添加桥接表后重新匹配
3. 签名 = `(sorted_tables, canonical_joins, sorted_filters)` 精确匹配

## 用法

```bash
# 在项目根目录下运行
python scripts/remap/map_benchmark_estimates.py
```

## 数据流

```
Stats-CEB/End-to-End-CardEst-Benchmark/workloads/
├── stats_CEB/sub_plan_queries/
│   ├── stats_CEB_sub_queries.sql          # 2603 条 SP 查询 (SQL||index 格式)
│   └── estimates/
│       ├── stats_CEB_sub_queries_flat.txt
│       ├── stats_CEB_sub_queries_bayescard.txt
│       ├── stats_CEB_sub_queries_deepdb.txt
│       └── stats_CEB_sub_queries_neurocard.txt
└── job-light/sub_plan_queries/
    ├── job_light_sub_query.sql             # 696 条 SP 查询
    └── estimates/
        ├── job_light_sub_queries_flat.txt
        ├── job_light_sub_queries_bayescard.txt
        ├── job_light_sub_queries_deepdb.txt
        └── job_light_sub_queries_neurocard.txt

        ↓ 映射 ↓

Benchmark/workloads/
├── STATS-CEB/subquery/result/{flat,bayescard,deepdb,neurocard}.txt  # 各 2471 行
└── JOBLight/subquery/result/{flat,bayescard,deepdb,neurocard}.txt   # 各 451 行
```

## 注意事项

- SP 查询文件 `stats_CEB_sub_queries.sql` 是原始 `SQL||index` 格式（无 `{aliases}` 前缀）
- deepdb 和 neurocard 的 SP 签名内存在估计值冲突（同一规范化查询对应多个不同值），脚本取第一个
- 映射覆盖率为 100%，无需人工处理
