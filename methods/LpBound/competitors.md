# Reproduce the results of the paper for the competitors

To reproduce the results of the paper, you first need to setup the environment and run the experiments for all approaches. We provide the scripts to run the experiments and overwrite the results in the `results` directory.
Once all the results are overwritten, you can use the juypter notebooks to generate the figures and tables in the paper as discussed in README.md.

We explain how to setup the competitors and how to run the experiments.
- [Postgres](#postgres)
- [DuckDB](#duckdb)
- [SafeBound](#safebound)
- [BayesCard](#bayescard)
- [DeepDB](#deepdb)

In the paper, we also show some results for `NeuroCard` and `FLAT`. For these approaches, as stated in the paper, we took the data from the prior work Cardinality Estimation in DBMS: A Comprehensive Benchmark Evaluation.

## Postgres

For installation and setup, please check the README.md file, Section `Setup PostgreSQL`.

### Run the experiments for Postgres

To reproduce the results, run the following commands:

```bash
# for fig 5 and table 2 estimation time
poetry run python benchmarks/experiments/accuracy_acyclic.py postgres
# for fig 6; note this can take a while to run
poetry run python benchmarks/approaches/postgres/fig6_postgres.py
# for fig 7
poetry run python benchmarks/experiments/accuracy_groupby.py postgres
# for fig 8
poetry run python benchmarks/approaches/postgres/fig8_postgres.py
```

## DuckDB

The DuckDB should have been installed when you set up the Python environment using `poetry`. The data will be imported automatically when you run the experiments.

### Run the experiments for DuckDB

To reproduce the results, run the following commands:

```bash
# for fig 5 
poetry run python benchmarks/experiments/accuracy_acyclic.py duckdb
# for fig 6
poetry run python benchmarks/approaches/duckdb_helper/fig6_duckdb.py
# for fig 7
poetry run python benchmarks/experiments/accuracy_groupby.py duckdb
# for fig 8
poetry run python benchmarks/approaches/duckdb_helper/fig8_duckdb.py
```

## SafeBound

We use the SafeBound implementation from the [SafeBound](https://github.com/kylebd99/SafeBound) repository.
We adapted the SafeBound implementation to run also `jobjoin` queries and output the results in the same format as all the other approaches.
The adapted implementation is in the `benchmarks/approaches/SafeBound` directory.

### Install SafeBound

You can follow the instructions in the SafeBound repository to install the dependencies. We copied them here for convenience. First, navigate to the SafeBound directory:

```bash
cd benchmarks/approaches/SafeBound
```

Building SafeBound Library

Set up the conda environment in order to build SafeBound using the `environment.yml` file.

```bash
conda env create
conda activate TestEnv
```

Build the pybloomfilter package.

```bash
sudo apt-get update
sudo apt-get install gcc
cd pybloomfiltermmap3
python setup.py install
cd ..
```

Build the SafeBound package

```bash
sudo apt-get install g++
cd Source
python CythonBuild.py build_ext --inplace
cd ..
```

At this point, the SafeBound library should be ready for use.

### Prepare the datasets

The next step is to prepare the datasets.
We had already downloaded the datasets, so we just need to create the symbolic links to the datasets.

```bash
cd benchmarks/approaches/SafeBound/Data
bash create_data_symlinks.sh
```

### Run the experiments for SafeBound

We next explain how to get the numbers for SafeBound.  Run the following commands to build the SafeBound statistics and run the inference experiments:

```bash
cd benchmarks/approaches/SafeBound
conda activate TestEnv
python Experiments/BuildExperiments.py  # build the SafeBound statistics
python Experiments/InferenceExperiments.py  # run the inference experiments
python Experiments/RuntimeExperiments.py  # estimate the cardinalities of the subqueries
```

The built statistics are stored in the `benchmarks/approaches/SafeBound/Data/StatObjects` directory and the inference results are stored in the `benchmarks/approaches/SafeBound/Data/Results` directory.

Run the following scripts to generate the results for the figures in the paper.

```bash
python reproduce/fig5_safebound.py # acyclic queries
python reproduce/fig7_safebound.py # groupby queries
```

This script measures the size of the SafeBound statistics. The estimation time is done in the `RuntimeExperiments.py` and `fig8_safebound.py` scripts.

```bash
python reproduce/table2_safebound.py # table 2
```

This script measures the time to build the SafeBound statistics.

```bash
python reproduce/table3_safebound.py # table 3
```

#### Estimate the cardinalities of the subqueries

This script estimates the cardinalities of the subqueries. It does not run the runtime experiments. To run the runtime experiments, you need to use the Section 6.6 of the README.md file.

```bash
python reproduce/fig8_safebound.py 
```


## DeepDB

First, create a symbolic link for the datasets. Execute the following command from the root directory.
```bash
ln -s ../../../../data/datasets/imdb benchmarks/approaches/deepdb/data/imdb_data
```

Now, navigate to `benchmarks/approaches/deepdb`.
DeepDB requires a specific python environment. Use anaconda to set it up.

```bash
cd benchmarks/approaches/deepdb
conda env create -f environment.yml -n deepdb
```

Run the experiments. The following script will run the full queries and subqueries for the JOBlight benchmark and capture the predicted cardinalities and the estimation times.

```bash
./run_deepdb.sh
```

The runner script automatically activates the conda environment and runs the experiments. This ensures the correct Python interpreter is used regardless of other virtual environments that may be active in your shell.

## BayesCard

First, create a symbolic link for the datasets. Execute the following command from the root directory.
```
ln -s ../../../../data/datasets/imdb benchmarks/approaches/bayescard/data/imdb_data
```

Now, navigate to `benchmarks/approaches/bayescard`.
BayesCard requires a specific python environment. Use anaconda to set it up.

```
conda env create -f environment.yml -n bayescard
```
Run the experiments. The following script will run the full queries and subqueries for the JOBlight benchmark and capture the predicted cardinalities and the estimation times. Note that you have to execute the commands from `benchmarks/approaches/bayescard`.

```python
conda activate bayescard
python measure_execution.py
```

## FactorJoin

FactorJoin requires some preprocessing of the data. We provide a modified `measure_execution.py` script that handles data setup and preprocessing automatically.

Navigate to `benchmarks/approaches/factorjoin`:

```bash
cd benchmarks/approaches/factorjoin
```

### Create the virtual environment

```bash
conda env create -f environment.yml -n factorjoin
conda activate factorjoin
```

**For STATS experiments only (no PostgreSQL required):**

```bash
./run_factorjoin.sh --stats-only
```

This will automatically:
1. Copy the STATS data from the project's `data/datasets/stats` directory
2. Preprocess the data (convert datetime strings to integers)
3. Train the FactorJoin model
4. Run evaluation on the STATS queries

**For IMDB experiments (requires PostgreSQL):**

FactorJoin queries PostgreSQL at inference time to estimate base table cardinalities.

1. Load the IMDB dataset into PostgreSQL (see README.md Section "Setup PostgreSQL")

2. Create a symlink for FactorJoin to access the CSV files:
```bash
mkdir -p benchmarks/approaches/factorjoin/End-to-End-CardEst-Benchmark/datasets
ln -s $(pwd)/data/datasets/imdb benchmarks/approaches/factorjoin/End-to-End-CardEst-Benchmark/datasets/imdb
```

3. Set `DBNAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` in `measure_execution.py`, then run:

```bash
./run_factorjoin.sh --imdb-only
```

The runner script automatically activates the conda environment and runs the experiments. This ensures the correct Python interpreter is used regardless of other virtual environments that may be active in your shell.

### Additional options

- `--skip-preprocess`: Skip data preprocessing if you've already run it once
- `--stats-only`: Run only STATS experiments (no PostgreSQL required)
- `--imdb-only`: Run only IMDB experiments (requires PostgreSQL)

