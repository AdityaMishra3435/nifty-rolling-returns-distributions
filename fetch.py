"""
Data loading for Nifty Total Return Index (TRI) series.

Sources, in order of preference for each index:
  1. A CSV you placed in data/manual/   (manual download from niftyindices.com)
  2. A cached CSV in data/tri/          (topped up with only the missing recent days)
  3. A live download from niftyindices.com (official NSE Indices data)

What is known about the niftyindices.com API (checked Oct 2026, see README):
  - Endpoint moved in July 2026 to  POST /BackPage/getTotalReturnIndexString
    (the old /Backpage.aspx/ path redirects to a login page)
  - Response is a bare JSON list of rows: {"Date": "23 Oct 2026", "TotalReturnsIndex": "34351.79", ...}
  - The User-Agent must look like a browser, otherwise the server hangs instead of refusing
  - No cookies needed. A wrong index name returns an empty list with HTTP 200.
  - Requests of ~13 months are proven to work, so history is fetched one calendar year at a time.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = "https://www.niftyindices.com"
# Tried in order; the first one that answers with data is used for the whole run.
ENDPOINTS = [
    BASE + "/BackPage/getTotalReturnIndexString",       # current (since Jul 2026)
    BASE + "/Backpage.aspx/getTotalReturnIndexString",  # legacy, in case it comes back
]
PAGE_URL = BASE + "/reports/historical-data"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": PAGE_URL,
    "User-Agent": USER_AGENT,
}
TIMEOUT = (10, 90)      # (connect, read). Long read: a slow answer is not a failure.
PAUSE = 0.6             # seconds between requests, to be polite
EARLIEST_YEAR = 1995    # nothing published before this; empty years are skipped

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "data" / "tri"
MANUAL_DIR = ROOT / "data" / "manual"
DEBUG_DIR = ROOT / "data" / "debug"
PROGRESS = {"printed": False}  # lets run.py keep the console output tidy

# Spellings verified to return TRI data (Oct 2026). Others are tried as given.
NAME_ALTERNATIVES = {
    "NIFTY NEXT 50": ["NIFTY NEXT 50", "Nifty Next 50"],
    "NIFTY SMALLCAP 250": ["NIFTY SMALLCAP 250", "NIFTY SMLCAP 250"],
    "NIFTY 50": ["NIFTY 50", "Nifty 50"],
}

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _fmt(d: dt.date) -> str:
    """dd-MMM-yyyy, locale-independent (e.g. 01-Jul-2025)."""
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


class NetworkError(RuntimeError):
    """The site could not be reached at all (no internet, firewall, DNS...)."""


class BadResponseError(RuntimeError):
    """The site answered, but not with the expected data."""


class BlockedError(BadResponseError):
    """The site answered with an HTML page (moved endpoint / login / block page)."""


# --------------------------------------------------------------------------- #
# Low-level request + parsing
# --------------------------------------------------------------------------- #
def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _payload(name: str, start: dt.date, end: dt.date, style: str) -> str:
    if style == "single":   # format used by the site's own page
        cinfo = (f"{{'name':'{name}','startDate':'{_fmt(start)}',"
                 f"'endDate':'{_fmt(end)}','indexName':'{name}'}}")
    else:                   # standard JSON inside the string (also seen working)
        cinfo = json.dumps({"name": name, "startDate": _fmt(start),
                            "endDate": _fmt(end), "indexName": name})
    return json.dumps({"cinfo": cinfo})


def _strip(t: str) -> str:
    return t.lstrip("\ufeff \t\r\n")


def _loads_lenient(t: str):
    t = _strip(t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return ast.literal_eval(t)


def _parse_body(text: str) -> list[dict]:
    """Accepts the current bare-list format and the older {"d": "<json>"} envelope."""
    t = _strip(text or "")
    if not t:
        raise BadResponseError("empty response body")
    if t.startswith("<"):
        title = re.search(r"<title>(.*?)</title>", t, re.I | re.S)
        hint = f" (page title: {title.group(1).strip()[:80]})" if title else ""
        raise BlockedError("server returned an HTML page instead of data" + hint)
    try:
        outer = _loads_lenient(t)
    except (ValueError, SyntaxError) as e:
        raise BadResponseError(f"response is not JSON ({type(e).__name__})") from e
    d = outer.get("d", outer) if isinstance(outer, dict) else outer
    if isinstance(d, str):
        ds = _strip(d)
        if ds in ("", "null", "[]"):
            return []
        if ds.startswith("<"):
            raise BlockedError("data field contains HTML instead of rows")
        try:
            d = _loads_lenient(ds)
        except (ValueError, SyntaxError) as e:
            raise BadResponseError(f"data field is not valid JSON ({type(e).__name__})") from e
    if isinstance(d, dict):
        msg = d.get("Message") or d.get("message")
        if msg:
            raise BadResponseError(f"server error message: {str(msg)[:150]}")
        for k in ("data", "Data", "rows", "Rows", "Table"):
            if isinstance(d.get(k), list):
                d = d[k]
                break
    if not isinstance(d, list):
        raise BadResponseError(f"unexpected data shape: {type(d).__name__}")
    return [r for r in d if isinstance(r, dict)]


def _save_debug(tag: str, r: requests.Response, err: str) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    p = DEBUG_DIR / f"{tag}.txt"
    hdrs = "\n".join(f"{k}: {v}" for k, v in r.headers.items())
    hist = " -> ".join(f"{h.status_code} {h.headers.get('Location', '')}" for h in r.history)
    body = r.text or ""
    p.write_text(
        f"Error: {err}\nStatus: {r.status_code}\nFinal URL: {r.url}\nRedirects: {hist or 'none'}\n"
        f"Body length: {len(body)} chars\n\n--- response headers ---\n{hdrs}\n\n"
        f"--- first 4000 chars of body (repr) ---\n{body[:4000]!r}\n", encoding="utf-8")
    return p


def _request(session: requests.Session, url: str, name: str, start: dt.date,
             end: dt.date, style: str) -> list[dict]:
    """One POST. Raises NetworkError / BlockedError / BadResponseError."""
    try:
        r = session.post(url, headers=HEADERS, data=_payload(name, start, end, style),
                         timeout=TIMEOUT, allow_redirects=True)
    except requests.ConnectionError as e:
        raise NetworkError(f"cannot reach niftyindices.com ({type(e).__name__})") from e
    except requests.Timeout as e:
        raise BadResponseError("request timed out") from e
    except requests.RequestException as e:
        raise BadResponseError(f"{type(e).__name__}: {e}") from e
    try:
        if r.history and any(h.status_code in (301, 302, 303, 307, 308) for h in r.history):
            raise BlockedError(f"request was redirected to {r.url} (endpoint moved?)")
        if r.status_code != 200:
            raise BadResponseError(f"HTTP {r.status_code}")
        return _parse_body(r.text)
    except BadResponseError as e:
        _save_debug(f"{slug(name)}_{start:%Y%m%d}_{'new' if '/BackPage/' in url else 'old'}", r, str(e))
        raise


# --------------------------------------------------------------------------- #
# API check (run once per session): which endpoint / payload style works?
# --------------------------------------------------------------------------- #
class Api:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or _session()
        self.url: str | None = None
        self.style: str | None = None
        self.report: list[str] = []

    def check(self, probe_name: str = "NIFTY 50") -> bool:
        """Try each endpoint x payload style on a tiny recent range."""
        end = dt.date.today()
        start = end - dt.timedelta(days=15)
        net_errors = 0
        for url in ENDPOINTS:
            for style in ("single", "json"):
                label = f"{url.replace(BASE, '')}  [{style}-quoted payload]"
                try:
                    rows = _request(self.session, url, probe_name, start, end, style)
                    if rows:
                        self.url, self.style = url, style
                        self.report.append(f"OK    {label}: {len(rows)} rows, latest "
                                           f"{rows[0].get('Date')} = {rows[0].get('TotalReturnsIndex')}")
                        return True
                    self.report.append(f"EMPTY {label}: answered, but no rows")
                except NetworkError as e:
                    net_errors += 1
                    self.report.append(f"FAIL  {label}: {e}")
                    if net_errors >= 2:
                        return False
                except BadResponseError as e:
                    self.report.append(f"FAIL  {label}: {e}")
                time.sleep(PAUSE)
        return False

    def network_down(self) -> bool:
        return any("cannot reach" in r for r in self.report) and self.url is None

    # ----------------------------------------------------------------------- #
    def _get(self, name: str, start: dt.date, end: dt.date, retries: int = 3) -> list[dict]:
        last: Exception | None = None
        for attempt in range(retries):
            try:
                return _request(self.session, self.url, name, start, end, self.style)
            except (NetworkError, BlockedError):
                raise
            except BadResponseError as e:
                last = e
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
        raise BadResponseError(f"{_fmt(start)}..{_fmt(end)}: {last}")

    def resolve_name(self, name: str) -> str:
        """Return the spelling the server accepts (checked on the last 15 days)."""
        end = dt.date.today()
        start = end - dt.timedelta(days=15)
        cands = list(dict.fromkeys(NAME_ALTERNATIVES.get(name.upper(), []) + [name, name.upper()]))
        for c in cands:
            if self._get(c, start, end):
                return c
            time.sleep(PAUSE)
        raise BadResponseError(
            f"no rows for '{name}' (tried: {', '.join(cands)}). The name must match the "
            "niftyindices.com dropdown spelling exactly.")

    def download(self, name: str, since: dt.date | None = None) -> pd.Series:
        """Full history (year by year), or only the days after `since`."""
        api_name = self.resolve_name(name)
        today = dt.date.today()
        if since is not None:
            rows = self._get(api_name, since, today)
            return _rows_to_series(rows) if rows else pd.Series(dtype=float, name="tri")
        frames, started = [], False
        for year in range(EARLIEST_YEAR, today.year + 1):
            a = dt.date(year, 1, 1)
            b = min(dt.date(year, 12, 31), today)
            rows = self._get(api_name, a, b)
            if rows:
                started = True
                frames.append(_rows_to_series(rows))
            elif started and year < today.year:
                raise BadResponseError(f"year {year} came back empty in the middle of the "
                                       "history; refusing to build a series with a gap")
            print(".", end="", flush=True)
            PROGRESS["printed"] = True
            time.sleep(PAUSE)
        if not frames:
            raise BadResponseError(f"no historical rows returned for '{name}'")
        return _clean(pd.concat(frames))


def _rows_to_series(rows: list[dict]) -> pd.Series:
    df = pd.DataFrame(rows)
    keys = {c: re.sub(r"[^a-z]", "", str(c).lower()) for c in df.columns}
    date_col = next((c for c, k in keys.items() if "date" in k), None)
    val_col = next((c for c, k in keys.items()
                    if "totalreturn" in k and "net" not in k), None)
    if date_col is None or val_col is None:
        raise BadResponseError(f"rows lack Date/TotalReturnsIndex fields: {list(df.columns)}")
    dates = df[date_col].map(_parse_date)
    vals = pd.to_numeric(df[val_col].astype(str).str.replace(",", ""), errors="coerce")
    return _clean(pd.Series(vals.values, index=pd.DatetimeIndex(dates), name="tri"))


_MONTH_NUM = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}


def _parse_date(raw) -> pd.Timestamp:
    """'23 Oct 2026' / '23-Oct-2026' / '2026-10-23' -> Timestamp (locale-independent)."""
    t = str(raw).strip()
    m = re.match(r"^(\d{1,2})[\s\-/]([A-Za-z]{3})[A-Za-z]*[\s\-/](\d{2,4})$", t)
    if m:
        d, mon, y = int(m.group(1)), _MONTH_NUM.get(m.group(2).lower()), int(m.group(3))
        if mon:
            y = y + 2000 if y < 100 else y
            try:
                return pd.Timestamp(year=y, month=mon, day=d)
            except ValueError:
                return pd.NaT
    try:
        return pd.Timestamp(t)
    except (ValueError, TypeError):
        return pd.NaT


def gap_report(s: pd.Series, max_days: int = 10) -> list[str]:
    """Calendar gaps longer than max_days between consecutive rows (data-quality check)."""
    d = s.index.to_series().diff().dt.days
    bad = d[d > max_days]
    return [f"{(i - pd.Timedelta(days=int(g))).date()} → {i.date()} ({int(g)} days)"
            for i, g in bad.items()]


# --------------------------------------------------------------------------- #
# CSV loading (cache + manual downloads)
# --------------------------------------------------------------------------- #
def _clean(s: pd.Series) -> pd.Series:
    s = s[~s.index.isna()].dropna()
    s = s[s > 0]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.name = "tri"
    return s


def read_any_csv(path: Path) -> pd.Series:
    """Read a TRI CSV in our cache format or a niftyindices.com manual export."""
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    cols = {c: re.sub(r"[^a-z]", "", str(c).lower()) for c in df.columns}
    date_col = next((c for c, k in cols.items() if "date" in k), None)
    prefs = ["totalreturnsindex", "totalreturnindex", "totalreturn", "tri", "close"]
    val_col = None
    for p in prefs:
        val_col = next((c for c, k in cols.items() if p in k and "net" not in k), None)
        if val_col:
            break
    if date_col is None or val_col is None:
        raise ValueError(f"{path.name}: could not find a date column and a TRI column "
                         f"(columns seen: {list(df.columns)})")
    raw = df[date_col].astype(str).str.strip()
    dates = None
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%y"):
        parsed = pd.to_datetime(raw, format=fmt, errors="coerce")
        if parsed.notna().mean() > 0.95:
            dates = parsed
            break
    if dates is None:
        dates = pd.to_datetime(raw, dayfirst=True, errors="coerce", format="mixed")
    vals = pd.to_numeric(df[val_col].astype(str).str.replace(",", ""), errors="coerce")
    return _clean(pd.Series(vals.values, index=dates))


def save_cache(name: str, s: pd.Series) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / f"{slug(name)}.csv"
    s.rename_axis("date").to_frame("tri").to_csv(p)
    return p


def _manual_file_for(name: str) -> Path | None:
    if not MANUAL_DIR.exists():
        return None
    target = slug(name)
    for p in sorted(MANUAL_DIR.iterdir()):
        if p.suffix.lower() in {".csv", ".xlsx", ".xls"} and slug(p.stem) == target:
            return p
    return None


def manual_only_files(known: list[str]) -> dict[str, Path]:
    """CSV files in data/manual that don't match any requested index name."""
    out = {}
    if not MANUAL_DIR.exists():
        return out
    known_slugs = {slug(k) for k in known}
    for p in sorted(MANUAL_DIR.iterdir()):
        if p.suffix.lower() in {".csv", ".xlsx", ".xls"} and slug(p.stem) not in known_slugs:
            out[p.stem.replace("_", " ").upper()] = p
    return out


