---
name: postgresql-env
description: StarCE 项目的 PostgreSQL 数据库环境配置信息：数据目录、连接参数、已有数据库（stats/imdb/imdblight/imdbm）、表结构和数据文件位置。当用户提到数据库连接、PostgreSQL、psql、数据库表结构时使用。
---

# StarCE PostgreSQL 环境配置

## 快速参考

### 基本连接信息

```bash
# 数据目录
PGDATA=/mnt/sdb1/tlw/pgdata

# psql 路径
/usr/local/pgsql/13.1/bin/psql

# PostgreSQL 版本
13.1

# 连接示例
PGDATA=/mnt/sdb1/tlw/pgdata /usr/local/pgsql/13.1/bin/psql -d stats
```

### 已有数据库

| 数据库 | Owner | 用途 | 表数量 | 对应 Benchmark |
|--------|-------|------|--------|---------------|
| `stats` | postgres | STATS-CEB 数据 | 8 | STATS-CEB |
| `imdb` | postgres | 完整 IMDB 数据 | 21+ | IMDB-JOB |
| `imdblight` | liwei | JOBLight 子集 | 6 | JOBLight |
| `imdbm` | liwei | JOBM 子集 | 17 | JOBM |

## 数据库详情

### stats 数据库

**用途**: Stack Overflow 数据集，用于 STATS-CEB benchmark

**表结构**:
```
badges      (79,851 行)
comments    (174,305 行)
posthistory (303,187 行)
postlinks   (11,102 行)
posts       (91,976 行)
tags        (1,032 行)
users       (40,325 行)
votes       (328,064 行)
```

**数据文件位置**: `methods/SafeBound/Data/Stats/*.csv`

**连接示例**:
```bash
PGDATA=/mnt/sdb1/tlw/pgdata /usr/local/pgsql/13.1/bin/psql -d stats -c "\dt"
```

### imdblight 数据库

**用途**: JOBLight benchmark（IMDB 最小子集）

**表结构**:
```
cast_info       (36,244,344 行)
movie_companies (2,609,129 行)
movie_info      (14,835,720 行)
movie_info_idx  (1,380,035 行)
movie_keyword   (4,523,930 行)
title           (2,528,312 行)
```

**特点**: 删除了大部分参考表和字符串列

**创建脚本**: `methods/SafeBound/Data/IMDB/CreateJOBLightDB.sql`

### imdbm 数据库

**用途**: JOBM benchmark（IMDB 中等子集）

**表结构** (17 表):
```
aka_title       cast_info       char_name       
comp_cast_type  company_name    company_type    
complete_cast   info_type       keyword         
kind_type       link_type       movie_companies 
movie_info      movie_info_idx  movie_keyword   
movie_link      title
```

**删除的表**: name, person_info, role_type, aka_name

**创建脚本**: `methods/SafeBound/Data/IMDB/CreateJOBMDB.sql`

### imdb 数据库

**用途**: 完整 IMDB 数据集

**表数量**: 21+ 表（包含所有电影、演员、公司等信息）

**数据文件位置**: `methods/SafeBound/Data/IMDB/*.csv`

### PG 配置参数

```bash
# 查看当前配置
/usr/local/pgsql/13.1/bin/psql -U postgres -c "SHOW shared_buffers;"
/usr/local/pgsql/13.1/bin/psql -U postgres -c "SHOW max_parallel_workers_per_gather;"

# 设置配置（需要重启生效的用 ALTER SYSTEM + restart）
/usr/local/pgsql/13.1/bin/psql -U postgres -c "ALTER SYSTEM SET max_parallel_workers_per_gather = 6;"
/usr/local/pgsql/13.1/bin/psql -U postgres -c "SELECT pg_reload_conf();"
```

**关键参数**（SafeBound 推荐 + 本项目调优）:

| 参数 | 值 | 说明 |
|------|-----|------|
| `shared_buffers` | 4GB | |
| `work_mem` | 2GB | |
| `effective_cache_size` | 32GB | |
| `max_parallel_workers_per_gather` | 6 | 并行查询 worker 数，影响执行计划选择 |
| `random_page_cost` | 默认 | |
| `seq_page_cost` | 默认 | |

## 常用操作

### 列出所有数据库

```bash
PGDATA=/mnt/sdb1/tlw/pgdata /usr/local/pgsql/13.1/bin/psql -l
```

### 查看表结构

