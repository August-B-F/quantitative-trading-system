"""Study 9 analysis — measured execution costs from SIP minute bars.

Inputs: data/{SYM}_1min_windows.parquet (fetch_bars.py), optional
data/nbbo_samples.parquet, and data/clean/prices/*.parquet (official raw
open/close + adj_close).

Outputs: results printed + measurements.csv in this folder.
Everything mirrors HYPOTHESIS.md definitions:
  (a) open slip: VWAP(09:30..09:34) vs official open; per-minute decay 0..9
  (b) spread proxy: mean 1-min (h-l)/c, window A 09:30..09:34 vs
      window B 15:45..15:54; NBBO supplement by instant
  (c) close drift: official close vs 15:44 bar close; last-10 VWAP vs close;
      blend_126_252 top-3 rank-flip + gate-flip on 15:44 proxy closes
"""
import os
from datetime import date

import numpy as np
import pandas as pd

ROOT = r"c:\Users\august\Documents\GitHub\quantitative-trading-system"
HERE = os.path.join(ROOT, "research", "droplets", "study9_intraday")
DATA = os.path.join(HERE, "data")
SYMBOLS = ["SOXX", "QQQ", "XLE", "GLD", "SHY", "SPY"]
UNIVERSE = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
INTRADAY_HAVE = [s for s in UNIVERSE if s in SYMBOLS]


def load_windows(sym):
    df = pd.read_parquet(os.path.join(DATA, f"{sym}_1min_windows.parquet"))
    df["et_date"] = pd.to_datetime(df["et_date"])
    return df


def load_daily(sym):
    df = pd.read_parquet(os.path.join(ROOT, f"data/clean/prices/{sym}.parquet"))
    return df


def stats(x):
    x = pd.Series(x).dropna()
    return dict(n=len(x), mean=x.mean(), median=x.median(),
                mean_abs=x.abs().mean(), median_abs=x.abs().median(),
                p90_abs=x.abs().quantile(0.9))


def vwap(g):
    v = g["v"].sum()
    return np.nan if v == 0 else (g["vw"] * g["v"]).sum() / v


def open_analysis(win, daily, sym):
    """(a) VWAP of minutes 09:30..09:34 vs official open, + per-minute."""
    am = win[(win.et_hm >= "09:30") & (win.et_hm <= "09:34")]
    rows = []
    for d, g in am.groupby("et_date"):
        if d not in daily.index:
            continue
        o = daily.loc[d, "open"]
        vw5 = vwap(g)
        if np.isfinite(vw5) and o > 0:
            rows.append((d, 1e4 * (vw5 / o - 1)))
    slip = pd.DataFrame(rows, columns=["date", "slip_bps"]).set_index("date")

    per_min = {}
    am10 = win[(win.et_hm >= "09:30") & (win.et_hm <= "09:39")].copy()
    am10 = am10.merge(daily["open"].rename("off_open"), left_on="et_date",
                      right_index=True)
    am10["min_slip"] = 1e4 * (am10["vw"] / am10["off_open"] - 1)
    for hm, g in am10.groupby("et_hm"):
        per_min[hm] = dict(mean=g.min_slip.mean(),
                           mean_abs=g.min_slip.abs().mean(),
                           median_abs=g.min_slip.abs().median())
    return slip["slip_bps"], per_min


def spread_analysis(win):
    """(b) mean 1-min (h-l)/c per window per day; per-minute am profile."""
    win = win.copy()
    win["hl_bps"] = 1e4 * (win["h"] - win["l"]) / win["c"]
    a = win[(win.et_hm >= "09:30") & (win.et_hm <= "09:34")]
    b = win[(win.et_hm >= "15:45") & (win.et_hm <= "15:54")]
    day_a = a.groupby("et_date").hl_bps.mean()
    day_b = b.groupby("et_date").hl_bps.mean()
    both = pd.concat([day_a.rename("am"), day_b.rename("pm")], axis=1).dropna()
    per_min = win[(win.et_hm >= "09:30") & (win.et_hm <= "09:39")] \
        .groupby("et_hm").hl_bps.median()
    return both, per_min


def close_analysis(win, daily):
    """(c) close drift 15:44 -> official close; last-10 VWAP vs close."""
    dec = win[win.et_hm == "15:44"].set_index("et_date")["c"]
    last10 = win[(win.et_hm >= "15:50") & (win.et_hm <= "15:59")]
    l10 = last10.groupby("et_date").apply(vwap, include_groups=False)
    cl = daily["close"]
    drift = (1e4 * (cl / dec - 1)).dropna()
    l10gap = (1e4 * (l10 / cl - 1)).dropna()
    return drift, l10gap


