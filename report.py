"""Builds a single self-contained HTML report (images embedded as base64)."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import pandas as pd

PCT_COLS_PREFIX = ("Mean", "Median", "Std dev", "Min", "P5", "P10", "P25",
                   "P75", "P90", "P95", "Max", "%")

CSS = """
:root { --bg:#ffffff; --fg:#1d232b; --muted:#5b6672; --line:#e3e7ec; --card:#f7f9fb; --accent:#00798c; --warn:#fff6e0; --warnline:#e8c46a; }
@media (prefers-color-scheme: dark) {
  :root { color-scheme: dark; --bg:#14181d; --fg:#e7ebef; --muted:#9aa5b1; --line:#2b323a; --card:#1b2026; --accent:#4fc3d6; --warn:#2c2616; --warnline:#8a7334; }
  img.chart { background:#fff; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
main { max-width:1280px; margin:0 auto; padding:32px 24px 64px; }
h1 { font-size:28px; margin:0 0 4px; }
h2 { font-size:21px; margin:44px 0 12px; padding-top:12px; border-top:1px solid var(--line); }
h3 { font-size:16px; margin:24px 0 8px; color:var(--muted); font-weight:600; }
.meta { color:var(--muted); font-size:13px; }
.note { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 18px; margin:16px 0; }
.warn { background:var(--warn); border-color:var(--warnline); }
img.chart { width:100%; height:auto; border:1px solid var(--line); border-radius:10px; margin:8px 0 4px; }
.tablewrap { overflow-x:auto; border:1px solid var(--line); border-radius:10px; margin:8px 0 16px; }
table { border-collapse:collapse; width:100%; font-size:12.5px; font-variant-numeric:tabular-nums; }
th, td { padding:6px 9px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line); }
th { background:var(--card); position:sticky; top:0; font-weight:600; }
td:first-child, th:first-child, td:nth-child(2), th:nth-child(2) { text-align:left; }
nav a { color:var(--accent); margin-right:14px; text-decoration:none; font-size:14px; }
code { background:var(--card); padding:1px 5px; border-radius:4px; }
"""


def _img(path: Path) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f'<img class="chart" src="data:image/png;base64,{data}" alt="{html.escape(Path(path).stem)}">'


def _fmt_table(df: pd.DataFrame) -> str:
    d = df.copy()
    for c in d.columns:
        if str(c).startswith(PCT_COLS_PREFIX):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
    return '<div class="tablewrap">' + d.to_html(index=False, border=0, escape=True) + "</div>"


def build_report(path: Path, *, title: str, generated: str, sources: pd.DataFrame,
                 summary: pd.DataFrame, per_index_imgs: dict[str, dict[str, Path]],
                 comparison_img: Path | None, demo: bool, common_period: str | None) -> Path:
    names = list(per_index_imgs)
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
             f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>"]
    parts.append(f"<h1>{html.escape(title)}</h1><div class='meta'>Generated {html.escape(generated)}. "
                 f"For your own comparisons, open the interactive <a href='dashboard.html'>dashboard.html</a>.</div>")
    if demo:
        parts.append("<div class='note warn'><b>DEMO MODE — SYNTHETIC DATA.</b> These charts come from "
                     "randomly generated series that only mimic the shape of equity returns. "
                     "They are for checking that the code runs. Do not read anything into the numbers. "
                     "Run without <code>--demo</code> to use real NSE data.</div>")
    if common_period:
        parts.append(f"<div class='note'>All indices trimmed to a common period: {html.escape(common_period)}.</div>")

    nav = " ".join(f"<a href='#idx{i}'>{html.escape(n)}</a>" for i, n in enumerate(names))
    if comparison_img:
        nav += " <a href='#compare'>Comparison</a>"
    parts.append(f"<nav>{nav} <a href='#method'>Method &amp; caveats</a></nav>")

    parts.append("<h2>Data used</h2>" + _fmt_table(sources))

    for i, name in enumerate(names):
        imgs = per_index_imgs[name]
        parts.append(f"<h2 id='idx{i}'>{html.escape(name)} TRI</h2>")
        if imgs.get("dist"):
            parts.append(_img(imgs["dist"]))
        sub = summary[summary["Index"] == name].drop(columns=["Index"])
        parts.append("<h3>Summary statistics</h3>" + _fmt_table(sub))
        if imgs.get("ts"):
            parts.append("<h3>Rolling returns over time (by start date)</h3>" + _img(imgs["ts"]))

    if comparison_img:
        parts.append("<h2 id='compare'>Comparison across indices</h2>" + _img(comparison_img))

    parts.append("""
<h2 id='method'>Method &amp; caveats</h2>
<div class='note'>
<p><b>Data.</b> Daily Total Return Index (price + reinvested dividends) from NSE Indices Ltd (niftyindices.com), unless a manual file was used.</p>
<p><b>Rolling windows.</b> Every trading day with at least N years of history before it is a window end date. The start is the last trading day on or before the same calendar date N years earlier. Return is CAGR: (end/start)^(365.25/days) − 1.</p>
<p><b>Overlap.</b> Consecutive windows share almost all their days, so thousands of rolling windows are <i>not</i> thousands of independent outcomes. The “Non-overlapping periods” column shows roughly how many independent N-year periods the history contains. For 10- and 15-year windows that number is small (often under 3), so those distributions describe a couple of market cycles, not a stable long-run law.</p>
<p><b>Different histories.</b> Indices start on different dates (e.g. Nifty 500 TRI from 1999, Midcap 150 / Smallcap 250 TRI from 2005). Comparisons across indices therefore mix different market periods unless you use <code>--common-period</code>.</p>
<p><b>Pre-launch data.</b> Index values before an index’s launch date are back-calculated by NSE Indices, not live track records.</p>
<p><b>Costs and taxes.</b> TRI ignores fund expenses, tracking error and taxes. An index fund investor would have earned somewhat less.</p>
</div>""")
    parts.append("</main></body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
