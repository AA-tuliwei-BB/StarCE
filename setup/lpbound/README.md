# LpBound Setup

LpBound requires a separate conda environment with its Python package and a compiled C++ solver.

## 1. Conda Environment

```bash
conda create -n lpbound python=3.11 -y
```

## 2. Python Package + Solver Dependencies

```bash
conda activate lpbound
pip install -e methods/LpBound/
conda install -n lpbound -c conda-forge highs nlohmann_json
```

## 3. C++ Solver Binary

```bash
cd methods/LpBound/src/lpbound/cpp_solver

mkdir -p HiGHS/build/lib json/include
ln -sf $CONDA_PREFIX/include/highs HiGHS/highs
ln -sf $CONDA_PREFIX/lib/libhighs.so HiGHS/build/lib/libhighs.so
ln -sf $CONDA_PREFIX/lib/libhighs.so.1 HiGHS/build/lib/libhighs.so.1
ln -sf $CONDA_PREFIX/lib/libhighs.so.1.15.1 HiGHS/build/lib/libhighs.so.1.15.1
ln -sf $CONDA_PREFIX/include/nlohmann json/include/nlohmann

cd lpbound_parallel && bash compile.sh
```

Requirements: cmake, g++ (≥12), OpenMP.

## 4. IMDB Data

Symlink from `Benchmark/IMDB/` to avoid re-download:

```bash
mkdir -p methods/LpBound/data/datasets/imdb
for f in Benchmark/IMDB/*.csv; do
    ln -sf ../../../../"$f" methods/LpBound/data/datasets/imdb/"$(basename $f)"
done
```

## 5. Estimation Input Data

The C++ solver needs precomputed LP input files. These are shipped as `raw_input.zip`.

```bash
cd methods/LpBound/src/lpbound/cpp_solver/lpbound_parallel

# Extract and reorganize (zip contents are flat, expected under raw_input/)
python3 -c "
import zipfile, os, shutil
with zipfile.ZipFile('raw_input.zip') as zf:
    zf.extractall('.')
os.makedirs('raw_input', exist_ok=True)
for d in ['stats_subqueries', 'joblight_subqueries', 'jobrange_subqueries', 'jobjoin_subqueries']:
    if os.path.isdir(d):
        shutil.move(d, 'raw_input/' + d)
"

# Generate input_data (script has a bug: defines main() but never calls it)
conda run -n lpbound python -c "
import sys, os
os.chdir('$(pwd)')
sys.path.insert(0, '.')
import create_input_files
create_input_files.main()
"
```

## 6. Run Estimation (populates timing data for EvaluatePerformance)

```bash
cd experiment
conda run -n lpbound python TestLpBound.py --est-only
```

This runs the C++ solver and writes `checkpoint/LpBound/timing_details.json`.

## Verify

```bash
conda run -n lpbound python -c "import lpbound; print('OK')"
ls methods/LpBound/src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel
ls methods/LpBound/src/lpbound/cpp_solver/lpbound_parallel/input_data/
python3 -c "import json; d=json.load(open('experiment/checkpoint/LpBound/timing_details.json')); print('estimate_time:', list(d['estimate_time'].keys()))"
```
