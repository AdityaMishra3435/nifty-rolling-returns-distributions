# Nifty rolling returns: the full distributions

Lots of people report the average, minimum and maximum rolling returns of the Nifty.
This shows the **whole distribution**: how often every outcome actually happened, for
holding periods from 1 to 20 years, across Nifty 50, Nifty 500, Nifty Next 50,
Nifty Midcap 150 and Nifty Smallcap 250.

The repo holds code only. Data goes stale, so the script downloads fresh official data
from NSE Indices every time you run it. Built with Claude.

**Historical analysis for education, not investment advice. Past returns do not predict
future returns.**

---

## Quick start

You need **Python 3.9 or newer** ([python.org/downloads](https://www.python.org/downloads/)).
On Windows, tick **"Add Python to PATH"** during installation.

1. Download this repo: green **Code** button → **Download ZIP**, then unzip it.
2. **Windows:** double-click `run_windows.bat`.
   **macOS / Linux:** open a terminal in the folder and run `./run_mac_linux.sh`.

The first run sets up a private Python environment (`.venv`) and installs the libraries
(1–2 minutes). It then checks the NSE Indices API and downloads each index's history one
year at a time (about 30 seconds per index). Later runs only fetch the new days. When it
finishes, the interactive dashboard opens in your browser.

**Just want to see what it produces?** `python run.py --demo` runs on synthetic data,
clearly labelled, with no download.

---

## What you get (in `output/`)

| File | What it is |
|---|---|
| `dashboard.html` | **Interactive explorer.** One file that works offline. Pick indices, holding periods (monthly steps), start years, and a common date range. |
| `report.html` | Static report: histograms for 1, 3, 5, 10 and 15-year windows for every index, plus a full statistics table |
| `summary_statistics.csv` | Count, mean, median, percentiles, min, max, % negative and threshold shares for every index × window |
| `rolling_returns_all.csv` | Every individual rolling window (index, window, start date, end date, CAGR %) |
| `charts/` | The report's charts as PNG files |
| `article/` | With `--article`: still images of the dashboard views plus an animated GIF |

### The dashboard's four views

| View | What it shows |
|---|---|
| **Funnel** | Holding period on the x-axis, with the median and percentile bands: the whole narrowing in one picture |
| **Ridgeline** | One distribution curve per holding period, stacked from shortest to longest |
| **Heatmap** | Holding period × return; colour shows how common each return was |
| **Animated histogram** | Press Play to sweep the holding period month by month, with live median, percentiles and % negative |

A table of key numbers follows your selections. Results based on fewer than 2 independent
periods of history are drawn dotted or greyed out.

---

## Options

```bash
python run.py --indices "NIFTY 50" "NIFTY 500"     # choose indices
python run.py --windows 1 3 5 7 10 15 20           # windows for the static report (years)
python run.py --common-period                      # same date range for every index
python run.py --article                            # + still images / GIF of the dashboard views
python run.py --refresh                            # ignore cached data, download everything again
python run.py --offline                            # use cached or manual files only
python run.py --demo                               # synthetic data, no internet needed
python run.py --no-open                            # don't open the browser
```

The launchers pass options through, e.g. `./run_mac_linux.sh --article`. Inside the
`.venv` you can also call `python run.py` directly (`.venv\Scripts\python run.py` on
Windows, `.venv/bin/python run.py` on Mac/Linux).

**Index names** must match the niftyindices.com dropdown spelling: `NIFTY 100`, `NIFTY 200`,
`NIFTY MIDCAP 100`, `NIFTY SMALLCAP 100`, `NIFTY LARGEMIDCAP 250`, `NIFTY TOTAL MARKET`,
`NIFTY100 LOW VOLATILITY 30`, `NIFTY200 MOMENTUM 30` and so on. A wrong name returns no data,
and the script says so.

---

## How the numbers are computed

Every trading day with enough history after it is a possible start date. For each start
date and holding period:

```
CAGR = (TRI_end / TRI_start) ^ (365.25 / days_between) − 1
```

The end is the same calendar date N years (or months) later, or the last trading day
before it. Data is the **Total Return Index** (price plus reinvested dividends), not the
headline price index.

Checks: a synthetic series growing exactly 10% a year returns 10.0000% in every window,
and the dashboard's in-browser calculations match the Python results exactly.

---

## Caveats

* **Overlapping windows aren't independent.** Consecutive start dates share almost all
  their days, so thousands of windows from ~27 years of data contain fewer than two truly
  separate 15-year periods. The "Non-overlapping periods" column and the dashboard's dotted
  lines flag this.
* **Different histories.** Data starts in mid-1999 for Nifty 50, 1999 for Nifty 500, late
  2002 for Next 50 and 2005 for Midcap 150 / Smallcap 250. Use `--common-period` (or the
  dashboard toggle) to compare like with like.
* **Back-calculated data.** Values before an index's launch date are computed backwards by
  NSE Indices.
* **No costs or taxes.** Real index funds earn somewhat less than the index.

---

## If the download fails

1. Run `python check_api.py` (inside `.venv`, as above). It tests each API call the script
   relies on and prints what the server returns. A copy is saved to `data/debug/`.
2. Meanwhile, download the data by hand: <https://www.niftyindices.com/reports/historical-data>
   → Equity → pick the index → **Total Returns Index** → earliest start date → download the CSV.
   Save it in `data/manual/`, named after the index (e.g. `NIFTY 50.csv`), and run the
   script again with `--offline`.

About the API: NSE does not document it. It moved in July 2026 to
`/BackPage/getTotalReturnIndexString` (the old `/Backpage.aspx/` path redirects to a login
page). It returns a JSON list of `{Date, TotalReturnsIndex, ...}` rows and needs a
browser-like User-Agent. Each run checks it first, trying the current and legacy paths, so a
future change shows up in seconds.

---

## Files

```
run.py              main script (options above)
fetch.py            download, cache and manual-CSV loading
analyze.py          rolling returns, statistics, report charts
report.py           static HTML report
dashboard.py        interactive dashboard
article_figures.py  still images + animated GIF of the dashboard views
check_api.py        tests which API calls work and what they return
run_windows.bat     one-click launcher (Windows)
run_mac_linux.sh    one-click launcher (macOS / Linux)
requirements.txt    pandas, numpy, matplotlib, requests, openpyxl, plotly
data/manual/        put manually downloaded CSVs here
data/tri/           download cache (created on first run, not committed)
```

## Data source and license

Data: NSE Indices Ltd, <https://www.niftyindices.com>, downloaded at run time and not
included in this repo. Code: MIT License (see `LICENSE`).
