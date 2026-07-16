---
name: python-env
description: Python environment configuration for the StarCE project: current version, dependencies, environment requirements and virtual environment setup for each method (FactorJoin/SafeBound/StarCE). Use when mentioning Python version, dependency installation, virtual environment, requirements.txt.
---

# StarCE Python Environment Configuration

## Quick Reference

### System Python

```bash
# Current system Python version
python --version
# Output: Python 3.12.7

which python
# Output: /usr/bin/python (or other path)
```

### Python Requirements by Method

| Method | Recommended Version | Actually Tested Version | Dependency File |
|------|----------|-------------|----------|
| **FactorJoin** | Python 3.7 | 3.12.7 (to be verified) | `methods/FactorJoin/requirements.txt` |
| **SafeBound** | Python 3.x | 3.12.7 | `methods/SafeBound/requirements.txt` |
| **StarCE** | Python 3.x | 3.12.7 | Project root (DuckDB) |

## FactorJoin Environment

### Location
`methods/FactorJoin/`

### Python Version Requirements
- **README requires**: Python 3.7
- **Current system**: Python 3.12.7
- **Status**: Needs compatibility verification or virtual environment creation

### Core Dependencies

```
numpy
pandas
pickle (stdlib)
psycopg2        # PostgreSQL connection (required for sampling mode)
scipy           # Scientific computing
pgmpy           # Bayesian networks
torch           # Deep learning (optional)
```

### Creating a Virtual Environment

```bash
# Run the following from the project root directory
cd methods/FactorJoin

# Option 1: Using conda (recommended)
conda create -n factorjoin python=3.7
conda activate factorjoin
pip install -r requirements.txt

# Option 2: Using venv
python3.7 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Option 3: Try using current Python 3.12
pip install -r requirements.txt
# If compatibility issues arise, fall back to option 1 or 2
```

### Verify Installation

```bash
cd methods/FactorJoin
python -c "import pickle, numpy, pandas; print('Core dependencies OK')"
python -c "import psycopg2; print('PostgreSQL driver OK')"
python -c "from BayesCard.Models.Bayescard_BN import Bayescard_BN; print('BayesCard OK')"
```

### Common Dependency Issues

**Issue 1: numpy not installed**
```bash
pip install numpy pandas
```

**Issue 2: psycopg2 compilation failure**
```bash
# Use binary version
pip install psycopg2-binary

# Or install system dependencies and retry
sudo apt-get install libpq-dev python3-dev
pip install psycopg2
```

**Issue 3: Python 3.7 vs 3.12 compatibility**
- Some dependencies may not support Python 3.12
- Recommended to use conda to create a Python 3.7 environment

## SafeBound Environment

### Location
`methods/SafeBound/`

### Dependency Installation

```bash
cd methods/SafeBound
pip install -r requirements.txt
```

### Core Dependencies

```
numpy
pandas
scipy
sklearn
pgmpy
psycopg2-binary
torch           # If using deep learning components
```

### Data Preprocessing Dependencies

SafeBound uses HDF5 format for data caching:

```bash
pip install tables h5py
```

### Verify Installation

```bash
cd methods/SafeBound
python -c "from bayescard.Models.Bayescard_BN import Bayescard_BN; print('SafeBound OK')"
```

## StarCE Environment

### Location
Project root + `duckdb/` subdirectory

### DuckDB Version
StarCE uses a custom-compiled DuckDB

### Python Bindings
If Python interface is needed:

```bash
pip install duckdb
```

### CMake Build
If recompiling StarCE is needed:

```bash
# Install build tools
sudo apt-get install cmake g++ make

# Build StarCE from project root
mkdir build
cd build
cmake ..
make -j$(nproc)
```

## Virtual Environment Management

### Conda Environment (Recommended)

```bash
# Create FactorJoin-dedicated environment
conda create -n factorjoin python=3.7
conda activate factorjoin
cd methods/FactorJoin
pip install -r requirements.txt

# Create SafeBound-dedicated environment
conda create -n safebound python=3.8
conda activate safebound
cd methods/SafeBound
pip install -r requirements.txt

# List all environments
conda env list

# Switch environments
conda activate factorjoin
conda deactivate
```

### venv Environment