def load_index(name: str, api: Api | None, refresh: bool = False,
               offline: bool = False) -> tuple[pd.Series | None, str]:
    """Return (series, source_description)."""
    manual = _manual_file_for(name)
    if manual:
        return read_any_csv(manual), f"manual file {manual.name}"

    cache = CACHE_DIR / f"{slug(name)}.csv"
    cached = read_any_csv(cache) if cache.exists() and not refresh else None

    if offline or api is None or api.url is None:
        if cached is not None:
            return cached, f"cache (last date {cached.index[-1].date()})"
        return None, "no cache or manual file, and the API is not usable this run"

    try:
        if cached is not None:
            age = (pd.Timestamp.today().normalize() - cached.index[-1]).days
            if age <= 1:
                return cached, f"cache (up to date, {cached.index[-1].date()})"
            since = (cached.index[-1] - pd.Timedelta(days=10)).date()
            new = api.download(name, since=since)
            s = _clean(pd.concat([cached, new])) if len(new) else cached
            save_cache(name, s)
            return s, f"cache + {max(0, len(s) - len(cached))} new days from niftyindices.com"
        s = api.download(name)
        save_cache(name, s)
        return s, "niftyindices.com (downloaded now)"
    except (NetworkError, BlockedError, BadResponseError) as e:
        tag = "NETWORK" if isinstance(e, NetworkError) else (
            "BLOCKED" if isinstance(e, BlockedError) else "FAILED")
        if cached is not None:
            return cached, f"cache only; update failed: {e}"
        return None, f"{tag}: {e}"


