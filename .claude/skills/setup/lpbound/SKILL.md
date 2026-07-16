---
name: lpbound-env
description: LpBound 复现环境搭建完整指南：conda 环境、CSV 数据、DuckDB 数据库、统计预计算、C++ 求解器编译。当用户提到 LpBound 环境搭建、初始化、setup 时使用。
---

# LpBound 复现环境搭建

LpBound 使用独立的 conda 环境 `lpbound`（Python 3.12，DuckDB 0.10.1），与项目主环境 TestEnv（DuckDB 1.5.2）**不兼容**。DuckDB 数据库文件互不通用，LpBound 必须自行从 CSV 建库。

## 1. Conda 环境

```bash
# 从快照恢复
conda env create -f setup/lpbound/environment.yml
conda activate lpbound
```

核心依赖：

| 包 | 版本 | 用途 |
|----|------|------|
| python | 3.12.13 | |
| duckdb | 0.10.1 | 统计信息存储和查询 |
| ortools | 9.14.6206 | Python 版 LP 求解器 |
| pandas | 2.3.2 | 数据处理 |
| numpy | 2.3.2 | 数值计算 |
| tqdm | 4.67.1 | 进度条 |
| cython | 3.1.3 | C++ LpFlow 扩展编译 |
| poetry | 2.4.1 | 包管理（源码安装 lpbound） |

环境快照文件：[`environment.yml`](environment.yml)

## 2. CSV 数据准备

### IMDB

从 `Benchmark/IMDB/` 建立符号链接：

```bash
mkdir -p methods/LpBound/data/datasets/imdb
for f in Benchmark/IMDB/*.csv; do
    ln -sf "$(realpath $f)" "methods/LpBound/data/datasets/imdb/$(basename $f)"
done
```

### STATS

```bash
mkdir -p methods/LpBound/data/datasets/stats
for f in methods/SafeBound/Data/Stats/*.csv; do
    cp "$f" "methods/LpBound/data/datasets/stats/$(basename $f)"
done
```

### 大小写符号链接

LpBound 代码强制将表名转为小写来查找 CSV（如 `postLinks` → `postlinks.csv`），必须创建小写符号链接：

```bash
cd methods/LpBound/data/datasets/stats
for f in *.csv; do
    lower=$(echo "$f" | tr '[:upper:]' '[:lower:]')
    [ "$f" != "$lower" ] && ln -sf "$f" "$lower"
done
cd methods/LpBound/data/datasets/imdb
for f in *.csv; do
    lower=$(echo "$f" | tr '[:upper:]' '[:lower:]')
    [ "$f" != "$lower" ] && ln -sf "$f" "$lower"
done
```

## 3. DuckDB 数据库与统计预计算

LpBound 的数据库管理和统计生成为自动化流程：

| 步骤 | 函数 | 说明 |
|------|------|------|
| 建库 + 导入 CSV | `DatabaseManager.create_or_load_db()` | 首次运行时自动建表、导数据、建 FK 索引 |
| 统计预计算 | `build_lpbound_statistics(config)` | 生成 MCV 表、直方图表、度序列聚合，写入 `norms` 表 |

可交互式逐一完成，也可一键构建所有 benchmark：

```bash
conda activate lpbound
python3 -c "
from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.acyclic.lpbound import build_lpbound_statistics

# 使用 LpBound 自身默认参数 (p_max=10, include_l0=True, include_l_inf=True)
for benchmark in ['stats', 'joblight', 'jobrange', 'jobjoin']:
    cfg = LpBoundConfig(benchmark_name=benchmark)
    build_lpbound_statistics(cfg)
    print(f'{benchmark}: done')
"
```

**耗时参考**（默认参数，实测）：