```bash
# 查看 stats 数据库的表
psql -d stats -c "\dt"

# 查看表详细信息
psql -d stats -c "\d+ badges"

# 统计行数
psql -d stats -c "SELECT COUNT(*) FROM badges;"
```

### 执行查询

```bash
# 单条查询
psql -d stats -c "SELECT COUNT(*) FROM badges WHERE Date >= '2014-01-01'::timestamp;"

# 执行 SQL 文件
psql -d stats -f query.sql

# 输出为 CSV
psql -d stats -c "SELECT * FROM badges LIMIT 10;" --csv
```

### 数据导入/导出

```bash
# 导出数据
psql -d stats -c "COPY badges TO '/path/to/badges.csv' CSV HEADER;"

# 导入数据
psql -d stats -c "COPY badges FROM '/path/to/badges.csv' CSV HEADER;"
```

## 数据集文件位置

### STATS 数据集

```
methods/SafeBound/Data/Stats/
├── badges.csv        (2.4M, 79,852 行)
├── comments.csv      (6.6M, 174,306 行)
├── postHistory.csv   (12M, 303,188 行)
├── postLinks.csv     (452K, 11,103 行)
├── posts.csv         (4.0M, 91,977 行)
├── tags.csv          (12K, 1,033 行)
├── users.csv         (1.4M, 40,326 行)
└── votes.csv         (12M, 328,065 行)
```

**加载脚本**:
- `stats.sql` - 创建表定义
- `stats_load.sql` - 加载数据
- `stats_index.sql` - 创建索引

### IMDB 数据集

```
methods/SafeBound/Data/IMDB/
├── title.csv              (307M)
├── cast_info.csv          (1.4G)
├── movie_companies.csv    (89M)
├── movie_info.csv         (920M)
├── movie_info_idx.csv     (34M)
├── movie_keyword.csv      (90M)
├── company_name.csv       (17M)
├── keyword.csv            (3.7M)
└── ... (其他参考表)
```

**数据库创建脚本**:
- `imdb_create.sql` - 创建完整 IMDB 表
- `CreateJOBLightDB.sql` - 从 imdb 创建 imdblight
- `CreateJOBMDB.sql` - 从 imdb 创建 imdbm

## 连接字符串格式

### Python psycopg2

```python
import psycopg2

# 基本连接
conn = psycopg2.connect(
    dbname="stats",
    user="postgres",
    host="localhost",
    port=5432
)

# 使用连接字符串
conn_str = "dbname=stats user=postgres host=localhost port=5432"
conn = psycopg2.connect(conn_str)
```

### FactorJoin 格式

```bash
# STATS (不需要数据库连接)
--data_path ../../methods/SafeBound/Data/Stats/{}.csv

# IMDB 采样模式（需要数据库）
--db_conn_kwargs "dbname=imdbm user=liwei host=localhost port=5432"
```

### SafeBound 格式

查看 `methods/SafeBound/` 中的具体配置

## 环境变量

```bash
# 设置 PGDATA（如果需要）
export PGDATA=/mnt/sdb1/tlw/pgdata

# 添加 psql 到 PATH
export PATH=/usr/local/pgsql/13.1/bin:$PATH

# 设置默认用户
export PGUSER=liwei
```

## 故障排查

### 连接失败

```bash
# 检查 PostgreSQL 是否运行
ps aux | grep postgres

# 检查进程
pgrep -a postgres

# 查看数据目录
ls -la /mnt/sdb1/tlw/pgdata
```

### 权限问题

```bash
# 检查用户权限
psql -d postgres -c "\du"

# 检查数据库所有者
psql -l
```

### 端口占用

```bash
# 检查端口 5432
netstat -tulpn | grep 5432
# 或
ss -tulpn | grep 5432
```

## Benchmark 与数据库对应

| Benchmark | 数据库 | 子查询文件 | 行数 |
|-----------|--------|-----------|------|
| STATS-CEB | `stats` | `benchmark/stats-ceb/subquery/subquery.sql` | 2471 |
| JOBM | `imdbm` | `benchmark/jobm/subqueries/subquery.sql` | 6424 |
| JOBLight | `imdblight` | `Benchmark/workloads/JOBLight/subquery/subquery.sql` | 451 |

## 相关 Skills

- [factorjoin-usage](../factorjoin-usage/SKILL.md) - FactorJoin 使用需要这些数据库
- [starce-usage](../starce-usage/SKILL.md) - StarCE 使用需要这些数据库
