# StarCE Project Claude Code Configuration

> This file is project-level configuration, effective for all Claude Code sessions.  
> Migrated from Cursor project configuration.

## Important Rules (Must Read)

**The following rules apply to all sessions. Violations will reduce work efficiency:**

1. **Refuse surface fixes**: Do not merely fix symptoms; identify and report the root cause
2. **No unapproved Git changes**: Any git operations (commit/push/merge) require explicit confirmation
3. **Direct feedback, not documents**: Do not generate report documents; respond directly in the conversation
4. **Avoid workarounds**: Do not use workarounds or fallback solutions; if necessary, confirm with the user first
5. **Code formatting standards**: Empty lines must not contain spaces or indentation characters
6. **Language**: Always reply in Simplified Chinese
7. **Do not overwrite Benchmark files**: `RecordingSubquery=1` will overwrite the file pointed to by `SUBQUERY_PATH`. When using it, `SUBQUERY_PATH` must be changed to a temporary file within running_space (e.g., `q59_subqueries.sql`). It is prohibited to point to any file under the `Benchmark/` directory
8. **How to reference a query**: Do not use unreliable Qxx notation for queries, as 0-indexed and 1-indexed confusion is common. When mentioning Qxx, first clarify its indexing base (0-indexed or 1-indexed), and verify with the corresponding line's SQL content. When a query needs to be mentioned in reports or other locations, always include the full query SQL to avoid confusion. Example: `sed -n '58p' queries.sql` corresponds to 0-indexed query_id=57.
9. **This project uses Relative Error, not Q-Error**: The evaluation metric is `max(1, est) / max(1, true)` (signed relative error), not standard Q-Error (`max(est/true, true/est)`). The two have different semantics: Relative Error is <1 when underestimating (log10 negative), >1 when overestimating (log10 positive); Q-Error is always >=1. Variable names `qerror`/`q_err` in the code are misused; their actual semantics is Relative Error. Be aware of this distinction when reading or writing evaluation code; do not confuse them.

For more details, see [`.claude/important-things.mdc`](.claude/important-things.mdc)

---

## Environment Configuration

### Python Environment

**This project uses the TestEnv conda environment:**
- **Environment name**: TestEnv
- **Python version**: 3.10.4
- **Activation command**: `conda activate TestEnv`

### Core Dependencies

| Category | Main Packages |
|------|--------|
| **Numerical Computing** | NumPy 1.22.0, Pandas 1.5.3, SciPy 1.7.3 |
| **Machine Learning** | PyTorch 2.10.0 (CUDA 12.8), XGBoost 3.1.3, Scikit-learn 1.1.2 |
| **Bayesian Networks** | pgmpy 0.1.26, pomegranate 0.14.3, pyro-ppl 1.9.1 |
| **Database** | psycopg2 2.8.6 (PostgreSQL) |
| **Data Processing** | HDF5 support (tables 3.10.1) |

Activate environment:
```bash
conda activate TestEnv
```

Full details at [`.claude/testenv-python-environment.mdc`](.claude/testenv-python-environment.mdc)

---

## Project Skills Navigation

> These skills provide project-specific knowledge and workflow guidance. The corresponding skill is automatically loaded when related topics are involved.

### Core Workflows

| Skill | Description | When to Use |
|-------|------|----------|
| [experiment-workflow](./claude/skills/experiment-workflow/SKILL.md) | Experiment flow overview, ExperimentRunner driver logic, cardinality collection and analysis workflow | When discussing experiment design, how to run tests, or result analysis |
| [python-env](./claude/skills/python-env/SKILL.md) | Python environment configuration, environment requirements for each method, virtual environment setup | When dealing with environment issues, dependency installation, or version compatibility |
| [postgresql-env](./claude/skills/postgresql-env/SKILL.md) | PostgreSQL connection configuration, database setup | When connecting to PG database |
| [setup](./claude/skills/setup/SKILL.md) | Unified environment setup: conda environment, dataset acquisition, PostgreSQL configuration, DuckDB compilation and database creation | When initializing project, configuring environment from scratch, or acquiring datasets |

### Main Method Documentation

| Skill | Description | When to Use |
|-------|------|----------|
| [starce-overview](./claude/skills/starce-overview/SKILL.md) | StarCE system overview, core features, project structure | When learning about StarCE's overall architecture |
| [starce-usage](./claude/skills/starce-usage/SKILL.md) | StarCE usage guide, parameter configuration, binary operations | When running or configuring StarCE |
| [factorjoin-usage](./claude/skills/factorjoin-usage/SKILL.md) | FactorJoin's two working modes (BN/sampling), training and evaluation workflow | When working with FactorJoin cardinality estimation |
| [factorjoin-jobm-sampling](./claude/skills/factorjoin-jobm-sampling/SKILL.md) | Specific implementation details of FactorJoin's JOBM sampling mode | When optimizing FactorJoin sampling performance |
| [fspn-usage](./claude/skills/fspn-usage/SKILL.md) | FSPN architecture principles, node types, learning algorithms, inference modes | When learning about or using FSPN cardinality estimation |
| [safebound-runtime](./claude/skills/safebound-runtime/SKILL.md) | SafeBound Runtime experiment pipeline | When running SafeBound experiments |

### Data and Tools

