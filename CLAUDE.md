# StarCE 项目 Claude Code 配置

> 此文件为项目级别的配置，对所有 Claude Code 会话生效。  
> 从 Cursor 项目配置迁移而来。

## 🔴 重要规则（必读）

**以下规则对所有会话生效，违反会导致工作效率降低：**

1. **拒绝表面修复**：不要仅修复症状，要找出根本原因并报告
2. **不擅自改 Git**：任何 git 操作（commit/push/merge）都需要显式确认
3. **直接反馈而非文档**：不要生成报告文档，在对话框中直接回复问题
4. **避免 workaround**：不使用 workaround 或 fallback 方案，如有需要必须与用户确认
5. **代码格式规范**：空行中不含空格或缩进符
6. **语言**：始终使用简体中文回复
7. **禁止覆盖 Benchmark 文件**：`RecordingSubquery=1` 会覆盖 `SUBQUERY_PATH` 指向的文件。使用时必须将 `SUBQUERY_PATH` 改为 running_space 内的临时文件（如 `q59_subqueries.sql`），禁止指向 `Benchmark/` 目录下的任何文件
8. **如何表示一个查询**：不要使用并不靠谱的Qxx来表示某个查询，容易出现0-idx和1-idx混淆。当提到 Qxx 时，必须先明确其编号基准（0-indexed 还是 1-indexed），并用对应行的 SQL 内容验证。在报告等位置需要提及某个查询的时候，一定要带上完整的查询 SQL，以免混淆。例如：`sed -n '58p' queries.sql` 对应 0-indexed query_id=57。
9. **本项目使用 Relative Error 而非 Q-Error**：评估指标为 `max(1, est) / max(1, true)`（有符号相对误差），不是标准 Q-Error（`max(est/true, true/est)`）。两者语义不同：Relative Error 低估时为 <1（log10 为负），高估时为 >1（log10 为正）；Q-Error 始终 >=1。代码中变量名 `qerror`/`q_err` 是误用，实际语义是 Relative Error。读取或编写评估代码时需注意此区别，勿混淆。

更多详情见 [`.claude/important-things.mdc`](.claude/important-things.mdc)

---

## 🛠️ 环境配置

### Python 环境

**当前项目使用 TestEnv conda 环境：**
- **环境名称**：TestEnv
- **Python 版本**：3.10.4
- **激活命令**：`conda activate TestEnv`

### 核心依赖

| 类别 | 主要包 |
|------|--------|
| **数值计算** | NumPy 1.22.0, Pandas 1.5.3, SciPy 1.7.3 |
| **机器学习** | PyTorch 2.10.0 (CUDA 12.8), XGBoost 3.1.3, Scikit-learn 1.1.2 |
| **贝叶斯网络** | pgmpy 0.1.26, pomegranate 0.14.3, pyro-ppl 1.9.1 |
| **数据库** | psycopg2 2.8.6 (PostgreSQL) |
| **数据处理** | HDF5 支持 (tables 3.10.1) |

激活环境：
```bash
conda activate TestEnv
```

完整详情见 [`.claude/testenv-python-environment.mdc`](.claude/testenv-python-environment.mdc)

---

## 📚 项目 Skills 导航

> 这些 skills 提供项目的专业知识和工作流程指导。当涉及相关主题时，会自动加载对应 skill。

### 核心工作流程

| Skill | 描述 | 何时使用 |
|-------|------|----------|
| [experiment-workflow](./claude/skills/experiment-workflow/SKILL.md) | 实验流程总览、ExperimentRunner 驱动逻辑、基数收集和分析流程 | 讨论实验设计、如何运行测试、结果分析时 |
| [python-env](./claude/skills/python-env/SKILL.md) | Python 环境配置、各方法的环境要求、虚拟环境设置 | 环境问题、依赖安装、版本兼容性时 |
| [postgresql-env](./claude/skills/postgresql-env/SKILL.md) | PostgreSQL 连接配置、数据库设置 | 需要连接 PG 数据库时 |
| [setup](./claude/skills/setup/SKILL.md) | 统一环境搭建：conda 环境、数据集获取、PostgreSQL 配置、DuckDB 编译与数据库创建 | 初始化项目、从零配置环境、获取数据集时 |