| Benchmark | 表数 | 耗时 (L1) | 耗时 (All) | DB 文件 |
|-----------|------|-----------|------------|---------|
| stats | 8 | ~14s | ~16s | `stats_duckdb.db` |
| joblight | 6 | ~9s | ~13s | `joblight_duckdb.db` |
| jobrange | 8 | ~31s | ~38s | `jobrange_duckdb.db` |
| jobjoin | 21 | ~5s | ~9s | `imdb_duckdb.db` |

所有 `.db` 文件位于 `methods/LpBound/data/duckdb/`。

## 4. C++ 求解器

C++ 版求解器（用于估计时间测量）依赖 HiGHS 线性规划库。

### 4.1 编译

需要 HiGHS 线性规划库和 nlohmann/json 头文件库：

```bash
cd methods/LpBound/src/lpbound/cpp_solver

# 克隆依赖
git clone https://github.com/ERGO-Code/HiGHS.git --depth 1
git clone https://github.com/nlohmann/json.git

# 编译 C++ solver
cd lpbound_parallel
bash compile.sh
```

编译产物：`build/lpbound_parallel`

### 4.2 输入数据准备

C++ 求解器需要 LP 约束 JSON 文件（`input_data/{benchmark}/`），由预构建的 LP dump 转换而来：

```bash
cd methods/LpBound/src/lpbound/cpp_solver/lpbound_parallel

# 解压预构建的 LP dump（提取后移入 raw_input/）
unzip raw_input.zip
mkdir -p raw_input
mv jobjoin_subqueries joblight_subqueries jobrange_subqueries stats_subqueries raw_input/

# 生成 JSON 输入数据（从 raw_input LP dump 转换）
conda activate lpbound
python create_input_files.py
```

> **说明**：`raw_input.zip` 中的 LP dump 是上游作者用他们预计算的 norms 表生成的。这些 JSON 仅用于 C++ solver 的 **timing 测量**。要获得基于**当前 norms 表的估计值**，需运行 Python `estimate()`（见步骤 4.3 的 accuracy 流程）。

### 4.3 精度实验（获取基数估计值）

按 README Section 6.2 运行 `accuracy_acyclic.py`，用当前 norms 表产生实际估计值：

```bash
cd methods/LpBound
conda activate lpbound
python benchmarks/experiments/accuracy_acyclic.py lpbound
```

结果写入 `results/accuracy_acyclic/{benchmark}/lpbound_{benchmark}_full_estimations.csv`，可对比 `truecardinality_*_full_estimations.csv` 计算误差。

### 4.4 性能实验（测 estimate time）

按 README Section 6.3，用 C++ solver 测 LP 求解耗时：

```bash
cd methods/LpBound
conda activate lpbound
python benchmarks/experiments/estimation_time.py
```

此脚本调用 C++ `lpbound_parallel`，分别跑 sequential 和 parallel 模式，结果写入 `results/estimation_time/raw_results/`。

per-subquery 平均耗时（实测）：
- sequential: ~0.06-0.15ms
- parallel: ~0.2-7.6ms（同一查询的所有子查询并行求解）

## 5. 路径映射

`paths.py` 中的映射关系：

```
benchmark → db_name (WORKLOAD_TO_DB_MAP):
  jobjoin → imdb            (全量 IMDB, 21 表)
  joblight → joblight       (JOBLight, 6 表)
  jobrange → jobrange       (JOBRange, 含范围谓词)
  stats → stats             (STATS-CEB, 8 表)

db_name → csv_dir (CSV_DATA_DIR_MAP):
  imdb → imdb
  joblight → imdb           (也从 IMDB CSV 读取)
  jobrange → imdb
  stats → stats
```

DB 文件：`methods/LpBound/data/duckdb/{db_name}_duckdb.db`

## 6. TestLpBound 运行

环境就绪后：

```bash
cd experiment
conda activate TestEnv          # 当前项目环境
python TestLpBound.py           # Build + Estimate
python TestLpBound.py --build-only
python TestLpBound.py --est-only
```

脚本内部通过 `conda run -n lpbound` 调用 LpBound 环境，无需手动切换。
