---
name: ar-par-tuning
description: StarCE PM0 AR/PAR automatic parameter tuning experiment: explores candidate AR×PAR grids by invoking StarCE, evaluates using |bias|+k*spread metric, selects optimal parameters, and compares with PM1 baseline. Use when the user mentions AR/PAR tuning, AdjustRate, PredicateAdjustRate, |bias|+spread, 2D grid, orthogonal violin plot, PM0 parameter selection, tune_two_phase, update_summary.
---

# AR/PAR Parameter Auto-Tuning Experiment

## Directory Structure

```
experiment/ar_par_tuning/
├── __init__.py                  # Package exports
├── tuner.py                     # Core tuning engine (ARPARTuner)
├── splitting.py                 # Subquery-level random splitting
├── update_summary.py            # ★ Unified entry point for updating summary
├── TuneARPAR.ipynb              # Main experiment notebook (1D scan)
├── PlotTuningResults.ipynb      # 1D results visualization
├── Plot2DGrid.ipynb             # 2D orthogonal grid visualization
├── run_all.py                   # Batch run 1D scan (deprecated)
├── tune_two_phase.py            # Two-phase tuning (PAR first, then AR)
└── checkpoint/                  # Split indices + tuning summary + final estimates + chart PDFs
    ├── all_summary.json         # Summary for all benchmarks
    └── {benchmark}/
        ├── split_tuning_indices.json
        ├── split_eval_indices.json
        ├── tuning_summary.json           # Optimal AR/PAR + grid_scores + various statistics
        └── card_{benchmark}_tuned_optimal.txt  # Subquery cardinality estimates under optimal parameters
```

Candidate estimate files follow the StarCE checkpoint pattern:
```
experiment/checkpoint/StarCE/ar_par_tuning/{benchmark}/card_{benchmark}_AR{ar}_PAR{par}.txt
```

## Updating the Summary

**`update_summary.py` is the sole entry point** — no manual operations needed. Two modes:

```bash
# Change metric only (e.g. swap k value), no StarCE re-run — sub-second
python update_summary.py --analyze-only -k 3

# Full pipeline: run 2D candidate sweep + final evaluation + write summary
python update_summary.py

# Update only specified benchmarks
python update_summary.py --analyze-only --benchmarks STATS JOBM
```

Automatically updated on each run:
- `checkpoint/{benchmark}/tuning_summary.json` — per-benchmark details (including grid_scores)
- `checkpoint/all_summary.json` — four-benchmark summary

`tuning_summary.json` structure:
```json
{
  "benchmark": "STATS",
  "best_ar": 0.1, "best_par": 0.0,
  "score_k": 2.0,
  "estimate_file": "checkpoint/STATS/card_STATS_tuned_optimal.txt",
  "grid_scores": {"AR0p1_PAR0": {"ar": 0.1, "par": 0.0, "score": 2.347, ...}, ...},
  "full_stats":   {"score": 2.353, "pm1_score": 2.542, "|bias|": 0.373, "spread": 0.990},
  "tuning_stats": {"score": 2.347, ...},
  "eval_stats":   {"score": 2.369, "pm1_score": 2.574, ...}
}
```

## Core Metric: |bias| + k*spread

Not Q-Error, but signed logarithmic error:

- `e_i = log10(est_i / true_i)` — positive = overestimation, negative = underestimation
- `bias = mean(e_i)` — direction and magnitude of systematic deviation
- `spread = std(e_i)` — degree of inconsistency (the more mixed over/under-estimation, the larger the spread)
- `score = |bias| + k * spread` — default k=2

**spread is weighted 2x over bias**: consistency matters more than being unbiased. Overestimating everything by 2x is much better than underestimating half by 10x and overestimating half by 10x.

## Candidate Parameters

`[0, 0.01, 0.1, 1.0]`. 1D scan (AR=PAR) has 4 candidates, 2D orthogonal (AR×PAR) has 16 candidates.

## Modules

### tuner.py — ARPARTuner

```python
tuner = ARPARTuner(project_root, benchmark, runner)
candidates = tuner.generate_candidates(ar_values=[0,0.01,0.1,1.0], mode_2d=True)
tuner.run_candidate_sweep(candidates, run_starce=True)  # Write checkpoint
tuner.run_tuned_evaluation(ar, par)                       # Final evaluation
```

Key methods:
- `generate_candidates(ar_values, par_values, mode_2d)` — generate candidate list
- `run_candidate_sweep(candidates)` — run StarCE for each candidate, save to checkpoint
- `run_tuned_evaluation(ar, par, label)` — run final evaluation, write to tuning_checkpoint

### splitting.py

- `split_subqueries(n, tune_ratio, seed)` — randomly split subquery indices
- `get_n_subqueries(benchmark)` — read line count from real.txt
- `load_split_indices(dir)` / `save_split_indices(dir, ...)` — JSON persistence

## Notebooks

### Plot2DGrid.ipynb — AR×PAR Orthogonal Visualization

4×4 grid, each cell: KDE density curves with shared x-axis (narrow = concentrated, wide = dispersed), red = median, blue = mean. Background color = score heatmap, gold border = optimal. Globally normalized bandwidth ensures cross-cell width comparability.

### PlotTuningResults.ipynb — 1D Results Visualization

|bias| vs spread scatter plot, Score bar chart, error distribution violin plot, evaluation set boxplot, Score decomposition stacked chart.

### TuneARPAR.ipynb — Early 1D Experiment

Phase 0: subquery splitting → Phase 1: 1D candidate scan → Phase 2: per-subquery optimal (mean aggregation, deprecated) → Phase 3: evaluation vs PM1.

### tune_two_phase.py — Two-Phase Tuning

Phase 1: tune PAR on single-Star subqueries (AR=1.0)  
Phase 2: tune AR on full set using optimal PAR

Single-Star = subqueries where all tables share at least one common EqualSet (AR does not affect this part of the estimate).

## Experimental Results (2D Orthogonal Grid, k=2)

| Benchmark | AR | PAR | Eval Score | PM1 Score | Winner |
|---|---|---|---|---|---|
| **STATS** | 0.1 | 0.0 | 2.369 | 2.574 | **PM0** |
| **JOBM** | 0.0 | 0.01 | 2.091 | 2.519 | **PM0** |
| JOBLight | 0.0 | 0.01 | 1.011 | 0.939 | PM1 |
| **JOBLightRanges** | 0.0 | 0.01 | 1.633 | 2.106 | **PM0** |

Conclusions:
- **PAR is 0 or 0.01 across all benchmarks**: predicate filtering should shrink fully toward the mean
- **On STATS, AR=0.1 outperforms AR=0**: Join shrinkage can have slight retention, but PAR must be 0
- The 1D diagonal (AR=PAR) cannot discover the optimal combination for STATS (PAR=0.1 would worsen it); 2D orthogonal decoupling is needed to find it
- Tuned PM0 significantly outperforms PM1 on three benchmarks: STATS, JOBM, and JOBLightRanges