### 主要方法文档

| Skill | 描述 | 何时使用 |
|-------|------|----------|
| [starce-overview](./claude/skills/starce-overview/SKILL.md) | StarCE 系统总览、核心特性、项目结构 | 了解 StarCE 整体架构时 |
| [starce-usage](./claude/skills/starce-usage/SKILL.md) | StarCE 使用指南、参数配置、二进制操作 | 运行或配置 StarCE 时 |
| [factorjoin-usage](./claude/skills/factorjoin-usage/SKILL.md) | FactorJoin 两种工作模式（BN/采样）、训练评估流程 | 处理 FactorJoin 基数估计时 |
| [factorjoin-jobm-sampling](./claude/skills/factorjoin-jobm-sampling/SKILL.md) | FactorJoin JOBM 采样模式的具体实现细节 | 优化 FactorJoin 采样性能时 |
| [fspn-usage](./claude/skills/fspn-usage/SKILL.md) | FSPN 架构原理、节点类型、学习算法、推理模式 | 了解或使用 FSPN 基数估计时 |
| [safebound-runtime](./claude/skills/safebound-runtime/SKILL.md) | SafeBound Runtime 实验流水线 | 运行 SafeBound 实验时 |

### 数据和工具

| Skill | 描述 | 何时使用 |
|-------|------|----------|
| [benchmark-datasets](./claude/skills/benchmark-datasets/SKILL.md) | 基准数据集详情、STATS-CEB/JOBM/JOBLight 的特点 | 选择或理解数据集时 |
| [workload-file-formats](./claude/skills/workload-file-formats/SKILL.md) | SQL 文件、结果文件、配置文件的格式说明 | 处理输入输出文件时 |
| [extract-worst-subqueries](./claude/skills/extract-worst-subqueries/SKILL.md) | 定位误差最大的子查询的工具和方法 | 找出问题查询时 |
| [remap-single-table-results](./claude/skills/remap-single-table-results/SKILL.md) | 基数估计结果的重映射和转换 | 处理单表查询结果时 |
| [remap-benchmark-estimates](./claude/skills/remap-benchmark-estimates/SKILL.md) | 将外部基准估计(flat/bayescard/deepdb/neurocard)映射到 Benchmark 格式 | 导入对照实验估计时 |

### 高级特性

| Skill | 描述 | 何时使用 |
|-------|------|----------|
| [toggle-explain](./claude/skills/toggle-explain/SKILL.md) | 在 EXPLAIN 和 非 EXPLAIN 模式间切换 | 调试查询计划时 |
| [starce-estimation-internals](./claude/skills/starce-estimation-internals/SKILL.md) | StarCE 估计机制详解：EqualSet、度序列、Merge 算法 | 理解或调试 StarCE 估计逻辑时 |
| [starce-error-diagnosis](./claude/skills/starce-error-diagnosis/SKILL.md) | 排查某条查询估计偏差的方法论与工具链 | 分析 StarCE 高估/低估原因时 |
| [starce-single-query-debug](./claude/skills/starce-single-query-debug/SKILL.md) | 特化单条查询调参测试：running_space 配置、参数速查、对照实验、子查询误差分析、TrueCard 注入对比计划 | 针对特定查询调参、分析估计误差、排查性能异常、对比 StarCE 与 TrueCard 计划时 |

---

## 🚀 快速命令参考

### Python 环境管理
```bash
# 激活环境
conda activate TestEnv

# 验证环境
python --version
python -c "import numpy, pandas, torch; print('环境正常')"

# 查看已安装包
pip list
```

