"""StarCE 实验统一绘图样式。

集中管理跨方法配色、展示名、方法排序，以及提琴图绘制辅助函数，供
experiment/ 下各 Evaluate notebook 共用（notebook 工作目录为 experiment/，
已有 ``sys.path.append(os.path.abspath('.'))``，可直接 ``import plot_style``）。

配色原则：StarCE 独占全图唯一红色调（最醒目），其余方法按语义分四组，
组内共享色调、按深浅区分：
  - StarCE 家族   : 红   (StarCE / StarCE-upper)
  - G1 传统 DB    : 蓝   (DuckDB / Postgres)
  - G2 Bound      : 绿   (SafeBound / LpBound)
  - G3 PGM/因子   : 紫   (BayesCard / FactorJoin / DeepDB)
  - G4 学习/神经  : 橙   (Flat / NeuroCard)

用法约定：
  - 跨方法对比图（精度、估计延迟）用 ``METHOD_COLORS`` / ``get_method_color``。
  - 参数扫描图（CompressPrecision、PredMethod 变体等非方法类别）用
    ``generate_color_palette`` 取一组区分色。
"""

import matplotlib as mpl
from matplotlib.colors import to_hex


# ========== 统一方法配色（规范展示名 -> hex）==========
# 每个方法一个清晰独立的色相（无两个同色系），最大化区分度；红色只留给
# StarCE（全图唯一，配合满不透明度+粗描边=最醒目）。分组仅体现在出图顺序
# （见 METHOD_ORDER），不体现在颜色上。
METHOD_COLORS = {
    # StarCE 家族 —— 红（StarCE 唯一鲜红最醒目，Upper 深红同族）
    "StarCE":       "#E31A1C",
    "StarCE-Upper": "#7F0000",
    # 其余方法各自独立色相（避开红）
    "DuckDB":       "#1F77B4",  # 蓝
    "Postgres":     "#17BECF",  # 青
    "SafeBound":    "#9467BD",  # 紫
    "LpBound":      "#E377C2",  # 粉
    "BayesCard":    "#FF7F0E",  # 橙
    "FactorJoin":   "#8C564B",  # 棕
    "DeepDB":       "#BCBD22",  # 橄榄
    "Flat":         "#2CA02C",  # 绿
    "NeuroCard":    "#7F7F7F",  # 灰
}

# 方法出图顺序：StarCE 置首（最左最醒目），其后 DuckDB 组、SafeBound 组、
# FactorJoin 紫组、Flat 橙组。
METHOD_ORDER = [
    "StarCE", "StarCE-Upper",
    "DuckDB", "Postgres",
    "SafeBound", "LpBound",
    "BayesCard", "FactorJoin", "DeepDB",
    "Flat", "NeuroCard",
]

# 未知方法回退色。
FALLBACK_COLOR = "#BBBBBB"

# 小写别名 -> 规范展示名。
_SPECIAL_CASES = {
    "duckdb": "DuckDB",
    "starce": "StarCE",
    "starce-upper": "StarCE-Upper",
    "safebound": "SafeBound",
    "factorjoin": "FactorJoin",
    "bayescard": "BayesCard",
    "flat": "Flat",
    "deepdb": "DeepDB",
    "neurocard": "NeuroCard",
    "lpbound": "LpBound",
    "postgres": "Postgres",
    "postgre": "Postgres",
    "postgresql": "Postgres",
}


def method_display_name(method_name):
    """把任意大小写/别名的方法名转换成规范展示名。"""
    base = method_name.lower()
    if base in _SPECIAL_CASES:
        return _SPECIAL_CASES[base]
    return method_name.replace("_", "-").title()


def get_method_color(method_name):
    """按方法名（大小写/别名不敏感）取统一配色，未知名回退灰色并告警。"""
    display = method_display_name(method_name)
    if display in METHOD_COLORS:
        return METHOD_COLORS[display]
    print(f"[plot_style] 未知方法 '{method_name}'（-> '{display}'），回退 {FALLBACK_COLOR}")
    return FALLBACK_COLOR


def method_colors(method_names):
    """批量返回 {规范展示名: 颜色}，供图例/循环使用。"""
    return {method_display_name(m): get_method_color(m) for m in method_names}


def generate_color_palette(n):
    """为非方法类别（参数扫描、变体等）生成 n 个区分色。

    收敛各 notebook 原先重复定义的实现：n<=10 用 tab10，否则 tab20。
    """
    if n <= 10:
        cmap = mpl.colormaps["tab10"]
        return [to_hex(cmap(i)) for i in range(n)]
    cmap = mpl.colormaps["tab20"]
    return [to_hex(cmap(i % 20)) for i in range(n)]


def draw_violins(ax, dataset, positions, colors, widths, *, emphasize_mask=None,
                 base_alpha=0.7, emph_alpha=1.0, edgecolor="black"):
    """在 ax 上绘制一组配色一致的提琴图。

    参数
    ----
    dataset : list[array-like]
        每个位置一列数值（如各方法的 log10 相对误差）。
    positions, widths : 传给 ``ax.violinplot``。
    colors : list[str]
        与 dataset 一一对应的填充色。
    emphasize_mask : list[bool] | None
        为真的 body 用满不透明度（StarCE 突出用）；None 表示不强调。提琴主体
        本身不描边（``edgecolor`` 仅用于内部中位线/须线）。
    返回
    ----
    matplotlib 的 violinplot 字典（含 'bodies' 等），供追加图例/微调。
    """
    vplot = ax.violinplot(
        dataset,
        positions=positions,
        widths=widths,
        showmeans=False,
        showmedians=True,
        showextrema=True,
    )

    for i, (body, color) in enumerate(zip(vplot["bodies"], colors)):
        emph = bool(emphasize_mask[i]) if emphasize_mask is not None else False
        body.set_facecolor(color)
        body.set_alpha(emph_alpha if emph else base_alpha)
        body.set_edgecolor("none")
        body.set_linewidth(0)

    for partname in ("cbars", "cmins", "cmaxes", "cmedians"):
        part = vplot.get(partname)
        if part is None:
            continue
        part.set_color(edgecolor)
        part.set_linewidth(1.2 if partname == "cmedians" else 0.6)

    return vplot
