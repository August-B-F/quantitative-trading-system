"""Study 9 probe: what does the free Alpaca IEX feed actually serve?

GET-only, market data API only. Documents: history depth, fields,
pagination, rate-limit headers, quote availability, feed access.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = r"c:\Users\august\Documents\GitHub\quantitative-trading-system"


def load_env():
    env = {}
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
KEY, SECRET = ENV["ALPACA_S1_KEY"], ENV["ALPACA_S1_SECRET"]
BASE = "https://data.alpaca.markets"


def get(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            hdr = {k: v for k, v in r.headers.items()
                   if k.lower().startswith("x-ratelimit")}
            return r.status, hdr, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}, json.loads(e.read() or b"{}")


def main():
    out = {}

    # 1. earliest 1-min bar per symbol on IEX feed
    for sym in ["SPY", "SOXX", "SHY"]:
        st, hdr, js = get(f"/v2/stocks/{sym}/bars", timeframe="1Min",
                          start="2010-01-01T00:00:00Z", limit=5, feed="iex")
        bars = js.get("bars") or []
        out[f"earliest_1min_{sym}"] = {
            "status": st, "first_bars": bars[:3], "ratelimit": hdr}
        print(f"{sym} earliest 1Min (iex): status={st} "
              f"first={bars[0]['t'] if bars else None} fields="
              f"{sorted(bars[0].keys()) if bars else None} rl={hdr}")

    # 2. is SIP historical allowed on this key?
    st, _, js = get("/v2/stocks/SPY/bars", timeframe="1Min",
                    start="2024-01-03T14:30:00Z", end="2024-01-03T14:35:00Z",
                    limit=5, feed="sip")
    print(f"SIP historical bars: status={st} "
          f"resp={str(js)[:200]}")
    out["sip_bars"] = {"status": st, "resp_head": str(js)[:300]}

    # 3. historical quotes on IEX
    st, _, js = get("/v2/stocks/SPY/quotes",
                    start="2026-06-29T13:30:00Z", end="2026-06-29T13:31:00Z",
                    limit=5, feed="iex")
    q = (js.get("quotes") or [])[:2]
    print(f"IEX historical quotes: status={st} sample={q}")
    out["iex_quotes"] = {"status": st, "sample": q}

    # 3b. how far back do IEX quotes go?
    st, _, js = get("/v2/stocks/SPY/quotes",
                    start="2020-01-02T14:30:00Z", end="2020-01-02T14:31:00Z",
                    limit=3, feed="iex")
    print(f"IEX quotes 2020: status={st} sample={str(js)[:200]}")
    out["iex_quotes_2020"] = {"status": st, "resp_head": str(js)[:300]}

    # 4. latest quote endpoint
    st, _, js = get("/v2/stocks/SPY/quotes/latest", feed="iex")
    print(f"latest quote: status={st} resp={str(js)[:250]}")
    out["latest_quote"] = {"status": st, "resp": js}

    # 5. daily bars (do they match our parquet / include auction OHLC?)
    st, _, js = get("/v2/stocks/SPY/bars", timeframe="1Day",
                    start="2026-06-29T00:00:00Z", end="2026-07-01T00:00:00Z",
                    feed="iex", adjustment="raw")
    print(f"IEX 1Day bars: status={st} bars={js.get('bars')}")
    out["iex_daily"] = js.get("bars")

    # 6. pagination shape + page size cap
    st, hdr, js = get("/v2/stocks/SPY/bars", timeframe="1Min",
                      start="2026-06-01T00:00:00Z", limit=10000, feed="iex")
    print(f"page: status={st} n={len(js.get('bars') or [])} "
          f"npt={'yes' if js.get('next_page_token') else 'no'} rl={hdr}")
    out["page_probe"] = {"n": len(js.get("bars") or []),
                         "next_page_token": bool(js.get("next_page_token")),
                         "ratelimit": hdr}

    with open(os.path.join(ROOT, "research/droplets/study9_intraday/"
                                 "probe_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("saved probe_results.json")


if __name__ == "__main__":
    sys.exit(main())
