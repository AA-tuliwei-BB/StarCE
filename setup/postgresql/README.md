# PostgreSQL 环境搭建

## 1. 前置条件

```bash
sudo apt-get install build-essential flex bison libreadline-dev
```

## 2. 安装 PostgreSQL 13.1

端对端基数注入测试需要一份修改过源码的 PG。源码位于仓库内：

```bash
cd Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1

# 首次编译
./configure --prefix=/usr/local/pgsql/13.1

# 编译并安装
make -j4
cd src/backend
sudo make install
```

> 如果不需要基数注入功能，可直接使用系统包管理安装的 PG 13.x。

## 3. 初始化与配置

```bash
# 初始化数据目录
/usr/local/pgsql/13.1/bin/initdb -D <PGDATA>
```

修改 `<PGDATA>/postgresql.conf`：

```ini
# 性能参数
shared_buffers = 4GB
work_mem = 2GB
effective_cache_size = 32GB
max_parallel_workers = 6
max_parallel_workers_per_gather = 6

# pg_hint_plan 预加载
shared_preload_libraries = 'pg_hint_plan'
dynamic_library_path = '$libdir:<PROJECT_ROOT>/methods/SafeBound/lib'
```

修改 `<PGDATA>/pg_hba.conf`，添加 trust 认证：

```
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
```

## 4. 启动 PostgreSQL

```bash
/usr/local/pgsql/13.1/bin/pg_ctl start -D <PGDATA>
```

## 5. 创建数据库

确保 PG 已启动且数据已初始化：

```bash
# 先初始化数据集
bash setup/dataset/init_stats.sh
bash setup/dataset/init_imdb.sh

# 创建 PG 数据库
bash setup/postgresql/create_stats_db.sh
bash setup/postgresql/create_imdb_db.sh
```

创建的数据库：

| 数据库 | 表数 | 说明 |
|--------|------|------|
| stats | 8 | STATS-CEB，Stack Overflow 数据 |
| imdb | 21 | 完整 IMDB |
| imdblight | 6 | JOBLight 子集 |
| imdblightranges | 6 | JOBLightRanges 子集 |
| imdbm | 17 | JOBM 子集 |

## 6. pg_hint_plan

pg_hint_plan 用于 SafeBound 端对端测试中的 Rows hint 注入。

- 共享库位置：`methods/SafeBound/lib/pg_hint_plan.so`
- 通过 `shared_preload_libraries = 'pg_hint_plan'` 预加载

## 7. 基数注入钩子（可选）

源码修改位于 `Stats-CEB/End-to-End-CardEst-Benchmark/postgresql-13.1/`，已包含注入逻辑。

注册的 GUC 变量：

| 变量 | 类型 | 说明 |
|------|------|------|
| `ml_joinest_enabled` | bool | 启用 join 基数注入 |
| `ml_joinest_fname` | string | 估计文件名（PGDATA 下） |
| `ml_cardest_enabled` | bool | 启用单表基数注入 |
| `ml_cardest_fname` | string | 单表估计文件名 |
| `print_sub_queries` | bool | 打印子查询 |
| `query_no` | int | 当前查询编号 |

完整注入流程见 [pg-end2end skill](../.claude/skills/pg-end2end/SKILL.md) 和 `experiment/pg_end2end/pgsql-setup.md`。

## 8. 验证

```bash
psql -U postgres -c "SELECT datname FROM pg_database WHERE datname LIKE 'imdb%' OR datname = 'stats';"
psql -U postgres -d stats -c "\dt"
psql -U postgres -d imdb -c "SELECT count(*) FROM title;"
```

## 9. 常见问题

**PG 启动失败：端口被占用**
```bash
ps aux | grep postgres
# 或修改 postgresql.conf 中的 port
```

**pg_hint_plan 加载失败**
```bash
# 检查 .so 文件是否存在
ls methods/SafeBound/lib/pg_hint_plan.so
# 检查 PG 日志
tail -f <PGDATA>/logfile
```

**IMDB 变种创建失败**
确保 imdb 全量库已创建且可连接，变种通过 `CREATE DATABASE ... TEMPLATE imdb` 方式生成。

**IMDB CSV 导入报 `extra data after last expected column`**
IMDB CSV 使用反斜杠转义引号（`\"`），PostgreSQL 默认 CSV 模式 ESCAPE 与 QUOTE 相同（均为 `"`），不识别 `\` 转义。修复：COPY 命令添加 `ESCAPE '\'`。
`create_imdb_db.sh` 已经包含此修复。若手动导入 CSV，需使用：
```sql
\copy table_name FROM 'file.csv' WITH CSV DELIMITER ',' ESCAPE '\';
```
