---
name: python-env
description: StarCE 项目的 Python 环境配置：当前版本、依赖包、各个方法（FactorJoin/SafeBound/StarCE）的环境要求和虚拟环境设置。当用户提到 Python 版本、依赖安装、虚拟环境、requirements.txt 时使用。
---

# StarCE Python 环境配置

## 快速参考

### 系统 Python

```bash
# 当前系统 Python 版本
python --version
# Output: Python 3.12.7

which python
# Output: /usr/bin/python (或其他路径)
```

### 各方法的 Python 要求

| 方法 | 推荐版本 | 实际测试版本 | 依赖文件 |
|------|----------|-------------|----------|
| **FactorJoin** | Python 3.7 | 3.12.7 (待验证) | `methods/FactorJoin/requirements.txt` |
| **SafeBound** | Python 3.x | 3.12.7 | `methods/SafeBound/requirements.txt` |
| **StarCE** | Python 3.x | 3.12.7 | 项目根目录 (DuckDB) |

## FactorJoin 环境

### 位置
`methods/FactorJoin/`

### Python 版本要求
- **README 要求**: Python 3.7
- **当前系统**: Python 3.12.7
- **状态**: 需要验证兼容性或创建虚拟环境

### 核心依赖

```
numpy
pandas
pickle (标准库)
psycopg2        # PostgreSQL 连接（采样模式需要）
scipy           # 科学计算
pgmpy           # 贝叶斯网络
torch           # 深度学习（可选）
```

### 创建虚拟环境

```bash
# 以下命令在项目根目录下运行
cd methods/FactorJoin

# 方案 1: 使用 conda (推荐)
conda create -n factorjoin python=3.7
conda activate factorjoin
pip install -r requirements.txt

# 方案 2: 使用 venv
python3.7 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 方案 3: 尝试使用当前 Python 3.12
pip install -r requirements.txt
# 如果遇到兼容性问题，回退到方案 1 或 2
```

### 验证安装

```bash
cd methods/FactorJoin
python -c "import pickle, numpy, pandas; print('Core dependencies OK')"
python -c "import psycopg2; print('PostgreSQL driver OK')"
python -c "from BayesCard.Models.Bayescard_BN import Bayescard_BN; print('BayesCard OK')"
```

### 常见依赖问题

**问题 1: numpy 未安装**
```bash
pip install numpy pandas
```

**问题 2: psycopg2 编译失败**
```bash
# 使用二进制版本
pip install psycopg2-binary

# 或安装系统依赖后重试
sudo apt-get install libpq-dev python3-dev
pip install psycopg2
```

**问题 3: Python 3.7 与 3.12 兼容性**
- 某些依赖可能不支持 Python 3.12
- 推荐使用 conda 创建 Python 3.7 环境

## SafeBound 环境

### 位置
`methods/SafeBound/`

### 依赖安装

```bash
cd methods/SafeBound
pip install -r requirements.txt
```

### 核心依赖

```
numpy
pandas
scipy
sklearn
pgmpy
psycopg2-binary
torch           # 如果使用深度学习组件
```

### 数据预处理依赖

SafeBound 使用 HDF5 格式缓存数据:

```bash
pip install tables h5py
```

### 验证安装

```bash
cd methods/SafeBound
python -c "from bayescard.Models.Bayescard_BN import Bayescard_BN; print('SafeBound OK')"
```

## StarCE 环境

### 位置
项目根目录 + `duckdb/` 子目录

### DuckDB 版本
StarCE 使用自定义编译的 DuckDB

### Python 绑定
如果需要 Python 接口:

```bash
pip install duckdb
```

### CMake 构建
如果需要重新编译 StarCE:

```bash
# 安装构建工具
sudo apt-get install cmake g++ make

# 在项目根目录下构建 StarCE
mkdir build
cd build
cmake ..
make -j$(nproc)
```

## 虚拟环境管理

### Conda 环境（推荐）

```bash
# 创建 FactorJoin 专用环境
conda create -n factorjoin python=3.7
conda activate factorjoin
cd methods/FactorJoin
pip install -r requirements.txt

# 创建 SafeBound 专用环境
conda create -n safebound python=3.8
conda activate safebound
cd methods/SafeBound
pip install -r requirements.txt

# 列出所有环境
conda env list

# 切换环境
conda activate factorjoin
conda deactivate
```

### venv 环境