```bash
# Create environment for FactorJoin
cd methods/FactorJoin
python3.7 -m venv venv_factorjoin
source venv_factorjoin/bin/activate
pip install -r requirements.txt
deactivate

# Create environment for SafeBound
cd methods/SafeBound
python3 -m venv venv_safebound
source venv_safebound/bin/activate
pip install -r requirements.txt
deactivate
```

### Environment Activation Shortcuts

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# StarCE project environments (assuming project root is $STARCE_ROOT)
alias starce-factorjoin='cd $STARCE_ROOT/methods/FactorJoin && conda activate factorjoin'
alias starce-safebound='cd $STARCE_ROOT/methods/SafeBound && conda activate safebound'
```

## Dependency File Locations

### FactorJoin

```
methods/FactorJoin/
├── requirements.txt           # Python dependencies
├── BayesCard/                 # Bayesian network implementation
├── Join_scheme/               # Core algorithm
└── Sampling/                  # Sampling methods
```

### SafeBound

```
methods/SafeBound/
├── requirements.txt           # Python dependencies
├── bayescard/                 # BayesCard methods
├── checkpoints/               # Models and caches
│   └── stats_hdf/            # HDF5 cache files
└── Workloads/                 # Query workloads
```

## Common Commands

### Check Current Environment

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Check specific package versions
pip show numpy pandas psycopg2

# Export current environment
pip freeze > current_requirements.txt
```

### Cleanup and Reinstall

```bash
# Uninstall all packages (use with caution)
pip freeze | xargs pip uninstall -y

# Reinstall
pip install -r requirements.txt

# Upgrade pip
pip install --upgrade pip
```

### Dependency Conflict Resolution

```bash
# Check dependency conflicts
pip check

# View dependency tree
pip install pipdeptree
pipdeptree

# Force reinstall specific package
pip install --force-reinstall numpy
```

## Jupyter Notebook Support

If running in Notebook is needed:

```bash
# Install Jupyter
pip install jupyter notebook

# Create kernel
python -m ipykernel install --user --name=factorjoin --display-name="Python (FactorJoin)"

# Launch Notebook
jupyter notebook
```

## IDE Configuration

### VS Code / Cursor

In `.vscode/settings.json` or Cursor settings:

```json
{
  "python.defaultInterpreterPath": "/path/to/conda/envs/factorjoin/bin/python",
  "python.linting.enabled": true,
  "python.formatting.provider": "black"
}
```

### PyCharm

1. File → Settings → Project → Python Interpreter
2. Add Conda environment or venv environment
3. Select the corresponding Python interpreter

## Performance Optimization

### NumPy/SciPy Acceleration

```bash
# Use OpenBLAS or MKL acceleration
pip install numpy scipy --no-binary numpy,scipy

# Or use conda's optimized versions
conda install numpy scipy -c conda-forge
```

### Multi-threading Configuration

```bash
# Set NumPy thread count
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

# Run Python script
python your_script.py
```

## Troubleshooting

### Import Errors

```bash
# Check module path
python -c "import sys; print('\n'.join(sys.path))"

# Check package installation location
python -c "import numpy; print(numpy.__file__)"
```

### PYTHONPATH Issues

```bash
# Temporarily add path (assuming from project root)
export PYTHONPATH=$(pwd)/methods/FactorJoin:$PYTHONPATH

# Permanently add (in ~/.bashrc, replace with actual project path)
echo 'export PYTHONPATH=/path/to/starCE/methods/FactorJoin:$PYTHONPATH' >> ~/.bashrc
source ~/.bashrc
```

### Package Version Conflicts

```bash
# View conflicts
pip check

# View dependency relationships
pip show <package-name>

# Install pinned version
pip install numpy==1.21.0
```

## Experiment Script Environment

### experiment/ Directory

Location: `experiment/` (under project root)

Contains various evaluation scripts, may require:
```bash
pip install jupyter matplotlib seaborn
```

### Running Experiments

```bash
cd experiment

# Activate appropriate environment
conda activate factorjoin

# Run Jupyter Notebook
jupyter notebook EvaluateAccuracy.ipynb
```

## Related Skills

- [factorjoin-usage](../factorjoin-usage/SKILL.md) - FactorJoin's Python environment requirements
- [postgresql-env](../postgresql-env/SKILL.md) - psycopg2 database connection configuration
