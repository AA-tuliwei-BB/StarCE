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

## Verify

```bash
conda run -n lpbound python -c "import lpbound; print('OK')"
ls methods/LpBound/src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel
```
