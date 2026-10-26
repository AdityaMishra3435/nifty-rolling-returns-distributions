#!/usr/bin/env python3
"""
Nifty rolling-return distributions: one command, end to end.

Examples
    python run.py                                  # default 5 indices, 1/3/5/10/15Y
    python run.py --indices "NIFTY 50" "NIFTY 500"
    python run.py --windows 1 3 5 7 10 15
    python run.py --common-period                  # same date range for all indices
    python run.py --refresh                        # force re-download
    python run.py --offline                        # use cached/manual files only
    python run.py --demo                           # synthetic data, no internet needed
    python run.py --article                        # + still images / GIF of the dashboard views
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import webbrowser
from pathlib import Path

import pandas as pd

import analyze
import article_figures
import dashboard
import fetch
import report

DEFAULT_INDICES = ["NIFTY 50", "NIFTY 500", "NIFTY NEXT 50",
                   "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250"]
DEFAULT_WINDOWS = [1, 3, 5, 10, 15]
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def now_utc_ist() -> str:
    u = dt.datetime.now(dt.timezone.utc)
    return f"{u:%d %b %Y, %H:%M} UTC ({u.astimezone(IST):%d %b %Y, %H:%M} IST)"


def parse_args():
    p = argparse.ArgumentParser(description="Distributions of Nifty TRI rolling returns")
    p.add_argument("--indices", nargs="+", default=DEFAULT_INDICES,
                   help="Exact niftyindices.com names, e.g. \"NIFTY 50\" \"NIFTY 500\"")
    p.add_argument("--windows", nargs="+", type=int, default=DEFAULT_WINDOWS,
                   help="Rolling windows in years (default: 1 3 5 10 15)")
    p.add_argument("--common-period", action="store_true",
                   help="Trim every index to the latest common start date")
    p.add_argument("--refresh", action="store_true", help="Ignore cache and re-download")
    p.add_argument("--offline", action="store_true", help="Never hit the network")
    p.add_argument("--demo", action="store_true", help="Use synthetic data (offline test)")
    p.add_argument("--out", default="output", help="Output folder (default: output)")
    p.add_argument("--no-open", action="store_true", help="Don't open the report in a browser")
    p.add_argument("--article", action="store_true",
                   help="Also export article-ready images of the dashboard views (PNG + animated GIF)")
    p.add_argument("--article-indices", nargs="+", default=None,
                   help="Indices shown in the article images (default: NIFTY 50 and NIFTY 500)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    out = (root / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    windows = sorted(set(args.windows))
    print(f"\nNifty rolling-return distributions · {now_utc_ist()}")
    print(f"Windows: {', '.join(f'{w}Y' for w in windows)}\n")

    # ---------------------------------------------------------------- load data
    series: dict[str, pd.Series] = {}
    src_rows = []
    if args.demo:
        print("DEMO MODE: generating synthetic series (not real market data)\n")
        for name, (start, mu, vol, seed) in fetch.DEMO_SPECS.items():
            if name in args.indices or args.indices == DEFAULT_INDICES:
                series[name] = fetch.synthetic_tri(name, start, mu, vol, seed)
                src_rows.append((name, "SYNTHETIC demo data"))
    else:
        names = list(dict.fromkeys(args.indices))
        extras = fetch.manual_only_files(names)
        api = None
        if not args.offline:
            print("Checking the niftyindices.com API...")
            api = fetch.Api()
            ok = api.check()
            for line in api.report:
                print("  " + line)
            if ok:
                print("  → API works. Downloading (first run fetches each index year by year;"
                      " later runs only add new days).\n")
            else:
                print("  → API not usable right now. Using cached / manual files only."
                      " Details saved in data/debug/.\n")
        for name in names + list(extras):
            print(f"  {name:<24}", end="", flush=True)
            fetch.PROGRESS["printed"] = False
            if name in extras:
                try:
                    s, src = fetch.read_any_csv(extras[name]), f"manual file {extras[name].name}"
                except Exception as e:  # noqa: BLE001
                    s, src = None, f"could not read manual file: {e}"
            else:
                s, src = fetch.load_index(name, api, refresh=args.refresh, offline=args.offline)
                if src.startswith(("NETWORK", "BLOCKED")) and api is not None:
                    api.url = None  # the site stopped working mid-run; don't hammer it
            if fetch.PROGRESS["printed"]:
                print("\n" + " " * 26, end="")
            if s is None or len(s) < 300:
                print(f"SKIPPED  ({src})")
                src_rows.append((name, f"SKIPPED: {src}"))
                continue
            series[name] = s
            print(f"{len(s):>6,} days  {s.index[0].date()} → {s.index[-1].date()}  [{src}]")
            gaps = fetch.gap_report(s)
            if gaps:
                print(f"{'':26}warning: {len(gaps)} gap(s) over 10 days, e.g. {gaps[0]}")
            src_rows.append((name, src))

    if not series:
        print("\nNo data could be loaded.")
        print("  1. Run:  python check_api.py   and share its output (also saved to data/debug/).")
        print("  2. Meanwhile, download the CSVs by hand: README.md → 'If the automatic download fails'.")
        return 1

    common_txt = None
    if args.common_period and len(series) > 1:
        start = max(s.index[0] for s in series.values())
        end = min(s.index[-1] for s in series.values())
        series = {k: v[(v.index >= start) & (v.index <= end)] for k, v in series.items()}
        common_txt = f"{start.date()} to {end.date()}"
        print(f"\nCommon period applied: {common_txt}")

    sources = pd.DataFrame([
        {"Index": n, "Source": src,
         "First date": series[n].index[0].date() if n in series else "",
         "Last date": series[n].index[-1].date() if n in series else "",
         "Trading days": f"{len(series[n]):,}" if n in series else "",
         "Years of history": round((series[n].index[-1] - series[n].index[0]).days / 365.25, 1)
         if n in series else ""}
        for n, src in src_rows])

    # ---------------------------------------------------------------- compute
    rr = analyze.compute_all(series, windows)
    summary = analyze.summarize(rr, series)
    missing = [(n, w) for n in series for w in windows
               if not ((rr["index"] == n) & (rr["window_years"] == w)).any()]
    for n, w in missing:
        print(f"  note: {n} has less than {w} years of data, so no {w}Y windows")

    rr_out = rr.copy()
    rr_out["cagr_pct"] = (rr_out.pop("cagr") * 100).round(4)
    rr_out.to_csv(out / "rolling_returns_all.csv", index=False)
    summary.to_csv(out / "summary_statistics.csv", index=False)

    # ---------------------------------------------------------------- plots
    tag = " [SYNTHETIC DEMO DATA]" if args.demo else ""
    tag += f" · {common_txt}" if common_txt else ""
    print("\nDrawing charts...")
    per_index = {}
    for name in series:
        sl = fetch.slug(name)
        per_index[name] = {
            "dist": analyze.plot_index_distributions(
                name, rr, windows, out / "charts" / f"distribution_{sl}.png", tag),
            "ts": analyze.plot_index_timeseries(
                name, rr, windows, out / "charts" / f"timeseries_{sl}.png", tag),
        }
    comp = analyze.plot_index_comparison(rr, list(series), windows,
                                         out / "charts" / "comparison_across_indices.png", tag)

    rpt = report.build_report(
        out / "report.html",
        title="Nifty TRI rolling returns: distributions" + (" (DEMO)" if args.demo else ""),
        generated=now_utc_ist(), sources=sources, summary=summary,
        per_index_imgs=per_index, comparison_img=comp, demo=args.demo,
        common_period=common_txt)

    dash, plotly_desc = dashboard.build_dashboard(series, out / "dashboard.html", demo=args.demo,
                                                  generated=now_utc_ist())

    imgs = []
    if args.article:
        print("Exporting article images (the animated GIF takes a minute)...")
        imgs = article_figures.export_all(series, out / "article", demo=args.demo,
                                          names=args.article_indices)

    # ---------------------------------------------------------------- console summary
    pd.set_option("display.width", 200)
    view = summary[["Index", "Window (yrs)", "No. of windows", "Median", "P10", "P90",
                    "Min", "Max", "% negative"]].copy()
    for c in ["Median", "P10", "P90", "Min", "Max", "% negative"]:
        view[c] = view[c].map(lambda v: f"{v:.1%}")
    print("\n" + view.to_string(index=False))
    print(f"\nDone. Outputs in: {out}")
    print(f"  dashboard.html            ← interactive: pick indices, holding periods, start years")
    print(f"  report.html               ← static summary with all charts")
    print(f"  summary_statistics.csv    ← all stats")
    print(f"  rolling_returns_all.csv   ← every window, for your own analysis")
    print(f"  charts/                   ← PNG charts")
    if imgs:
        print(f"  article/                  ← images of the dashboard views (PNG + animated GIF)")
    print()
    if not args.no_open:
        try:
            webbrowser.open(dash.as_uri())
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