```bash
# 为 FactorJoin 创建环境
cd methods/FactorJoin
python3.7 -m venv venv_factorjoin
source venv_factorjoin/bin/activate
pip install -r requirements.txt
deactivate

# 为 SafeBound 创建环境
cd methods/SafeBound
python3 -m venv venv_safebound
source venv_safebound/bin/activate
pip install -r requirements.txt
deactivate
```

### 环境激活快捷方式

在 `~/.bashrc` 或 `~/.zshrc` 中添加:

```bash
# StarCE 项目环境（假设项目根目录为 $STARCE_ROOT）
alias starce-factorjoin='cd $STARCE_ROOT/methods/FactorJoin && conda activate factorjoin'
alias starce-safebound='cd $STARCE_ROOT/methods/SafeBound && conda activate safebound'
```

## 依赖文件位置

### FactorJoin

```
methods/FactorJoin/
├── requirements.txt           # Python 依赖
├── BayesCard/                 # 贝叶斯网络实现
├── Join_scheme/               # 核心算法
└── Sampling/                  # 采样方法
```

### SafeBound

```
methods/SafeBound/
├── requirements.txt           # Python 依赖
├── bayescard/                 # 贝叶斯卡方法
├── checkpoints/               # 模型和缓存
│   └── stats_hdf/            # HDF5 缓存文件
└── Workloads/                 # 查询工作集
```

## 常用命令

### 检查当前环境

```bash
# 查看 Python 版本
python --version

# 查看已安装包
pip list

# 查看特定包版本
pip show numpy pandas psycopg2

# 导出当前环境
pip freeze > current_requirements.txt
```

### 清理和重装

```bash
# 卸载所有包（慎用）
pip freeze | xargs pip uninstall -y

# 重新安装
pip install -r requirements.txt

# 升级 pip
pip install --upgrade pip
```

### 依赖冲突解决

```bash
# 检查依赖冲突
pip check

# 查看依赖树
pip install pipdeptree
pipdeptree

# 强制重装特定包
pip install --force-reinstall numpy
```

## Jupyter Notebook 支持

如果需要在 Notebook 中运行:

```bash
# 安装 Jupyter
pip install jupyter notebook

# 创建内核
python -m ipykernel install --user --name=factorjoin --display-name="Python (FactorJoin)"

# 启动 Notebook
jupyter notebook
```

## IDE 配置

### VS Code / Cursor

在 `.vscode/settings.json` 或 Cursor 设置中:

```json
{
  "python.defaultInterpreterPath": "/path/to/conda/envs/factorjoin/bin/python",
  "python.linting.enabled": true,
  "python.formatting.provider": "black"
}
```

### PyCharm

1. File → Settings → Project → Python Interpreter
2. 添加 Conda 环境或 venv 环境
3. 选择对应的 Python 解释器

## 性能优化

### NumPy/SciPy 加速

```bash
# 使用 OpenBLAS 或 MKL 加速
pip install numpy scipy --no-binary numpy,scipy

# 或使用 conda 的优化版本
conda install numpy scipy -c conda-forge
```

### 多线程配置

```bash
# 设置 NumPy 线程数
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

# 运行 Python 脚本
python your_script.py
```

## 故障排查

### 导入错误

```bash
# 检查模块路径
python -c "import sys; print('\n'.join(sys.path))"

# 检查包安装位置
python -c "import numpy; print(numpy.__file__)"
```

### PYTHONPATH 问题

```bash
# 临时添加路径（假设在项目根目录下）
export PYTHONPATH=$(pwd)/methods/FactorJoin:$PYTHONPATH

# 永久添加（在 ~/.bashrc，需替换为实际项目路径）
echo 'export PYTHONPATH=/path/to/starCE/methods/FactorJoin:$PYTHONPATH' >> ~/.bashrc
source ~/.bashrc
```

### 包版本冲突

```bash
# 查看冲突
pip check

# 查看依赖关系
pip show <package-name>

# 固定版本安装
pip install numpy==1.21.0
```

## 实验脚本环境

### experiment/ 目录

位置: `experiment/`（项目根目录下）

包含各种评估脚本，可能需要:
```bash
pip install jupyter matplotlib seaborn
```

### 运行实验

```bash
cd experiment

# 激活合适的环境
conda activate factorjoin

# 运行 Jupyter Notebook
jupyter notebook EvaluateAccuracy.ipynb
```

## 相关 Skills

- [factorjoin-usage](../factorjoin-usage/SKILL.md) - FactorJoin 的 Python 环境要求
- [postgresql-env](../postgresql-env/SKILL.md) - psycopg2 连接数据库配置
