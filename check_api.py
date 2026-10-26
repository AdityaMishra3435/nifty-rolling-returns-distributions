#!/usr/bin/env python3
"""
Checks, on YOUR machine, which niftyindices.com API calls work and what they return.
Takes under a minute and downloads only a few kilobytes.

    python check_api.py            (or: .venv/bin/python check_api.py after a launcher run)

It tests:
  1. Can the site be reached at all?
  2. Which endpoint + request format returns TRI data (current and legacy are both tried)
  3. Whether each default index name is accepted
  4. A one-year historical request (how the main script downloads history)
  5. A single full-history request (informational: tells us if 27 years in one call works)

Output is also saved to data/debug/check_api.txt so you can share it.
"""
import datetime as dt
import platform
import sys
import time

import requests

import fetch

DEFAULT_INDICES = ["NIFTY 50", "NIFTY 500", "NIFTY NEXT 50", "NIFTY MIDCAP 150",
                   "NIFTY SMALLCAP 250"]
out = []


def say(m=""):
    print(m, flush=True)
    out.append(m)


def main() -> int:
    utc = dt.datetime.now(dt.timezone.utc)
    ist = utc.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    say(f"niftyindices.com API check · {utc:%d %b %Y %H:%M} UTC ({ist:%d %b %Y %H:%M} IST)")
    say(f"Python {sys.version.split()[0]} · requests {requests.__version__} · {platform.system()}")

    say("\n1) Reaching the site")
    try:
        r = requests.get(fetch.BASE, headers={"User-Agent": fetch.USER_AGENT}, timeout=15)
        say(f"   OK: homepage answered HTTP {r.status_code}")
    except requests.RequestException as e:
        say(f"   FAIL: {type(e).__name__}: {e}")
        say("   → No connection to niftyindices.com from this network (firewall / VPN / offline).")
        return finish(False)

    say("\n2) Endpoint + request format (NIFTY 50, last 15 days)")
    api = fetch.Api()
    ok = api.check()
    for line in api.report:
        say("   " + line)
    if not ok:
        say("   → No working combination. See data/debug/ for the raw responses.")
        return finish(False)
    say(f"   → Using {api.url.replace(fetch.BASE, '')} with {api.style}-quoted payload")

    say("\n3) Index names (last 15 days each)")
    all_names_ok = True
    for name in DEFAULT_INDICES:
        try:
            used = api.resolve_name(name)
            rows = api._get(used, dt.date.today() - dt.timedelta(days=15), dt.date.today())
            say(f"   OK    {name:<20} accepted as '{used}', latest {rows[0].get('Date')}"
                f" TRI {rows[0].get('TotalReturnsIndex')}")
        except Exception as e:  # noqa: BLE001
            all_names_ok = False
            say(f"   FAIL  {name:<20} {e}")
        time.sleep(fetch.PAUSE)

    say("\n4) One historical year (NIFTY 50, calendar year 2000)")
    year_ok = False
    try:
        rows = api._get("NIFTY 50", dt.date(2000, 1, 1), dt.date(2000, 12, 31))
        s = fetch._rows_to_series(rows)
        year_ok = len(s) > 200
        say(f"   {'OK' if year_ok else 'SHORT'}: {len(s)} trading days, "
            f"{s.index[0].date()} → {s.index[-1].date()}, TRI {s.iloc[0]:.2f} → {s.iloc[-1]:.2f}")
    except Exception as e:  # noqa: BLE001
        say(f"   FAIL: {e}")

    say("\n5) Full history in ONE request (informational only)")
    try:
        t0 = time.time()
        rows = api._get("NIFTY 50", dt.date(1995, 1, 1), dt.date.today(), retries=1)
        s = fetch._rows_to_series(rows)
        say(f"   {len(s):,} rows, {s.index[0].date()} → {s.index[-1].date()} in {time.time()-t0:.1f}s"
            " (the main script uses yearly requests regardless)")
    except Exception as e:  # noqa: BLE001
        say(f"   did not work ({e}). Fine: the main script uses yearly requests.")

    return finish(ok and all_names_ok and year_ok)


def finish(good: bool) -> int:
    say("\nVERDICT: " + ("everything the main script needs works. Run it."
                         if good else "something failed (details above)."))
    p = fetch.DEBUG_DIR / "check_api.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out), encoding="utf-8")
    print(f"(saved to {p})")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
