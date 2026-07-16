# Conda 环境配置

StarCE 项目使用的 conda 环境为 **TestEnv**（Python 3.10.4），其精确配置由以下三个文件描述：

| 文件 | 格式 | 用途 |
|------|------|------|
| `environment.yml` | conda env export | 含 exact Linux build hashes，用于精确复现 |
| `environment-no-builds.yml` | conda env export (no builds) | 跨平台便携版，不含 build hash |
| `requirements-freeze.txt` | pip freeze | pip 格式，方便在各平台上使用 pip 安装 |

**关键依赖**：numpy 1.22.0, pandas 1.5.3, torch 2.10.0, duckdb 1.5.2, scipy 1.7.3, scikit-learn 1.1.2, pgmpy 0.1.26, xgboost 3.1.3, psycopg2 2.8.6。

## 使用方式

```bash
# 创建环境
conda env create -f setup/conda/environment.yml

# 或跨平台创建
conda env create -f setup/conda/environment-no-builds.yml

# 激活环境
conda activate TestEnv
```
