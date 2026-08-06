---
name: plot-style
description: Unified plot style for StarCE experiments: cross-method color scheme (StarCE gets exclusive eye-catching red, DuckDB/SafeBound/FactorJoin/Flat grouped by hue), experiment/plot_style.py shared module (METHOD_COLORS/METHOD_ORDER/get_method_color/generate_color_palette/draw_violins), violin plot conventions. Use when mentioning plot colors, chart style, method colors, box-to-violin conversion, violin, accuracy/latency distribution colors, unified legend, plot_style.
---

# StarCE Experiment Unified Plot Style

All Evaluate notebooks share a common color scheme and violin plot helper functions, centralized in
`experiment/plot_style.py`. Goal: **StarCE is the most prominent in every figure**, while other methods
are grouped semantically with consistent hues across figures.

## Color Scheme

Each method has a **distinct, independent hue** (no two share the same color family, maximizing differentiation);
**red is reserved exclusively for StarCE** (the only red in the entire figure, with full opacity + thick
stroke = most prominent). Grouping only affects the display order
(`METHOD_ORDER`), not the colors.

| Method | Color | Hex |
|------|----|-----|
| **StarCE** | Bright red (unique in figure, most prominent) | `#E31A1C` |
| StarCE-Upper | Dark red/maroon (StarCE family variant) | `#7F0000` |
| DuckDB | Blue | `#1F77B4` |
| Postgre | Cyan | `#17BECF` |
| SafeBound | Purple | `#9467BD` |
| LpBound | Pink | `#E377C2` |
| BayesCard | Orange | `#FF7F0E` |
| FactorJoin | Brown | `#8C564B` |
| DeepDB | Olive | `#BCBD22` |
| Flat | Green | `#2CA02C` |
| NeuroCard | Gray | `#7F7F7F` |

Except for the StarCE family, each method uses a different hue (blue/green/orange/cyan/purple/brown/pink/olive/gray),
instantly distinguishable from one another.

**Why StarCE stands out most**: (1) Red is the only red tone in the figure, clearly separated from
blue/green/purple/orange groups; (2) When plotting, StarCE uses full opacity + thick black stroke, while
other methods use alpha≈0.65 and thin stroke (see `draw_violins` `emphasize_mask`).

**Display order** `METHOD_ORDER`: StarCE first (leftmost, most prominent), followed by DuckDB group →
SafeBound group → FactorJoin brown group → Flat green group.

## Shared Module `experiment/plot_style.py`

Each notebook's working directory is `experiment/`, with the import cell already containing
`sys.path.append(os.path.abspath('.'))`, so directly use:

```python
import plot_style
from plot_style import METHOD_COLORS, METHOD_ORDER, get_method_color, \
    method_display_name, generate_color_palette, draw_violins
```

Exported objects:

| Name | Description |
|------|------|
| `METHOD_COLORS` | Canonical display name → hex color dictionary (table above). |
| `METHOD_ORDER` | Method display order, StarCE first. |
| `method_display_name(name)` | Arbitrary case/alias → canonical display name (e.g., `postgres→Postgre`, `starce-upper→StarCE-Upper`). |
| `get_method_color(name)` | Get color by method name (case/alias insensitive), fallback `#BBBBBB` with warning for unknown. |
| `method_colors(names)` | Batch return `{display_name: color}`. |
| `generate_color_palette(n)` | Get n distinguishable colors for **non-method categories** (parameter sweeps, variants) from tab10/tab20. |
| `draw_violins(ax, dataset, positions, colors, widths, *, emphasize_mask=None)` | Unified violin drawing, returns violinplot dict. |

## Usage Conventions

- **Cross-method comparison figures** (accuracy, estimation latency) → use `METHOD_COLORS` / `get_method_color`,
  with `emphasize_mask=[m=='StarCE' for m in methods]` to highlight StarCE.
- **Parameter sweep figures** (CompressPrecision values, PredMethod variants, SplitStar variants, etc.
  — non-method categories) → use `generate_color_palette(n)` for distinct colors, do not use method colors.
- **Distribution figures always use violin plots**, not box plots: call `draw_violins` instead of `ax.bxp`/`ax.boxplot`.

## `draw_violins` Example

```python
# Data pre-arranged by position: dataset[i] is the i-th violin's column of values (e.g., log10 relative error)
methods = ['StarCE', 'DuckDB', 'Postgre', 'SafeBound']
colors  = [get_method_color(m) for m in methods]
emph    = [m == 'StarCE' for m in methods]

vp = draw_violins(ax, dataset, positions, colors, widths=0.8, emphasize_mask=emph)

legend_handles = [
    mpl.patches.Patch(color=get_method_color(m), label=method_display_name(m))
    for m in methods
]
ax.legend(handles=legend_handles, loc='upper center', ncol=len(methods))
```

## Figures Using This Style

| Notebook | Figure | Color Dimension |
|----------|-----|---------|
| EvaluateAccuracy | `accuracy_violin_joins.pdf` (JobJoin/StatsJoin), `accuracy_violin_predicates.pdf` (STATS/JOBM/JOBLight/JOBLightRanges) | Method |
| EvaluatePlanAndBuild | Estimation latency distribution violin plot | Method |
| EvaluateCompress | CompressPrecision violin plot (2 figures) | Parameter value |
| EvaluateSplitStar | SplitStar accuracy violin plot (2 figures) | Variant (hardcoded 4 colors) |
| EvaluatePredMethod | PredMethod violin plot | Variant label |