# --------------------------------------------------------------------------- #
# Synthetic data for an offline test run
# --------------------------------------------------------------------------- #
def synthetic_tri(name: str, start: str, mu: float, vol: float, seed: int) -> pd.Series:
    """Random-walk TRI with fat tails and volatility regimes. NOT real market data."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, dt.date.today())
    n = len(idx)
    regime = np.where(np.sin(np.arange(n) / 700.0 + seed) > 0.6, 1.8, 1.0)
    shocks = rng.standard_t(df=4, size=n) / np.sqrt(2.0)
    daily = (mu - 0.5 * vol ** 2) / 252 + vol * regime / np.sqrt(252) * shocks * 0.8
    vals = 1000 * np.exp(np.cumsum(daily))
    return pd.Series(vals, index=idx, name="tri")


DEMO_SPECS = {
    "NIFTY 50": ("1999-06-30", 0.13, 0.21, 1),
    "NIFTY 500": ("1999-01-01", 0.135, 0.22, 2),
    "NIFTY NEXT 50": ("2002-11-08", 0.15, 0.25, 3),
    "NIFTY MIDCAP 150": ("2005-04-01", 0.16, 0.24, 4),
    "NIFTY SMALLCAP 250": ("2005-04-01", 0.15, 0.28, 5),
}
