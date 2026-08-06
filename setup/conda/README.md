# Conda Environment Configuration

The conda environment used by the StarCE project is **TestEnv** (Python 3.10.4), with its exact configuration described by the following three files:

| File | Format | Purpose |
|------|------|------|
| `environment.yml` | conda env export | Contains exact Linux build hashes for precise reproduction |
| `environment-no-builds.yml` | conda env export (no builds) | Cross-platform portable version, without build hash |
| `requirements-freeze.txt` | pip freeze | pip format, convenient for pip installation on various platforms |

**Key dependencies**: numpy 1.22.0, pandas 1.5.3, torch 2.10.0, duckdb 1.5.2, scipy 1.7.3, scikit-learn 1.1.2, pgmpy 0.1.26, xgboost 3.1.3, psycopg2 2.8.6.

## Usage

```bash
# Create environment
conda env create -f setup/conda/environment.yml

# Or cross-platform creation
conda env create -f setup/conda/environment-no-builds.yml

# Activate environment
conda activate TestEnv
```