def rank_flip(proxy_closes):
    """(c) blend_126_252 top-3 + gate flips: official close vs 15:44 proxy.

    proxy_closes: {sym: Series et_date -> raw 15:44 close} for INTRADAY_HAVE.
    XLK/VGT/IGV (and SPY gate when missing) fall back to official close, so
    flips are slightly UNDERcounted (documented limitation).
    """
    adj = {}
    raw = {}
    for t in UNIVERSE + ["SPY"]:
        d = load_daily(t)
        adj[t] = d["adj_close"].dropna()
        raw[t] = d["close"].dropna()
    adj = pd.DataFrame(adj).dropna()
    raw_df = pd.DataFrame(raw).reindex(adj.index)

    # proxy adjusted close: adj * (proxy_raw / official_raw)
    prox = adj.copy()
    for t, s in proxy_closes.items():
        s = s.reindex(adj.index)
        ratio = (s / raw_df[t]).fillna(1.0)
        prox[t] = adj[t] * ratio

    sample_days = None
    for t, s in proxy_closes.items():
        idx = s.dropna().index
        sample_days = idx if sample_days is None else sample_days.union(idx)
    days = adj.index.intersection(sample_days)
    days = days[days >= adj.index[252]]

    def top3_and_gate(px, d):
        i = px.index.get_loc(d)
        scores = {}
        for t in UNIVERSE:
            r126 = px[t].iloc[i] / px[t].iloc[i - 126] - 1
            r252 = px[t].iloc[i] / px[t].iloc[i - 252] - 1
            scores[t] = (r126, r252)
        df = pd.DataFrame(scores, index=["r126", "r252"]).T
        blend = df.rank(axis=0, method="average", ascending=True).mean(axis=1)
        top3 = frozenset(blend.nlargest(3).index)
        sma = px["SPY"].iloc[i - 199:i + 1].mean()
        gate_off = px["SPY"].iloc[i] <= sma
        return top3, gate_off

    flips, gate_flips, n = 0, 0, 0
    flip_days = []
    for d in days:
        t_off, g_off = top3_and_gate(adj, d)
        t_px, g_px = top3_and_gate(prox, d)
        n += 1
        if t_off != t_px:
            flips += 1
            flip_days.append(d)
        if g_off != g_px:
            gate_flips += 1

    # decision days: month-end trading day +0/+5/+10/+15
    tdays = adj.index
    month_ends = tdays.to_series().groupby(
        [tdays.year, tdays.month]).max()
    dec_days = set()
    pos = {d: i for i, d in enumerate(tdays)}
    for me in month_ends:
        for off in (0, 5, 10, 15):
            i = pos[me] + off
            if i < len(tdays):
                dec_days.add(tdays[i])
    dd = [d for d in days if d in dec_days]
    dflips = sum(1 for d in flip_days if d in dec_days)

    return dict(all_days=n, all_flips=flips, all_flip_rate=flips / n,
                gate_flips=gate_flips, gate_flip_rate=gate_flips / n,
                dec_days=len(dd), dec_flips=dflips,
                dec_flip_rate=dflips / len(dd) if dd else np.nan,
                flip_days_sample=[str(d.date()) for d in flip_days[:20]])


def main():
    out_rows = []
    proxy_closes = {}
    print("=" * 78)
    for sym in SYMBOLS:
        win = load_windows(sym)
        daily = load_daily(sym)
        slip, per_min = open_analysis(win, daily, sym)
        spread_days, spread_per_min = spread_analysis(win)
        drift, l10gap = close_analysis(win, daily)
        proxy_closes[sym] = win[win.et_hm == "15:44"].set_index("et_date")["c"]

        s_slip, s_drift, s_l10 = stats(slip), stats(drift), stats(l10gap)
        am_med, pm_med = spread_days.am.median(), spread_days.pm.median()
        pm_cheaper = (spread_days.pm < spread_days.am).mean()
        print(f"\n--- {sym}  (days: {s_slip['n']} open, {s_drift['n']} close)")
        print(f"(a) open slip vwap(0-4m) vs official open: "
              f"mean {s_slip['mean']:+.2f} | mean|.| {s_slip['mean_abs']:.2f}"
              f" | med|.| {s_slip['median_abs']:.2f} | p90|.| "
              f"{s_slip['p90_abs']:.2f} bps")
        pm_line = {k: f"{v['mean']:+.1f}/{v['median_abs']:.1f}"
                   for k, v in sorted(per_min.items())}
        print(f"    per-min mean-signed/med-abs vs open: {pm_line}")
        print(f"(b) spread proxy (h-l)/c med: open5m {am_med:.2f} vs "
              f"pm10m {pm_med:.2f} bps | pm cheaper on {pm_cheaper:.0%} of "
              f"days | am per-min med {dict(spread_per_min.round(1))}")
        print(f"(c) close drift 15:44->close: mean {s_drift['mean']:+.2f} | "
              f"med|.| {s_drift['median_abs']:.2f} | p90|.| "
              f"{s_drift['p90_abs']:.2f} bps ; last10 VWAP vs close med|.| "
              f"{s_l10['median_abs']:.2f} bps")
        for k, v in [("open_slip", s_slip), ("close_drift", s_drift),
                     ("last10_gap", s_l10)]:
            out_rows.append(dict(symbol=sym, metric=k, **v))
        out_rows.append(dict(symbol=sym, metric="spread_am_vs_pm",
                             n=len(spread_days), mean=spread_days.am.mean(),
                             median=am_med, mean_abs=spread_days.pm.mean(),
                             median_abs=pm_med, p90_abs=pm_cheaper))

    # NBBO supplement
    nbbo_path = os.path.join(DATA, "nbbo_samples.parquet")
    if os.path.exists(nbbo_path):
        q = pd.read_parquet(nbbo_path)
        q["spread_bps"] = 1e4 * (q.ask - q.bid) / ((q.ask + q.bid) / 2)
        q = q[(q.spread_bps > 0) & (q.spread_bps < 200)]  # drop crossed/junk
        piv = q.pivot_table(index="symbol", columns="et_instant",
                            values="spread_bps", aggfunc="median").round(2)
        print("\n=== NBBO median spread (bps) by sampled instant ===")
        print(piv)
        piv.to_csv(os.path.join(HERE, "nbbo_spread_summary.csv"))

    print("\n=== rank-flip test (blend_126_252, 15:44 proxy closes) ===")
    rf = rank_flip(proxy_closes)
    for k, v in rf.items():
        print(f"  {k}: {v}")

    pd.DataFrame(out_rows).to_csv(
        os.path.join(HERE, "measurements.csv"), index=False)
    print("\nsaved measurements.csv")


if __name__ == "__main__":
    main()
