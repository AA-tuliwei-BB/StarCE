# SafeBound Setup

SafeBound uses Cython (`.pyx`) files that must be compiled to native `.so` modules before use.

## Compile

```bash
conda activate TestEnv
cd methods/SafeBound/Source
python CythonBuild.py build_ext --inplace
```

Compiles 4 extensions: `SafeBoundUtils`, `HistogramUtils`, `JoinGraphUtils`, `PiecewiseConstantFunctionUtils`.

Requirements: gcc, g++, Cython (in TestEnv), OpenMP.

## Verify

```bash
python -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(1, 'ExperimentUtils')
from BuildUtils import build_stats_object
print('SafeBound OK')
"
```
