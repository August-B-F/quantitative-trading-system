"""Study 9 fetcher — historical minute bars (and sampled NBBO quotes) from
Alpaca market data. GET-only; market-data endpoints only.

Probe result 2026-07-02 (probe_api.py / probe_results.json): this account's
keys serve the **SIP (consolidated) feed** historically — minute bars back to
2016-01, NBBO quotes back to 2016, recency limited only by the 15-minute
delay. IEX minute bars start 2020-07-27 and are ~2-3% of volume; we therefore
use feed=sip as primary (fall back to iex automatically if a key loses SIP).

Keeps only the windows the study needs (America/New_York):
  09:30-09:39  open-execution + morning spread proxy
  15:40-15:59  close drift, 15:44 decision bar, last-10-min VWAP, pm spread

Output (per symbol): data/{SYM}_1min_windows.parquet
  columns: t (UTC), et_date, et_hm, o,h,l,c,v,n,vw
Rerunnable: skips existing files unless --force.

Usage:
  py -3 research/droplets/study9_intraday/fetch_bars.py
  py -3 fetch_bars.py --symbols SPY,QQQ --start 2016-01-01 --force
  py -3 fetch_bars.py --quotes          # sampled NBBO quotes supplement
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = r"c:\Users\august\Documents\GitHub\quantitative-trading-system"
HERE = os.path.join(ROOT, "research", "droplets", "study9_intraday")
DATA = os.path.join(HERE, "data")
BASE = "https://data.alpaca.markets"
SYMBOLS = ["SOXX", "QQQ", "XLE", "GLD", "SHY", "SPY"]
ET = ZoneInfo("America/New_York")
WINDOWS = [("09:30", "09:39"), ("15:40", "15:59")]  # inclusive HH:MM


def load_keys():
    env = {}
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env["ALPACA_S1_KEY"], env["ALPACA_S1_SECRET"]


KEY, SECRET = load_keys()


def get(path, **params):
    """GET with rate-limit respect (200 req/min on this plan)."""
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                remaining = int(r.headers.get("X-Ratelimit-Remaining", 100))
                reset = int(r.headers.get("X-Ratelimit-Reset", 0))
                if remaining < 3:
                    time.sleep(max(0.0, reset - time.time()) + 0.5)
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {path}")


def in_window(hm):
    return any(a <= hm <= b for a, b in WINDOWS)


def fetch_symbol_bars(sym, start, end, feed):
    rows, token, pages = [], None, 0
    while True:
        # adjustment=split matches data/clean/prices parquet convention
        # (split-adjusted, dividend-unadjusted) — verified 2026-07-02 for all
        # six symbols; raw would be 3x off for SOXX and 2x for XLE pre-2024.
        params = dict(timeframe="1Min", start=start + "T00:00:00Z",
                      end=end + "T23:59:59Z", limit=10000, feed=feed,
                      adjustment="split")
        if token:
            params["page_token"] = token
        js = get(f"/v2/stocks/{sym}/bars", **params)
        for b in js.get("bars") or []:
            t = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
            et = t.astimezone(ET)
            hm = et.strftime("%H:%M")
            if in_window(hm):
                rows.append((b["t"], et.date().isoformat(), hm, b["o"],
                             b["h"], b["l"], b["c"], b["v"], b["n"],
                             b["vw"]))
        token = js.get("next_page_token")
        pages += 1
        if pages % 20 == 0:
            print(f"  {sym}: {pages} pages, {len(rows)} window-rows, "
                  f"last={js['bars'][-1]['t'] if js.get('bars') else '-'}",
                  flush=True)
        if not token:
            break
    df = pd.DataFrame(rows, columns=["t", "et_date", "et_hm", "o", "h", "l",
                                     "c", "v", "n", "vw"])
    return df, pages


def fetch_bars_main(symbols, start, end, feed, force):
    os.makedirs(DATA, exist_ok=True)
    for sym in symbols:
        out = os.path.join(DATA, f"{sym}_1min_windows.parquet")
        if os.path.exists(out) and not force:
            print(f"{sym}: exists, skip (--force to refetch)")
            continue
        t0 = time.time()
        df, pages = fetch_symbol_bars(sym, start, end, feed)
        df.to_parquet(out)
        print(f"{sym}: {len(df)} rows, {pages} pages, "
              f"{df.et_date.min()}..{df.et_date.max()}, "
              f"{time.time()-t0:.0f}s -> {out}", flush=True)


# ---------------- quotes supplement (sampled NBBO spreads) ----------------

SAMPLE_INSTANTS_ET = ["09:30:15", "09:31:00", "09:33:00", "09:35:00",
                      "15:45:00", "15:50:00", "15:55:00"]


def fetch_quotes_main(symbols, days_back, feed):
    """Sample the NBBO at fixed instants on the 10th trading day of every
    OTHER month (from the SPY parquet calendar), one request per
    symbol/instant with limit=1 (the multi-symbol endpoint fills its limit
    with the alphabetically first symbol — measured 2026-07-02)."""
    spy = pd.read_parquet(os.path.join(ROOT, "data/clean/prices/SPY.parquet"))
    tdays = spy.index[spy.index >= "2016-01-01"]
    bymonth = {}
    for d in tdays:
        bymonth.setdefault((d.year, d.month), []).append(d)
    sample_days = [v[9] for v in bymonth.values() if len(v) > 9]
    sample_days = sample_days[-days_back:][::2]
    rows = []
    for d in sample_days:
        for inst in SAMPLE_INSTANTS_ET:
            et_dt = datetime.fromisoformat(f"{d.date()}T{inst}").replace(
                tzinfo=ET)
            start = et_dt.astimezone(ZoneInfo("UTC"))
            end = start + timedelta(seconds=30)
            for sym in symbols:
                js = get(f"/v2/stocks/{sym}/quotes",
                         start=start.isoformat().replace("+00:00", "Z"),
                         end=end.isoformat().replace("+00:00", "Z"),
                         limit=1, feed=feed)
                qs = js.get("quotes") or []
                if qs:
                    q = qs[0]
                    if q["bp"] > 0 and q["ap"] > 0:
                        rows.append((sym, d.date().isoformat(), inst,
                                     q["bp"], q["ap"], q["t"]))
        print(f"quotes {d.date()}: total rows {len(rows)}", flush=True)
    df = pd.DataFrame(rows, columns=["symbol", "et_date", "et_instant",
                                     "bid", "ask", "t"])
    out = os.path.join(DATA, "nbbo_samples.parquet")
    df.to_parquet(out)
    print(f"quotes: {len(df)} rows -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-07-01")
    ap.add_argument("--feed", default="sip")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quotes", action="store_true",
                    help="fetch sampled NBBO quotes instead of bars")
    ap.add_argument("--quote-months", type=int, default=126)
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if a.quotes:
        fetch_quotes_main(syms, a.quote_months, a.feed)
    else:
        fetch_bars_main(syms, a.start, a.end, a.feed, a.force)
