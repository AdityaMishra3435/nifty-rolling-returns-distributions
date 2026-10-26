"""
Article-ready images of the dashboard views, for platforms that can't run the
interactive file (Substack, Medium, LinkedIn, email):

    output/article/funnel.png
    output/article/ridgeline.png
    output/article/heatmap.png
    output/article/histogram_animation.gif

Same calculations as the dashboard: rolling CAGR for every trading-day start,
holding periods stepped by month.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from analyze import kde  # noqa: E402

PALETTE = ["#1d5c7a", "#d98c1e", "#7a3b69", "#5b7f3a", "#b5473a"]
INK, MUTED, LINE, NEG = "#18262e", "#5a6b74", "#d5dde0", "#b5473a"
PCT = FuncFormatter(lambda v, _: f"{v:.0%}")
plt.rcParams.update({"font.size": 11, "axes.edgecolor": LINE, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.titleweight": "bold"})


def rolling_months(tri: pd.Series, months: int) -> tuple[np.ndarray, float]:
    """Sorted CAGRs for every start date, and the number of independent periods."""
    idx = tri.index
    target = idx - pd.DateOffset(months=months)
    pos = idx.searchsorted(target, side="right") - 1
    ok = (target >= idx[0]) & (pos >= 0)
    if not ok.any():
        return np.array([]), 0.0
    e, s = np.where(ok)[0], pos[ok]
    days = (idx[e] - idx[s]).days.values.astype(float)
    cagr = (tri.values[e] / tri.values[s]) ** (365.25 / days) - 1.0
    span = (idx[e[-1]] - idx[s[0]]).days / 365.25
    return np.sort(cagr), span / (months / 12)


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.35, color=LINE)


def _footer(fig, text):
    import textwrap
    fig.text(0.01, 0.01, textwrap.fill(text, 150), fontsize=8.5, color=MUTED, ha="left", va="bottom")


def _stats(series, names, months):
    out = {}
    for n in names:
        rows = []
        for m in months:
            x, ind = rolling_months(series[n], m)
            if len(x) < 20:
                continue
            q = np.quantile(x, [.05, .10, .25, .5, .75, .90, .95])
            rows.append((m, *q, ind, x))
        out[n] = rows
    return out


def funnel(series, names, path, foot, max_years=20):
    months = list(range(12, max_years * 12 + 1))
    st = _stats(series, names, months)
    fig, ax = plt.subplots(figsize=(10, 5.8))
    multi = len(names) > 1
    for i, n in enumerate(names):
        rows = st[n]
        if not rows:
            continue
        c = PALETTE[i % len(PALETTE)]
        x = np.array([r[0] / 12 for r in rows])
        p5, p25, p50, p75, p95 = (np.array([r[k] for r in rows]) for k in (1, 3, 4, 5, 7))
        ind = np.array([r[8] for r in rows])
        if not multi:
            ax.fill_between(x, p5, p95, color=c, alpha=.12, lw=0)
        else:
            ax.plot(x, p5, color=c, lw=.9, alpha=.8)
            ax.plot(x, p95, color=c, lw=.9, alpha=.8)
        ax.fill_between(x, p25, p75, color=c, alpha=.22 if multi else .28, lw=0)
        solid = np.where(ind >= 2, p50, np.nan)
        dotted = np.where(ind < 2, p50, np.nan)
        k = np.argmax(ind < 2) if (ind < 2).any() else None
        if k:
            dotted[k - 1] = p50[k - 1]  # join the two pieces
        ax.plot(x, solid, color=c, lw=2.6, label=n)
        ax.plot(x, dotted, color=c, lw=2.2, ls=(0, (1.5, 1.5)))
    ax.axhline(0, color=NEG, lw=1, ls=":")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlim(1, max_years)
    ax.set_xticks(range(1, max_years + 1, 1 if max_years <= 12 else 2))
    ax.set_xlabel("Holding period (years)")
    ax.set_ylabel("Annualised return")
    ax.set_title("How the range of returns narrows as you hold longer", loc="left", fontsize=14)
    ax.legend(frameon=False, loc="upper right")
    _style(ax)
    band = "shaded: middle 50%; thin lines: 90% range" if multi else "dark band: middle 50%; light band: 90% range"
    _footer(fig, f"Line: median; {band}; dotted: under 2 independent periods of history. {foot}")
    fig.tight_layout(rect=(0, 0.065, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def ridgeline(series, names, path, foot, horizons=(1, 2, 3, 4, 5, 7, 10, 12, 15, 20)):
    hs = [h for h in horizons if any(len(rolling_months(series[n], h * 12)[0]) >= 20 for n in names)]
    if not hs:
        return
    lo, hi = np.inf, -np.inf
    for n in names:
        x, _ = rolling_months(series[n], hs[0] * 12)
        if len(x):
            lo, hi = min(lo, np.quantile(x, .005)), max(hi, np.quantile(x, .995))
    lo, hi = max(lo, -0.8), min(hi, 2.0)
    pad = (hi - lo) * .04
    grid = np.linspace(lo - pad, hi + pad, 400)
    fig, ax = plt.subplots(figsize=(10, 7.2))
    rows = len(hs)
    for k, h in enumerate(hs):
        off = rows - 1 - k
        z = 10 + 2 * k
        thin = None
        for i, n in enumerate(names):
            x, ind = rolling_months(series[n], h * 12)
            if len(x) < 20:
                continue
            d = kde(x, grid)
            d = d / d.max() * 1.55
            keep = d > 0.006
            gx, gy = grid[keep], off + d[keep]
            c = PALETTE[i % len(PALETTE)]
            ax.fill_between(gx, off, gy, color="white", lw=0, zorder=z)
            ax.fill_between(gx, off, gy, color=c, alpha=.20 if len(names) > 1 else .34, lw=0, zorder=z + 1)
            ax.plot(gx, gy, color=c, lw=1.6, zorder=z + 1, label=n if k == 0 else None)
            med = np.median(x)
            ax.plot([med, med], [off, off + np.interp(med, grid, d)], color=c, lw=2.4, zorder=z + 1)
            if ind < 2:
                thin = f"≈{ind:.1f} independent periods"
        if thin:
            ax.text(grid[-1], off + .25, thin, ha="right", fontsize=8.5, color=MUTED, zorder=50)
    ax.axvline(0, color=NEG, lw=1, ls=":", zorder=60)
    ax.set_yticks(range(rows))
    ax.set_yticklabels([f"{h}Y" for h in reversed(hs)])
    ax.set_ylim(-0.3, rows + 0.9)
    ax.set_xlim(grid[0], grid[-1])
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Annualised return")
    ax.set_ylabel("Holding period")
    ax.set_title("The distribution of returns for each holding period", loc="left", fontsize=14)
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=.35, color=LINE)
    _footer(fig, f"Each curve is scaled to the same height; width shows spread. Tick = median. {foot}")
    fig.tight_layout(rect=(0, 0.055, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def heatmap(series, name, path, foot, max_years=20):
    months = list(range(12, max_years * 12 + 1))
    cols = [(m, *rolling_months(series[name], m)) for m in months]
    cols = [c for c in cols if len(c[1]) >= 20]
    if not cols:
        return
    lo, hi = np.quantile(cols[0][1], .01), np.quantile(cols[0][1], .99)
    lo, hi = max(lo, -0.8), min(hi, 2.0)
    nb = 110
    edges = np.linspace(lo, hi, nb + 1)
    z = np.zeros((nb, len(cols)))
    for j, (_, x, _) in enumerate(cols):
        cnt, _ = np.histogram(x, bins=edges)
        z[:, j] = cnt / max(cnt.max(), 1)
    xs = np.array([c[0] / 12 for c in cols])
    cmap = LinearSegmentedColormap.from_list("t", ["#ffffff", "#cfe0e8", "#5f97b3", "#1d5c7a", "#0e3347"])
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.pcolormesh(xs, (edges[:-1] + edges[1:]) / 2, z, cmap=cmap, shading="nearest", rasterized=True)
    ax.plot(xs, [np.median(c[1]) for c in cols], color=INK, lw=2, label="Median")
    ax.plot(xs, [np.quantile(c[1], .1) for c in cols], color=INK, lw=1.1, ls="--", label="10th / 90th percentile")
    ax.plot(xs, [np.quantile(c[1], .9) for c in cols], color=INK, lw=1.1, ls="--")
    ax.axhline(0, color=NEG, lw=1, ls=":")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Holding period (years)")
    ax.set_ylabel("Annualised return")
    ax.set_title(f"{name}: how common each return was, by holding period", loc="left", fontsize=14)
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    _footer(fig, f"Darker = more common (each column shaded relative to its own most common return). {foot}")
    fig.tight_layout(rect=(0, 0.065, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def histogram_gif(series, names, path, foot, max_years=20, step=3, fps=8):
    months = [m for m in range(12, max_years * 12 + 1, step)]
    data = {n: {m: rolling_months(series[n], m) for m in months} for n in names}
    months = [m for m in months if any(len(data[n][m][0]) >= 20 for n in names)]
    if not months:
        return
    lo, hi = np.inf, -np.inf
    for n in names:
        x = data[n][months[0]][0]
        if len(x):
            lo, hi = min(lo, np.quantile(x, .005)), max(hi, np.quantile(x, .995))
    lo, hi = max(lo, -0.8), min(hi, 2.0)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    frames = months + [months[-1]] * fps * 2  # hold the last frame for ~2 seconds

    def draw(m):
        ax.clear()
        cl, ch = np.inf, -np.inf
        for n in names:
            x = data[n][m][0]
            if len(x) >= 20:
                cl, ch = min(cl, np.quantile(x, .01)), max(ch, np.quantile(x, .99))
        size = max(0.0025, (ch - cl) / 40)
        bins = np.arange(np.floor(min(lo, cl) / size) * size, max(hi, ch) + size, size)
        ymax, lines = 0, []
        for i, n in enumerate(names):
            x, ind = data[n][m]
            if len(x) < 20:
                continue
            c = PALETTE[i % len(PALETTE)]
            w = np.full(len(x), 100 / len(x))
            h, _, _ = ax.hist(x, bins=bins, weights=w, color=c, alpha=.55 if len(names) > 1 else .75,
                              edgecolor=c, linewidth=.5, label=n)
            ymax = max(ymax, h.max())
            med = np.median(x)
            ax.axvline(med, color=c, lw=1.6, ls="--")
            lines.append(f"{n}: median {med:.1%}, negative {np.mean(x < 0):.1%}")
        ax.axvline(0, color=NEG, lw=1, ls=":")
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, ymax * 1.12 if ymax else 1)
        ax.xaxis.set_major_formatter(PCT)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.set_xlabel("Annualised return")
        ax.set_ylabel("% of windows")
        yrs = f"{m // 12} yr" + (f" {m % 12} mo" if m % 12 else "")
        ax.set_title(f"Holding period: {yrs}", loc="left", fontsize=14)
        ax.text(0.99, 0.97, "\n".join(lines), transform=ax.transAxes, ha="right", va="top",
                fontsize=9, color=INK)
        ax.legend(frameon=False, loc="upper left")
        _style(ax)
        return []

    fig.text(0.01, 0.01, foot, fontsize=7.5, color=MUTED)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.9, bottom=0.17)
    anim = FuncAnimation(fig, draw, frames=frames, blit=False)
    anim.save(path, writer=PillowWriter(fps=fps), dpi=90)
    plt.close(fig)


def export_all(series: dict[str, pd.Series], out_dir: Path, *, demo: bool,
               names: list[str] | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pick = names or [n for n in ("NIFTY 50", "NIFTY 500") if n in series] or list(series)[:2]
    first = min(series[n].index[0] for n in pick).date()
    last = max(series[n].index[-1] for n in pick).date()
    foot = (("SYNTHETIC DEMO DATA. " if demo else "") +
            f"Data: NSE Indices Total Return Index, {first} to {last}.")
    paths = [out_dir / f for f in ("funnel.png", "ridgeline.png", "heatmap.png", "histogram_animation.gif")]
    funnel(series, pick, paths[0], foot)
    ridgeline(series, pick, paths[1], foot)
    heatmap(series, pick[0], paths[2], foot)
    histogram_gif(series, pick, paths[3], foot)
    return [p for p in paths if p.exists()]