### 编译 StarCE
```bash
# 始终使用 build.sh，不要直接 cd build && make
./build.sh          # release 模式
./build.sh debug    # debug 模式
```
编译后二进制位于 `build/starce`（release）或 `build-debug/starce`（debug）。

### 实验运行
```bash
cd experiment

# 运行 Jupyter Notebook
jupyter notebook

# 执行特定 notebook
python ExperimentRunner.py
```

### PostgreSQL 操作
```bash
# 连接数据库
/usr/local/pgsql/13.1/bin/psql -U postgres -d stats

# 可用数据库
stats             # STATS-CEB 数据
imdb              # 完整 IMDB 数据
imdblight         # JOBLight 数据
imdblightranges   # JOBLightRanges 数据
imdbm             # JOBM 数据
```

---

## 📋 项目结构

```
# 以下为项目根目录结构
├── CLAUDE.md                    # 本文件（项目配置）
├── .claude/                     # Claude Code 配置目录
│   ├── skills/                  # 所有 skill 文档
│   └── important-things.mdc     # 重要规则
├── main.cpp                     # StarCE 入口：统计收集 + SQL 执行驱动
├── duckdb/src/include/duckdb/starce/
│   ├── starce.hpp               # 核心估计逻辑：StatisticManager（EstimateCardinality、Merge）
│   ├── statistic.hpp            # 数据结构：DSStatistic、DegreeSequence
│   └── equalset.hpp             # EqualSet 定义与序列化
├── methods/
│   ├── FactorJoin/              # FactorJoin 方法
│   ├── SafeBound/               # SafeBound 方法
│   └── ...
├── experiment/                  # 实验脚本和 notebook
│   ├── ExperimentRunner.py
│   ├── TestStarCE.ipynb
│   ├── TestSafebound.ipynb
│   ├── EvaluateAccuracy.ipynb
│   └── ...
├── setup/                       # 统一环境搭建指南
│   ├── conda/                   # Conda 环境配置
│   ├── dataset/                 # 数据集初始化脚本
│   ├── postgresql/              # PostgreSQL 配置指南
│   └── duckdb/                  # DuckDB 编译与数据库创建
├── Benchmark/                   # 标准基准数据集
│   └── workloads/
├── build/                       # 编译输出目录
└── report/                      # 分析报告
```

## 🔑 StarCE 源码关键位置

| 文件 | 内容 |
|------|------|
| `main.cpp` | 程序入口；统计收集（`CollectStatistics`）；SQL 执行（`ExecuteSql`）；config.json 解析 |
| `duckdb/src/include/duckdb/starce/starce.hpp` | `StatisticManager`：`EstimateCardinality`、`Merge`、`AdjustToAverage`、`ParsePredicate`、`AddTable/AddPredicate` |
| `duckdb/src/include/duckdb/starce/statistic.hpp` | `DSStatistic`（度序列统计体）、`DegreeSequence`（压缩度序列）、`Merge` 点积实现 |
| `duckdb/src/include/duckdb/starce/equalset.hpp` | `EqualSet` 定义（表名+列名的等价集合）、序列化/反序列化 |

统计信息缓存文件：`experiment/running_space/statistics_{benchmark}.json`

---

## 🔗 相关资源

- **项目根目录**：本仓库所在目录
- **PostgreSQL 数据目录**：`/mnt/sdb1/tlw/pgdata`
- **Conda 环境路径**：`/home/liwei/miniconda3/envs/TestEnv`

---

## ✅ 迁移完成

✓ 项目规则已迁移至 `.claude/important-things.mdc`  
✓ 环境配置已迁移至 `.claude/testenv-python-environment.mdc`  
✓ 所有 skills 已迁移至 `.claude/skills/`  
✓ CLAUDE.md 创建为项目导航中心  

**在 Cursor 中工作时**，继续使用 `.cursor/` 目录。  
**在 Claude Code 中工作时**，本文件和 `.claude/` 目录会自动加载。
