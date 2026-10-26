"""
Rolling-return computation, summary statistics and plots.

A rolling N-year return is computed for EVERY trading day that has at least
N years of history before it:
    start = last trading day on or before (end_date - N years)
    CAGR  = (TRI_end / TRI_start) ** (365.25 / days_between) - 1
For the 1-year window this is (almost exactly) the plain 1-year return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

THRESHOLDS = [0.0, 0.07, 0.10, 0.12, 0.15]
WINDOW_COLORS = ["#d1495b", "#edae49", "#66a182", "#00798c", "#2e4057",
                 "#8d6cab", "#6b4e16"]
INDEX_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
                "#8c564b", "#e377c2", "#17becf", "#7f7f7f", "#bcbd22"]
PCT = FuncFormatter(lambda v, _: f"{v:.0%}")


# --------------------------------------------------------------------------- #
# Computation
# --------------------------------------------------------------------------- #
def rolling_cagr(tri: pd.Series, years: int) -> pd.DataFrame:
    idx = tri.index
    target = idx - pd.DateOffset(years=years)
    pos = idx.searchsorted(target, side="right") - 1
    ok = (target >= idx[0]) & (pos >= 0)
    if not ok.any():
        return pd.DataFrame(columns=["start_date", "end_date", "cagr"])
    end_dates = idx[ok]
    start_pos = pos[ok]
    start_dates = idx[start_pos]
    v_end = tri.values[ok]
    v_start = tri.values[start_pos]
    days = (end_dates - start_dates).days.values.astype(float)
    cagr = (v_end / v_start) ** (365.25 / days) - 1.0
    return pd.DataFrame({"start_date": start_dates, "end_date": end_dates, "cagr": cagr})


def compute_all(series: dict[str, pd.Series], windows: list[int]) -> pd.DataFrame:
    frames = []
    for name, s in series.items():
        for w in windows:
            df = rolling_cagr(s, w)
            if len(df):
                df.insert(0, "window_years", w)
                df.insert(0, "index", name)
                frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["index", "window_years", "start_date", "end_date", "cagr"])
    return pd.concat(frames, ignore_index=True)


def summarize(rr: pd.DataFrame, series: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    for (name, w), g in rr.groupby(["index", "window_years"], sort=False):
        x = g["cagr"].values
        span_years = (series[name].index[-1] - series[name].index[0]).days / 365.25
        q = np.quantile(x, [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
        row = {
            "Index": name,
            "Window (yrs)": w,
            "No. of windows": len(x),
            "First start": g["start_date"].min().date(),
            "Last start": g["start_date"].max().date(),
            "Non-overlapping periods": round(span_years / w, 1),
            "Mean": x.mean(),
            "Median": q[3],
            "Std dev": x.std(ddof=1) if len(x) > 1 else np.nan,
            "Min": x.min(),
            "P5": q[0], "P10": q[1], "P25": q[2],
            "P75": q[4], "P90": q[5], "P95": q[6],
            "Max": x.max(),
        }
        row["% negative"] = (x < 0).mean()
        for t in THRESHOLDS[1:]:
            row[f"% below {t:.0%}"] = (x < t).mean()
        for t in THRESHOLDS[2:]:
            row[f"% above {t:.0%}"] = (x > t).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def kde(x: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Gaussian KDE with Silverman's bandwidth (numpy only, no scipy needed)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return np.zeros_like(grid)
    sd = x.std(ddof=1)
    iqr = np.subtract(*np.quantile(x, [0.75, 0.25]))
    scale = min(sd, iqr / 1.349) if iqr > 0 else sd
    bw = 0.9 * scale * n ** (-0.2) if scale > 0 else 1e-3
    out = np.zeros_like(grid)
    # chunk to keep memory modest
    for i in range(0, n, 2000):
        z = (grid[None, :] - x[i:i + 2000, None]) / bw
        out += np.exp(-0.5 * z * z).sum(axis=0)
    return out / (n * bw * np.sqrt(2 * np.pi))


# --------------------------------------------------------------------------- #
# Plots
# --------------------------------------------------------------------------- #
def _bins(x: np.ndarray) -> np.ndarray:
    edges = np.histogram_bin_edges(x, bins="fd")
    nb = int(np.clip(len(edges) - 1, 30, 80))
    return np.linspace(x.min(), x.max(), nb + 1)


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def _hist_panel(ax, x, color, title, show_kde=True):
    bins = _bins(x)
    width = bins[1] - bins[0]
    weights = np.full(len(x), 1.0 / len(x))
    ax.hist(x, bins=bins, weights=weights, color=color, alpha=0.55,
            edgecolor="white", linewidth=0.4)
    if show_kde:
        grid = np.linspace(x.min() - 3 * width, x.max() + 3 * width, 400)
        ax.plot(grid, kde(x, grid) * width, color=color, lw=1.8)
    p10, med, p90 = np.quantile(x, [0.10, 0.50, 0.90])
    ymax = ax.get_ylim()[1]
    ax.axvline(med, color="black", lw=1.4)
    ax.axvline(p10, color="black", lw=1, ls="--")
    ax.axvline(p90, color="black", lw=1, ls="--")
    if x.min() < 0 < x.max():
        ax.axvline(0, color="#b00020", lw=1, ls=":")
    ax.text(med, ymax * 0.97, f" median {med:.1%}", va="top", fontsize=8)
    ax.text(p10, ymax * 0.84, f"P10 {p10:.1%} ", va="top", ha="right", fontsize=8)
    ax.text(p90, ymax * 0.84, f" P90 {p90:.1%}", va="top", fontsize=8)
    neg = (x < 0).mean()
    ax.set_title(f"{title}\n{len(x):,} windows · {neg:.1%} negative", fontsize=10)
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Annualised return (CAGR)")
    ax.set_ylabel("% of windows")
    _style(ax)


def plot_index_distributions(name: str, rr: pd.DataFrame, windows: list[int],
                             path, subtitle: str = ""):
    g = rr[rr["index"] == name]
    present = [w for w in windows if (g["window_years"] == w).any()]
    if not present:
        return None
    n_panels = len(present) + 1
    ncols = 3
    nrows = int(np.ceil(n_panels / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 4.6 * nrows))
    axes = np.atleast_1d(axes).ravel()
    for i, w in enumerate(present):
        x = g.loc[g["window_years"] == w, "cagr"].values
        _hist_panel(axes[i], x, WINDOW_COLORS[i % len(WINDOW_COLORS)], f"{w}-year rolling")
    # percentile "funnel": how the range narrows as the holding period grows
    ax = axes[len(present)]
    for i, w in enumerate(present):
        x = g.loc[g["window_years"] == w, "cagr"].values
        mn, p5, p25, med, p75, p95, mx = np.quantile(x, [0, .05, .25, .5, .75, .95, 1])
        c = WINDOW_COLORS[i % len(WINDOW_COLORS)]
        y = len(present) - 1 - i
        ax.plot([mn, mx], [y, y], color=c, lw=1, alpha=0.6)
        ax.plot([p5, p95], [y, y], color=c, lw=6, alpha=0.45, solid_capstyle="butt")
        ax.plot([p25, p75], [y, y], color=c, lw=13, solid_capstyle="butt")
        ax.plot([med], [y], marker="o", color="white", mec="black", ms=7, zorder=5)
        ax.text(med, y + 0.33, f"{med:.1%}", ha="center", fontsize=8)
    ax.axvline(0, color="#b00020", lw=1, ls=":")
    ax.set_yticks(range(len(present)))
    ax.set_yticklabels([f"{w}Y" for w in reversed(present)])
    ax.set_ylim(-0.6, len(present) - 0.3)
    ax.set_title("Range by holding period\nthin = min–max · mid = P5–P95 · "
                 "thick = P25–P75 · dot = median", fontsize=10)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Annualised return (CAGR)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    for ax in axes[n_panels:]:
        ax.set_visible(False)
    fig.suptitle(f"{name} TRI: distribution of rolling returns{subtitle}",
                 fontsize=14, fontweight="bold")
    fig.text(0.5, 0.005, "Solid line = median, dashed = 10th/90th percentile, dotted red = 0%. "
             "Each panel has its own x-axis scale. Every trading day is a window end date; windows overlap heavily.",
             ha="center", fontsize=8.5, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_index_comparison(rr: pd.DataFrame, names: list[str], windows: list[int],
                          path, subtitle: str = ""):
    present = [w for w in windows if (rr["window_years"] == w).any()]
    if not present or len(names) < 2:
        return None
    ncols = min(3, len(present))
    nrows = int(np.ceil(len(present) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5.6 * ncols, 4.3 * nrows))
    axes = np.atleast_1d(axes).ravel()
    for i, w in enumerate(present):
        ax = axes[i]
        sub = rr[rr["window_years"] == w]
        lo, hi = np.quantile(sub["cagr"], [0.002, 0.998])
        grid = np.linspace(lo, hi, 400)
        for j, name in enumerate(names):
            x = sub.loc[sub["index"] == name, "cagr"].values
            if len(x) < 30:
                continue
            c = INDEX_COLORS[j % len(INDEX_COLORS)]
            ax.plot(grid, kde(x, grid), color=c, lw=2)
            ax.axvline(np.median(x), color=c, lw=0.9, ls="--")
        ax.axvline(0, color="#b00020", lw=1, ls=":")
        ax.set_title(f"{w}-year rolling", fontsize=11)
        ax.xaxis.set_major_formatter(PCT)
        ax.set_yticks([])
        _style(ax)
    handles = [plt.Line2D([], [], color=INDEX_COLORS[j % len(INDEX_COLORS)], lw=2.5)
               for j in range(len(names))]
    labels = list(names)
    handles.append(plt.Line2D([], [], color="gray", lw=1, ls="--"))
    labels.append("median (same colour)")
    spare = axes[len(present):]
    if len(spare):
        spare[0].axis("off")
        spare[0].legend(handles, labels, loc="center", frameon=False, fontsize=11)
        for ax in spare[1:]:
            ax.set_visible(False)
    else:
        fig.legend(handles, labels, loc="lower center", ncol=min(len(labels), 6),
                   frameon=False, bbox_to_anchor=(0.5, 0.02))
    fig.suptitle(f"Rolling-return distributions compared across indices{subtitle}",
                 fontsize=14, fontweight="bold")
    fig.text(0.5, 0.005, "Each index uses its own full history, so periods differ. "
             "For a like-for-like view, run with --common-period.",
             ha="center", fontsize=8.5, color="#555")
    fig.tight_layout(rect=(0, 0.06 if not len(spare) else 0.02, 1, 0.95))
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_index_timeseries(name: str, rr: pd.DataFrame, windows: list[int], path,
                          subtitle: str = ""):
    g = rr[rr["index"] == name]
    present = [w for w in windows if (g["window_years"] == w).any()]
    if not present:
        return None
    fig, ax = plt.subplots(figsize=(14, 5))
    for i, w in enumerate(present):
        sub = g[g["window_years"] == w]
        ax.plot(sub["start_date"], sub["cagr"], lw=1.1,
                color=WINDOW_COLORS[i % len(WINDOW_COLORS)], label=f"{w}Y")
    ax.axhline(0, color="#b00020", lw=1, ls=":")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Investment start date")
    ax.set_ylabel("Annualised return (CAGR)")
    ax.set_title(f"{name} TRI: rolling returns by start date{subtitle}",
                 fontsize=13, fontweight="bold")
    ax.legend(frameon=False, ncol=len(present))
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
