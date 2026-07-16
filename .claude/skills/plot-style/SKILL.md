---
name: plot-style
description: StarCE 实验图表统一绘图样式：跨方法配色方案（StarCE 独占醒目红，DuckDB/SafeBound/FactorJoin/Flat 四组按色调分组）、experiment/plot_style.py 共享模块（METHOD_COLORS/METHOD_ORDER/get_method_color/generate_color_palette/draw_violins）、提琴图绘制约定。当用户提到绘图配色、图表样式、方法颜色、箱线图改提琴图、violin、精度图/延迟分布图配色、统一图例、plot_style 时使用。
---

# StarCE 实验统一绘图样式

所有 Evaluate notebook 共用一套配色与提琴图辅助函数，集中在
`experiment/plot_style.py`。目标：**StarCE 在任何图里都最醒目**，其余方法按语义
分组、组内同色调，跨图一致。

## 配色方案

每个方法一个**清晰独立的色相**（无两个同色系，最大化区分度）；**红色只留给
StarCE**（全图唯一，配合满不透明度+粗描边=最醒目）。分组只体现在出图顺序
（`METHOD_ORDER`），不体现在颜色上。

| 方法 | 色 | Hex |
|------|----|-----|
| **StarCE** | 鲜红（全图唯一、最醒目） | `#E31A1C` |
| StarCE-Upper | 深红/栗（StarCE 同族变体） | `#7F0000` |
| DuckDB | 蓝 | `#1F77B4` |
| Postgre | 青 | `#17BECF` |
| SafeBound | 紫 | `#9467BD` |
| LpBound | 粉 | `#E377C2` |
| BayesCard | 橙 | `#FF7F0E` |
| FactorJoin | 棕 | `#8C564B` |
| DeepDB | 橄榄 | `#BCBD22` |
| Flat | 绿 | `#2CA02C` |
| NeuroCard | 灰 | `#7F7F7F` |

除 StarCE 家族外，每个方法都是不同色相（蓝/绿/橙/青/紫/棕/粉/橄榄/灰），彼此
一眼可分。

**StarCE 为何最醒目**：① 红色是全图唯一红调，与蓝/绿/紫/橙四组明显拉开；
② 绘图时 StarCE 用满不透明度 + 粗黑描边，其余方法 alpha≈0.65、细描边
（见 `draw_violins` 的 `emphasize_mask`）。

**出图顺序** `METHOD_ORDER`：StarCE 置首（最左最醒目），其后 DuckDB 组 →
SafeBound 组 → FactorJoin 紫组 → Flat 橙组。

## 共享模块 `experiment/plot_style.py`

各 notebook 工作目录为 `experiment/`，import cell 已有
`sys.path.append(os.path.abspath('.'))`，直接：

```python
import plot_style
from plot_style import METHOD_COLORS, METHOD_ORDER, get_method_color, \
    method_display_name, generate_color_palette, draw_violins
```

导出对象：

| 名称 | 说明 |
|------|------|
| `METHOD_COLORS` | 规范展示名 → hex 的配色字典（上表）。 |
| `METHOD_ORDER` | 方法出图顺序，StarCE 置首。 |
| `method_display_name(name)` | 任意大小写/别名 → 规范展示名（`postgres→Postgre`、`starce-upper→StarCE-Upper` 等）。 |
| `get_method_color(name)` | 按方法名（大小写/别名不敏感）取色，未知名回退 `#BBBBBB` 并告警。 |
| `method_colors(names)` | 批量返回 `{展示名: 色}`。 |
| `generate_color_palette(n)` | 为**非方法类别**（参数扫描、变体）取 n 个区分色（tab10/tab20）。 |
| `draw_violins(ax, dataset, positions, colors, widths, *, emphasize_mask=None)` | 统一提琴绘制，返回 violinplot 字典。 |

## 用法约定

- **跨方法对比图**（精度、估计延迟）→ 用 `METHOD_COLORS` / `get_method_color`，
  并以 `emphasize_mask=[m=='StarCE' for m in methods]` 突出 StarCE。
- **参数扫描图**（CompressPrecision 值、PredMethod 变体、SplitStar variant 等
  非方法类别）→ 用 `generate_color_palette(n)` 取区分色，不接入方法配色。
- **分布图一律用提琴图**，不用箱线：调 `draw_violins` 而非 `ax.bxp`/`ax.boxplot`。

## `draw_violins` 示例

```python
# 数据已按位置排好：dataset[i] 是第 i 个提琴的一列数值（如 log10 相对误差）
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

## 使用该样式的图

| Notebook | 图 | 配色维度 |
|----------|-----|---------|
| EvaluateAccuracy | `accuracy_violin_joins.pdf`（JobJoin/StatsJoin）、`accuracy_violin_predicates.pdf`（STATS/JOBM/JOBLight/JOBLightRanges） | 方法 |
| EvaluatePlanAndBuild | 估计延迟分布提琴图 | 方法 |
| EvaluateCompress | CompressPrecision 提琴图（2 张） | 参数值 |
| EvaluateSplitStar | SplitStar 精度提琴图（2 张） | variant（硬编码 4 色） |
| EvaluatePredMethod | PredMethod 提琴图 | 变体 label |
