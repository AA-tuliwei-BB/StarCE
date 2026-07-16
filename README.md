# StarCE

基于 DuckDB 的基数估计系统，使用度序列统计（Degree Sequence Statistics）对 Join 查询进行基数估计。

## 快速开始

```bash
# 1. 环境
conda env create -f setup/conda/environment.yml
conda activate TestEnv

# 2. 数据
bash setup/dataset/init_stats.sh
bash setup/dataset/init_imdb.sh

# 3. 编译
./build.sh

# 4. 创建 DuckDB 数据库
bash setup/duckdb/create_stats_db.sh
bash setup/duckdb/create_imdb_db.sh
```

完整环境搭建（含 PostgreSQL）见 [setup/README.md](setup/README.md)。

## 项目结构

```
├── main.cpp                      # StarCE 入口：统计收集 + SQL 执行
├── duckdb/                       # DuckDB 源码 + StarCE 扩展头文件
│   └── src/include/duckdb/starce/
│       ├── starce.hpp            # StatisticManager（核心估计逻辑）
│       ├── statistic.hpp         # DSStatistic、DegreeSequence
│       └── equalset.hpp          # EqualSet 定义与序列化
├── methods/
│   ├── FactorJoin/               # FactorJoin 方法
│   ├── SafeBound/                # SafeBound 方法
│   └── LpBound/                  # LpBound 方法
├── experiment/                   # 实验脚本和 Notebook
├── Benchmark/                    # 基准数据集和 Workload
│   ├── STATS/                    # STATS-CEB 数据 (8 表)
│   ├── IMDB/                     # IMDB 数据 (21 表)
│   └── workloads/                # 查询 Workload
└── setup/                        # 统一环境搭建指南
```

## 数据集

| 数据集 | 表数 | 大小 | 说明 |
|--------|------|------|------|
| STATS-CEB | 8 | ~39 MB | Stack Overflow 数据，仓库已有 |
| IMDB | 21 | ~4.8 GB | Internet Movie Database，需下载 |
| JOBLight | 6 | IMDB 子集 | 仅 6 张核心表 |
| JOBLightRanges | 6 | IMDB 子集 | JOBLight + Range 谓词 |
| JOBM | 17 | IMDB 子集 | 去掉 4 张宽表 |

## 外部方法

| 方法 | 说明 |
|------|------|
| FactorJoin | 贝叶斯网络 + 采样基数估计 |
| SafeBound | 安全界限基数估计 |
| LpBound | 线性规划界限估计 |
| FLAT / FSPN | Factorized Sum-Product Network |
| DeepDB / BayesCard | 深度学习基数估计 |
| NeuroCard | 神经基数估计 |

## 编译

```bash
./build.sh          # release 模式 → build/starce
./build.sh debug    # debug 模式 → build-debug/starce
```

## 实验

```bash
cd experiment
python ExperimentRunner.py
```

详细实验流程、配置文件、评估方法见 Claude Code skills（`/experiment-workflow`、`/starce-usage` 等）。
