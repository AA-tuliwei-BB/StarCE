"""Unified plotting style for StarCE experiments.

Centralizes cross-method color schemes, display names, method ordering, and violin plot helper functions for
use by Evaluate notebooks under experiment/ (notebook working directory is experiment/,
already has ``sys.path.append(os.path.abspath('.'))``, can directly ``import plot_style``).

Color principle: StarCE gets the only red tone in the entire figure (most eye-catching), other methods are grouped into four semantic groups,
sharing hues within groups, differentiated by shade:
  - StarCE family   : Red   (StarCE / StarCE-upper)
  - G1 Traditional DB    : Blue   (DuckDB / Postgres)
  - G2 Bound      : Green   (SafeBound / LpBound)
  - G3 PGM/Factor   : Purple   (BayesCard / FactorJoin / DeepDB)
  - G4 Learning/Neural  : Orange   (Flat / NeuroCard)

Usage conventions:
  - Cross-method comparison plots (accuracy, estimation latency) use ``METHOD_COLORS`` / ``get_method_color``.
  - Parameter sweep plots (CompressPrecision, PredMethod variants, etc., non-method categories) use
    ``generate_color_palette`` to get a set of distinguishing colors.
"""

import matplotlib as mpl
from matplotlib.colors import to_hex


# ========== Unified method colors (canonical display name -> hex) ==========
# Each method gets a clear, independent hue (no two share the same color family), maximizing differentiation; red is reserved only for
# StarCE (unique in the entire figure, full opacity + bold stroke = most eye-catching). Grouping is only reflected in the drawing order
# (see METHOD_ORDER), not in the colors.
METHOD_COLORS = {
    # StarCE family — Red (StarCE unique bright red most eye-catching, Upper dark red same family)
    "StarCE":       "#E31A1C",
    "StarCE-Upper": "#7F0000",
    # Other methods each get independent hues (avoiding red)
    "DuckDB":       "#1F77B4",  # Blue
    "Postgres":     "#17BECF",  # Cyan
    "SafeBound":    "#9467BD",  # Purple
    "LpBound":      "#E377C2",  # Pink
    "BayesCard":    "#FF7F0E",  # Orange
    "FactorJoin":   "#8C564B",  # Brown
    "DeepDB":       "#BCBD22",  # Olive
    "Flat":         "#2CA02C",  # Green
    "NeuroCard":    "#7F7F7F",  # Gray
}

# Method drawing order: StarCE first (leftmost, most eye-catching), then DuckDB group, SafeBound group,
# FactorJoin purple group, Flat orange group.
METHOD_ORDER = [
    "StarCE", "StarCE-Upper",
    "DuckDB", "Postgres",
    "SafeBound", "LpBound",
    "BayesCard", "FactorJoin", "DeepDB",
    "Flat", "NeuroCard",
]

# Fallback color for unknown methods.
FALLBACK_COLOR = "#BBBBBB"

# Lowercase alias -> canonical display name.
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
    """Convert method names of any case/alias to canonical display names."""
    base = method_name.lower()
    if base in _SPECIAL_CASES:
        return _SPECIAL_CASES[base]
    return method_name.replace("_", "-").title()


def get_method_color(method_name):
    """Get unified color by method name (case/alias insensitive), fallback gray with warning for unknowns."""
    display = method_display_name(method_name)
    if display in METHOD_COLORS:
        return METHOD_COLORS[display]
    print(f"[plot_style] Unknown method '{method_name}'（-> '{display}'）, fallback  {FALLBACK_COLOR}")
    return FALLBACK_COLOR


def method_colors(method_names):
    """Batch return {canonical display name: color}, for legend/loop use."""
    return {method_display_name(m): get_method_color(m) for m in method_names}


def generate_color_palette(n):
    """Generate n distinguishing colors for non-method categories (parameter sweeps, variants, etc.).

    Converge previously duplicated implementations across notebooks: tab10 for n<=10, tab20 otherwise.
    """
    if n <= 10:
        cmap = mpl.colormaps["tab10"]
        return [to_hex(cmap(i)) for i in range(n)]
    cmap = mpl.colormaps["tab20"]
    return [to_hex(cmap(i % 20)) for i in range(n)]


def draw_violins(ax, dataset, positions, colors, widths, *, emphasize_mask=None,
                 base_alpha=0.7, emph_alpha=1.0, edgecolor="black"):
    """Draw a set of consistently-colored violin plots on ax.

    Parameters
    ----------
    dataset : list[array-like]
        One numeric column per position (e.g. log10 relative error of each method).
    positions, widths : passed to ``ax.violinplot``.
    colors : list[str]
        Fill colors one-to-one with dataset.
    emphasize_mask : list[bool] | None
        True bodies use full opacity (for highlighting StarCE); None means no emphasis. The violin body
        itself has no edge (``edgecolor`` only used for internal median/whisker lines).
    Returns
    -------
    matplotlib violinplot dict (contains 'bodies' etc.), for adding legend/fine-tuning.
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