| Skill | Description | When to Use |
|-------|------|----------|
| [benchmark-datasets](./claude/skills/benchmark-datasets/SKILL.md) | Benchmark dataset details, characteristics of STATS-CEB/JOBM/JOBLight | When selecting or understanding datasets |
| [workload-file-formats](./claude/skills/workload-file-formats/SKILL.md) | Format description of SQL files, result files, configuration files | When handling input/output files |
| [extract-worst-subqueries](./claude/skills/extract-worst-subqueries/SKILL.md) | Tools and methods for locating subqueries with the largest error | When identifying problematic queries |
| [remap-single-table-results](./claude/skills/remap-single-table-results/SKILL.md) | Remapping and conversion of cardinality estimation results | When handling single-table query results |
| [remap-benchmark-estimates](./claude/skills/remap-benchmark-estimates/SKILL.md) | Map external benchmark estimates (flat/bayescard/deepdb/neurocard) to Benchmark format | When importing control experiment estimates |

### Advanced Features

| Skill | Description | When to Use |
|-------|------|----------|
| [toggle-explain](./claude/skills/toggle-explain/SKILL.md) | Switch between EXPLAIN and non-EXPLAIN modes | When debugging query plans |
| [starce-estimation-internals](./claude/skills/starce-estimation-internals/SKILL.md) | Detailed explanation of StarCE estimation mechanism: EqualSet, degree sequences, Merge algorithm | When understanding or debugging StarCE estimation logic |
| [starce-error-diagnosis](./claude/skills/starce-error-diagnosis/SKILL.md) | Methodology and toolchain for diagnosing estimation bias in a query | When analyzing causes of StarCE overestimation/underestimation |
| [starce-single-query-debug](./claude/skills/starce-single-query-debug/SKILL.md) | Specialized single-query tuning test: running_space configuration, parameter quick reference, control experiments, subquery error analysis, TrueCard injection comparison plan | When tuning parameters for a specific query, analyzing estimation errors, troubleshooting performance anomalies, or comparing StarCE and TrueCard plans |

---

## Quick Command Reference

### Python Environment Management
```bash
# Activate environment
conda activate TestEnv

# Verify environment
python --version
python -c "import numpy, pandas, torch; print('environment OK')"

# View installed packages
pip list
```

### Build StarCE
```bash
# Always use build.sh; do not directly cd build && make
./build.sh          # release mode
./build.sh debug    # debug mode
```
Compiled binary is located at `build/starce` (release) or `build-debug/starce` (debug).

### Running Experiments
```bash
cd experiment

# Run Jupyter Notebook
jupyter notebook

# Execute a specific notebook
python ExperimentRunner.py
```

### PostgreSQL Operations
```bash
# Connect to database
/usr/local/pgsql/13.1/bin/psql -U postgres -d stats

# Available databases
stats             # STATS-CEB data
imdb              # Full IMDB data
imdblight         # JOBLight data
imdblightranges   # JOBLightRanges data
imdbm             # JOBM data
```

---

## Project Structure

```
# Below is the project root directory structure
├── CLAUDE.md                    # This file (project configuration)
├── .claude/                     # Claude Code configuration directory
│   ├── skills/                  # All skill documents
│   └── important-things.mdc     # Important rules
├── main.cpp                     # StarCE entry point: statistics collection + SQL execution driver
├── duckdb/src/include/duckdb/starce/
│   ├── starce.hpp               # Core estimation logic: StatisticManager (EstimateCardinality, Merge)
│   ├── statistic.hpp            # Data structures: DSStatistic, DegreeSequence
│   └── equalset.hpp             # EqualSet definition and serialization
├── methods/
│   ├── FactorJoin/              # FactorJoin method
│   ├── SafeBound/               # SafeBound method
│   └── ...
├── experiment/                  # Experiment scripts and notebooks
│   ├── ExperimentRunner.py
│   ├── TestStarCE.ipynb
│   ├── TestSafebound.ipynb
│   ├── EvaluateAccuracy.ipynb
│   └── ...
├── setup/                       # Unified environment setup guide
│   ├── conda/                   # Conda environment configuration
│   ├── dataset/                 # Dataset initialization scripts
│   ├── postgresql/              # PostgreSQL configuration guide
│   └── duckdb/                  # DuckDB compilation and database creation
├── Benchmark/                   # Standard benchmark datasets
│   └── workloads/
├── build/                       # Build output directory
└── report/                      # Analysis reports
```

## StarCE Source Code Key Locations

| File | Content |
|------|------|
| `main.cpp` | Program entry; statistics collection (`CollectStatistics`); SQL execution (`ExecuteSql`); config.json parsing |
| `duckdb/src/include/duckdb/starce/starce.hpp` | `StatisticManager`: `EstimateCardinality`, `Merge`, `AdjustToAverage`, `ParsePredicate`, `AddTable/AddPredicate` |
| `duckdb/src/include/duckdb/starce/statistic.hpp` | `DSStatistic` (degree sequence statistics body), `DegreeSequence` (compressed degree sequence), `Merge` dot product implementation |
| `duckdb/src/include/duckdb/starce/equalset.hpp` | `EqualSet` definition (table name + column name equivalence set), serialization/deserialization |

Statistics cache file: `experiment/running_space/statistics_{benchmark}.json`

---

## Related Resources

- **Project root directory**: The directory where this repository is located
- **PostgreSQL data directory**: `/mnt/sdb1/tlw/pgdata`
- **Conda environment path**: `/home/liwei/miniconda3/envs/TestEnv`

---

## Migration Complete

- Project rules migrated to `.claude/important-things.mdc`  
- Environment configuration migrated to `.claude/testenv-python-environment.mdc`  
- All skills migrated to `.claude/skills/`  
- CLAUDE.md created as project navigation center  

**When working in Cursor**, continue using the `.cursor/` directory.  
**When working in Claude Code**, this file and the `.claude/` directory are automatically loaded.
