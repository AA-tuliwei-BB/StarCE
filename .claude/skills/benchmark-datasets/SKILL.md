---
name: benchmark-datasets
description: 基准数据集（STATS、IMDB/JOB）的目录位置、结构、表定义、数据文件和查询工作集说明。在 methods/SafeBound 和 benchmark/workloads 等位置。包含数据加载脚本、Schema 文件、CSV 数据文件和查询集合。适用于定位数据集、理解基准数据库结构、查看样例查询、运行基准实验时。
---

# 基准数据集

## 快速定位

项目中包含多个基准数据集，主要位置：

| 数据集 | 路径 | 用途 |
|--------|------|------|
| STATS | `methods/SafeBound/Data/Stats/` 或 `benchmark/workloads/stats-ceb/` | Stack Overflow 数据集，用于 STATS-CEB 基准 |
| IMDB/JOB | `methods/SafeBound/Data/IMDB/` | 互联网电影数据库，用于 JOB/JOBLight 基准 |
| Workloads | `methods/SafeBound/Workloads/` | SafeBound 方法的查询集合 |

## STATS 数据集

### 路径
`methods/SafeBound/Data/Stats/` 或 `benchmark/workloads/stats-ceb/`

### 表结构
Stack Overflow 数据集包含 7 个主要表：

- **users**: 用户信息（Id, Reputation, CreationDate, Views, UpVotes, DownVotes）
- **posts**: 帖子（Id, PostTypeId, CreationDate, Score, ViewCount, OwnerUserId, AnswerCount, CommentCount, FavoriteCount）
- **comments**: 评论（与 posts/users 关联）
- **badges**: 徽章（与 users 关联）
- **postHistory**: 帖子历史（与 posts 关联）
- **postLinks**: 帖子链接（PostId, RelatedPostId）
- **votes**: 投票

### 数据文件
CSV 格式数据文件：
- `users.csv`
- `posts.csv`
- `comments.csv`
- `badges.csv`
- `postHistory.csv`
- `postLinks.csv`
- `votes.csv`
- `tags.csv`

### 加载脚本
- `stats.sql`: 创建表定义
- `stats_load.sql`: 加载数据（\copy 命令）
- `stats_index.sql`: 创建索引

## IMDB 数据集（JOB/JOBLight）

### 路径
`methods/SafeBound/Data/IMDB/`

### 表结构
IMDB 数据集包含 21+ 个表，主要表：

- **title**: 电影标题（id, production_year）
- **movie_info**: 电影信息（movie_id, info_type_id）
- **movie_info_idx**: 电影信息索引（movie_id, info_type_id）
- **movie_keyword**: 电影关键字（movie_id, keyword_id）
- **movie_companies**: 电影公司（movie_id, company_type_id）
- **cast_info**: 演员信息（movie_id, person_id, role_id）
- **aka_name**, **aka_title**, **char_name**, **name**: 别名和名字表
- **company_name**, **keyword**, **kind_type**, **link_type**, **role_type**: 参考表

### 子集变体
IMDB 有多个基于 JOB (Job-light) 的变体：
- `CreateJOBLightDB.sql`: JOBLight 子集
- `CreateJOBLightRangesDB.sql`: JOBLight with ranges 子集
- `CreateJOBMDB.sql`: JOBM 子集

### 数据加载
- `imdb_create.sql`: 创建所有表
- 数据文件位于 `Data/IMDB/` 中（CSV 格式）

## Workloads 查询集合

### SafeBound Workloads
位置: `methods/SafeBound/Workloads/`

#### STATS 查询集合
- `StatsQueries.sql`: 基础 STATS 查询集（~150 条多表 Join 查询）
- `StatsSubQueriesBayes.sql`: STATS 子查询集合
- 样例查询包含多表 Join、复杂谓词和日期范围过滤

#### JOB 查询集合
| 文件 | 用途 |
|------|------|
| `JOBLightQueries.sql` | JOBLight 基准查询 |
| `JOBLightRangesQueries.sql` | JOBLight with ranges 查询 |
| `JOBMQueries.sql` | JOBM (full JOB) 查询 |
| `JOBQueries.sql` | 完整 JOB 查询集 |

### 查询特点
- 每行一条 SQL 查询
- 包含多表 Join（2-5 个表）
- 包含选择谓词（=, <, >, BETWEEN）
- 大部分是 SELECT * 查询（用于计算真实基数）

## 结果目录

### 位置
`methods/SafeBound/Data/Results/`

### 文件说明
- `Stats_Sizes.csv`: STATS 查询真实基数和各估计器预测结果
- `JOBLight_Sizes.csv`: JOBLight 查询结果
- `JOBLightRanges_Sizes.csv`: JOBLightRanges 查询结果
- `JOBM_Sizes.csv`: JOBM 查询结果
- `Postgres_Inference_Stats_subquery.csv`: PostgreSQL 推断结果

## 使用示例

### 加载 STATS 数据集到 PostgreSQL
```sql
-- 1. 创建表
psql -f methods/SafeBound/Data/Stats/stats.sql

-- 2. 加载数据
psql -f methods/SafeBound/Data/Stats/stats_load.sql

-- 3. 创建索引
psql -f methods/SafeBound/Data/Stats/stats_index.sql
```

### 查看样例查询
```bash
# 查看前 10 条 STATS 查询
head -10 methods/SafeBound/Workloads/StatsQueries.sql

# 查看 JOBLight 查询
head -10 methods/SafeBound/Workloads/JOBLightQueries.sql
```

## 相关方法和工具

- `methods/SafeBound/README.md`: SafeBound 使用说明和参数详解
- `methods/SafeBound/run_experiment.py`: SafeBound 实验运行脚本
- `methods/SafeBound/checkpoints/`: 预训练模型和缓存数据
  - `stats_hdf/`: STATS 数据集 HDF5 缓存
  - `stats_models/`: STATS 已训练 Bayesian 网络模型

## 实验规范

当运行基准实验时，确保：
1. 数据文件路径相对于项目根目录
2. 使用对应的 workload 文件（StatsQueries.sql 配合 STATS 数据）
3. 结果文件与对应的结果目录格式对应

## 更多信息

- 详见 `methods/SafeBound/README.md`
- 各 workload 格式标准见相关技能文档
