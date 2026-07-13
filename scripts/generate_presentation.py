"""Generate results/backtest_presentation.json — the single data file the
dashboard and PDF report consume.

Pulls the canonical M26_post_3d strategy from the stress harness cache,
plus a SPY benchmark series and an "original B3" (plain top1 63d momentum,
no regime classifier, no SMA gate, no inv-vol, no FOMC deferral) for
comparison.

Numbers must match results/FINAL_STRATEGY_VALIDATED.md exactly:
    CAGR 23.61%  Sharpe 1.50  MaxDD -12.94%
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "model"))

from stress_harness import (  # type: ignore
    load_cache, run_strategy_from_cache, stats, ETFS, LB_STABLE, K,
    W_TOP1, W_TOPK, SMA_GATE,
)

OUT_PATH = ROOT / "results" / "backtest_presentation.json"
REGIME_NAMES = ["HG_LI", "HG_HI", "LG_LI", "LG_HI_stag"]
REGIME_LABELS = ["Hi-Growth/Lo-Inf", "Hi-Growth/Hi-Inf", "Lo-Growth/Lo-Inf", "Lo-Growth/Hi-Inf (stag)"]


# Helpers
def _equity(r: np.ndarray) -> np.ndarray:
    r = np.nan_to_num(r, nan=0.0)
    return np.cumprod(1.0 + r)


def _drawdown(r: np.ndarray) -> np.ndarray:
    eq = _equity(r)
    peak = np.maximum.accumulate(eq)
    return eq / peak - 1.0


def _rolling_sharpe(r: pd.Series, win: int = 12) -> pd.Series:
    mu = r.rolling(win).mean()
    sd = r.rolling(win).std(ddof=1)
    return (mu / sd) * np.sqrt(12)


def _streaks(r: np.ndarray) -> tuple[int, int]:
    win = lose = cur_w = cur_l = 0
    for v in r:
        if np.isnan(v):
            cur_w = cur_l = 0
            continue
        if v > 0:
            cur_w += 1; cur_l = 0
            if cur_w > win: win = cur_w
        elif v < 0:
            cur_l += 1; cur_w = 0
            if cur_l > lose: lose = cur_l
        else:
            cur_w = cur_l = 0
    return win, lose


def _capture(strat: np.ndarray, bench: np.ndarray) -> tuple[float, float]:
    up = bench > 0; dn = bench < 0
    up_c = float(strat[up].mean() / bench[up].mean()) if up.any() and bench[up].mean() != 0 else float("nan")
    dn_c = float(strat[dn].mean() / bench[dn].mean()) if dn.any() and bench[dn].mean() != 0 else float("nan")
    return up_c, dn_c


def _sortino(r: np.ndarray) -> float:
    r = r[~np.isnan(r)]
    dn = r[r < 0]
    if len(dn) == 0:
        return float("nan")
    return float(r.mean() / dn.std(ddof=1) * np.sqrt(12))


def _key_stats(r: pd.Series) -> dict:
    a = r.values
    s = stats(a)
    win, lose = _streaks(a)
    yrly = (1 + r).groupby(r.index.year).prod() - 1
    return {
        "cagr": s["cagr"],
        "sharpe": s["sharpe"],
        "sortino": _sortino(a),
        "max_dd": s["max_dd"],
        "calmar": s["cagr"] / abs(s["max_dd"]) if s["max_dd"] != 0 else float("nan"),
        "best_month": float(np.nanmax(a)),
        "worst_month": float(np.nanmin(a)),
        "best_year": float(yrly.max()),
        "worst_year": float(yrly.min()),
        "n_neg_years": int((yrly < 0).sum()),
        "win_rate": float((a[~np.isnan(a)] > 0).mean()),
        "avg_month": float(np.nanmean(a)),
        "median_month": float(np.nanmedian(a)),
        "longest_win_streak": win,
        "longest_lose_streak": lose,
        "n_months": int((~np.isnan(a)).sum()),
    }


# Comparison series
def build_spy_monthly(cache: dict, month_last_pos: pd.Series) -> pd.Series:
    """SPY forward-21d return at each month-end rebalance position."""
    spy_fwd21 = cache["spy_ret_21d"]  # trailing 21d — convert to forward
    # The cache stores trailing; we need forward to align with strategy fwd_ret.
    # Shift: forward_t = trailing_{t+21}. Simpler: load returns_21d and shift.
    rdf = pd.read_parquet(ROOT / "data/features/price/returns_21d.parquet").reindex(cache["DATES"])
    spy_f = rdf["SPY"].shift(-21).values
    out = {}
    for d, i in month_last_pos.items():
        out[d] = float(spy_f[int(i)])
    return pd.Series(out).sort_index()


def build_original_b3(cache: dict, month_last_pos: pd.Series) -> pd.Series:
    """Plain 63d top-1 momentum, no SMA gate, no inv-vol, no regime, no M26."""
    M = cache["M_STABLE"]
    FWD = cache["FWD_ARR"]
    out = {}
    for d, i in month_last_pos.items():
        i = int(i)
        sf = np.where(np.isnan(M[i]), -np.inf, M[i])
        top1 = int(np.argmax(sf))
        out[d] = float(FWD[i, top1])
    return pd.Series(out).sort_index()


# Component attribution (cumulative-build variants)
def build_attribution(cache: dict, month_last_pos: pd.Series) -> dict:
    """Compute per-year contribution by progressively adding components.

    Variants (cumulative):
        v0 base       = plain 63d top1, no gate, no inv-vol, no regime, no M26
        v1 +regime    = add regime-conditional lookback (63 stable / 21 trans)
        v2 +inv_vol   = add 50/50 top1 + inv-vol top3 sleeve
        v3 +sma_gate  = add SMA200 SHY gate on top1
        v4 +m26       = add FOMC post-3d deferral  (== full strategy)
    """
    DATES = cache["DATES"]; NDAYS = cache["NDAYS"]
    FWD = cache["FWD_ARR"]; ATR = cache["ATR"]
    M_S = cache["M_STABLE"]; M_T = cache["M_TRANS"]
    pred_reg = cache["pred_reg"]; cur_reg = cache["current_reg"]
    spy_dist = cache["spy_dist"]; shy = cache["shy_ret"]
    fomc_idx = cache["fomc_day_idx"]
    fomc_post = np.zeros(NDAYS, bool)
    for fi in fomc_idx:
        hi = min(NDAYS - 1, fi + 2)
        fomc_post[fi:hi + 1] = True

    use_trans = (pred_reg != -1) & (pred_reg != cur_reg)
    MOM_REG = np.where(use_trans[:, None], M_T, M_S)

    def run(use_regime, use_invvol, use_gate, use_m26):
        out = {}
        for d, i in month_last_pos.items():
            i = int(i)
            iu = min(i + 3, NDAYS - 1) if (use_m26 and fomc_post[i]) else i
            mom = MOM_REG[iu] if use_regime else M_S[iu]
            sf = np.where(np.isnan(mom), -np.inf, mom)
            order = np.argsort(-sf)
            top1 = int(order[0]); tk = order[:K]
            r1 = FWD[iu, top1]
            if use_gate and spy_dist[iu] <= SMA_GATE:
                r1 = shy[iu]
            if use_invvol:
                sel_atr = ATR[iu, tk]
                inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
                if np.isnan(inv).all():
                    rk = np.nanmean(FWD[iu, tk])
                else:
                    w = inv / np.nansum(inv)
                    rk = np.nansum(FWD[iu, tk] * w)
                ret = W_TOP1 * r1 + W_TOPK * rk
            else:
                ret = float(r1)
            out[d] = float(ret)
        return pd.Series(out).sort_index()

    v0 = run(False, False, False, False)
    v1 = run(True, False, False, False)
    v2 = run(True, True, False, False)
    v3 = run(True, True, True, False)
    v4 = run(True, True, True, True)

    def yr_ret(s):
        return ((1 + s).groupby(s.index.year).prod() - 1)

    y0, y1, y2, y3, y4 = [yr_ret(s) for s in (v0, v1, v2, v3, v4)]
    years = sorted(set(y4.index))
    rows = []
    for yr in years:
        rows.append({
            "year": int(yr),
            "base":     float(y0.get(yr, np.nan)),
            "regime":   float(y1.get(yr, np.nan) - y0.get(yr, np.nan)),
            "inv_vol":  float(y2.get(yr, np.nan) - y1.get(yr, np.nan)),
            "sma_gate": float(y3.get(yr, np.nan) - y2.get(yr, np.nan)),
            "m26":      float(y4.get(yr, np.nan) - y3.get(yr, np.nan)),
            "total":    float(y4.get(yr, np.nan)),
        })
    return {"per_year": rows}


# Regime breakdowns
def regime_breakdown(cache, strat: pd.Series, picks: pd.DataFrame) -> dict:
    DATES = cache["DATES"]
    vix = cache["vix"]; cur_reg = cache["current_reg"]
    # Build a series of vix and regime at each rebal-date
    vix_at = []; reg_at = []
    for d, used_i in zip(picks["rebal_date"], picks["used_i"]):
        vix_at.append(float(vix[int(used_i)]))
        reg_at.append(int(cur_reg[int(used_i)]))
    vix_at = np.array(vix_at); reg_at = np.array(reg_at)
    r = strat.values

    def bucket_stats(mask):
        x = r[mask]
        x = x[~np.isnan(x)]
        if len(x) == 0:
            return {"n": 0, "mean": float("nan"), "ann": float("nan")}
        return {"n": int(len(x)), "mean": float(x.mean()),
                "ann": float((1 + x.mean()) ** 12 - 1)}

    vix_buckets = {
        "calm (<15)":     bucket_stats(vix_at < 15),
        "normal (15-25)": bucket_stats((vix_at >= 15) & (vix_at < 25)),
        "stressed (>=25)":bucket_stats(vix_at >= 25),
    }
    reg_buckets = {REGIME_LABELS[k]: bucket_stats(reg_at == k) for k in range(4)}
    return {"vix": vix_buckets, "regime": reg_buckets}


# Main
def main():
    print("[gen] Loading cache...")
    cache = load_cache()

    print("[gen] Running canonical strategy...")
    res = run_strategy_from_cache(cache, return_picks=True)
    strat = res["monthly"]
    picks = res["picks"]
    st = res["stats"]
    print(f"  CAGR {st['cagr']*100:.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:.2f}%")

    # Build a month_last positions Series with original (un-deferred) i
    month_last_pos = pd.Series(
        picks["orig_i"].values, index=pd.to_datetime(picks["rebal_date"].values)
    ).astype(int)
    # Align strat index to month_last_pos for cleanliness
    strat.index = pd.to_datetime(strat.index)

    print("[gen] Building SPY benchmark...")
    spy = build_spy_monthly(cache, month_last_pos)
    spy.index = pd.to_datetime(spy.index)

    print("[gen] Building original B3 comparison...")
    orig = build_original_b3(cache, month_last_pos)
    orig.index = pd.to_datetime(orig.index)

    # Restrict the start to 2010 for visualization (per request)
    cutoff = pd.Timestamp("2010-01-01")
    strat = strat[strat.index >= cutoff]
    spy = spy[spy.index >= cutoff]
    orig = orig[orig.index >= cutoff]
    picks = picks[pd.to_datetime(picks["rebal_date"]) >= cutoff].reset_index(drop=True)

    # NOTE: validation requires the FULL window — keep a copy
    full_strat = res["monthly"]
    full_strat.index = pd.to_datetime(full_strat.index)
    full_stats = stats(full_strat.values)

    # --- Equity curves ---
    def to_curve(s, name):
        eq = _equity(s.values) * 10000.0
        return [{"date": d.strftime("%Y-%m"), "value": float(v)} for d, v in zip(s.index, eq)]

    equity = {
        "strategy": to_curve(strat, "strategy"),
        "spy":      to_curve(spy, "spy"),
        "original": to_curve(orig, "original"),
    }

    # --- Drawdowns ---
    def to_dd(s):
        dd = _drawdown(s.values)
        return [{"date": d.strftime("%Y-%m"), "dd": float(v)} for d, v in zip(s.index, dd)]
    drawdowns = {"strategy": to_dd(strat), "spy": to_dd(spy)}

    # --- Annual returns table ---
    def yr(s):
        return ((1 + s).groupby(s.index.year).prod() - 1).to_dict()
    sy = yr(strat); spyy = yr(spy)
    # Best ETF held + worst month per year
    picks["year"] = pd.to_datetime(picks["rebal_date"]).dt.year
    annual = []
    years = sorted(sy.keys())
    for y in years:
        mask = strat.index.year == y
        worst_m = float(strat[mask].min()) if mask.any() else float("nan")
        # Best ETF: most-frequent top1 in that year
        sub = picks[picks["year"] == y]
        best_etf = sub["top1"].mode().iloc[0] if len(sub) else ""
        annual.append({
            "year": int(y),
            "strategy": float(sy[y]),
            "spy": float(spyy.get(y, float("nan"))),
            "excess": float(sy[y] - spyy.get(y, 0.0)),
            "best_etf": best_etf,
            "worst_month": worst_m,
        })

    # --- Monthly heatmap ---
    heatmap = []
    for d, v in zip(strat.index, strat.values):
        heatmap.append({"year": int(d.year), "month": int(d.month), "ret": float(v)})

    # --- Rolling sharpe ---
    rs = _rolling_sharpe(strat)
    rb = _rolling_sharpe(spy)
    rolling = []
    for d, vs, vb in zip(strat.index, rs.values, rb.values):
        rolling.append({
            "date": d.strftime("%Y-%m"),
            "strategy": None if np.isnan(vs) else float(vs),
            "spy": None if np.isnan(vb) else float(vb),
        })
    # 12m rolling excess
    excess_roll = []
    for i in range(len(strat)):
        if i < 11:
            excess_roll.append({"date": strat.index[i].strftime("%Y-%m"), "excess": None})
            continue
        s_w = strat.values[i - 11:i + 1]
        b_w = spy.values[i - 11:i + 1]
        e = float(np.prod(1 + s_w) - np.prod(1 + b_w))
        excess_roll.append({"date": strat.index[i].strftime("%Y-%m"), "excess": e})

    # --- Key stats ---
    stats_strat = _key_stats(strat)
    stats_spy = _key_stats(spy)
    up_c, dn_c = _capture(strat.values, spy.values)
    stats_strat["upside_capture"] = up_c
    stats_strat["downside_capture"] = dn_c
    stats_spy["upside_capture"] = 1.0
    stats_spy["downside_capture"] = 1.0

    # SPY underperformance streak
    diff = strat.values - spy.values
    longest_under = cur = 0
    for v in diff:
        if v < 0:
            cur += 1
            if cur > longest_under: longest_under = cur
        else:
            cur = 0
    stats_strat["longest_spy_underperf"] = longest_under

    # --- Trade log ---
    trade_log = []
    prev = None
    for _, row in picks.iterrows():
        weights = {}
        if not row["spy_gated"]:
            weights[row["top1"]] = weights.get(row["top1"], 0.0) + W_TOP1
        else:
            weights["SHY"] = weights.get("SHY", 0.0) + W_TOP1
        for nm, wv in zip(row["topk"], row["topk_w"]):
            wv = 1.0 / K if (wv is None or (isinstance(wv, float) and np.isnan(wv))) else float(wv)
            weights[nm] = weights.get(nm, 0.0) + W_TOPK * wv
        d = pd.to_datetime(row["rebal_date"])
        used_i = int(row["used_i"])
        cur_reg = int(cache["current_reg"][used_i])
        pred_reg = int(cache["pred_reg"][used_i]) if cache["pred_reg"][used_i] != -1 else cur_reg
        lookback = 21 if (pred_reg != cur_reg and pred_reg != -1) else 63
        trade_log.append({
            "date": d.strftime("%Y-%m-%d"),
            "from": prev or {},
            "to": {k: round(v, 4) for k, v in weights.items()},
            "regime": REGIME_LABELS[cur_reg],
            "lookback": lookback,
            "deferred": bool(row["deferred"]),
            "ret": float(row["gross_ret"]),
        })
        prev = {k: round(v, 4) for k, v in weights.items()}

    # --- Component attribution ---
    print("[gen] Building component attribution...")
    attrib = build_attribution(cache, month_last_pos)

    # --- Regime breakdown ---
    print("[gen] Building regime breakdown...")
    regime = regime_breakdown(cache, strat, picks)

    # Average monthly turnover from picks weights
    weights_mat = []
    etf_idx = {e: j for j, e in enumerate(ETFS)}
    for _, row in picks.iterrows():
        w = np.zeros(len(ETFS))
        if row["spy_gated"]:
            w[etf_idx["SHY"]] += W_TOP1
        else:
            w[etf_idx[row["top1"]]] += W_TOP1
        for nm, wv in zip(row["topk"], row["topk_w"]):
            wv = 1.0 / K if (wv is None or (isinstance(wv, float) and np.isnan(wv))) else float(wv)
            w[etf_idx[nm]] += W_TOPK * wv
        weights_mat.append(w)
    W = np.array(weights_mat)
    dW = np.abs(np.diff(W, axis=0, prepend=np.zeros((1, W.shape[1]))))
    monthly_turnover = float(dW.sum(axis=1).mean())

    # --- Header / headline ---
    headline = {
        "name": "ETF Momentum Rotation — AI-Enhanced",
        "subtitle": f"Backtest: {strat.index.min().strftime('%b %Y')} – {strat.index.max().strftime('%b %Y')} ({len(strat)} months)",
        "cagr_full": full_stats["cagr"],
        "sharpe_full": full_stats["sharpe"],
        "max_dd_full": full_stats["max_dd"],
        "n_full": full_stats["n"],
        "monthly_turnover": monthly_turnover,
        "annual_turnover": monthly_turnover * 12,
        "n_trades": int(len(picks)),
    }

    # Annotations for hero chart
    annotations = [
        {"date": "2020-03", "label": "COVID crash"},
        {"date": "2022-06", "label": "Energy rotation"},
        {"date": "2018-12", "label": "Q4-2018 / FOMC"},
        {"date": "2023-01", "label": "Tech rebound"},
    ]

    out = {
        "meta": {
            "generated": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "scripts/generate_presentation.py",
            "validates_against": "results/FINAL_STRATEGY_VALIDATED.md",
        },
        "headline": headline,
        "validation": {
            "target": {"cagr": 0.2361, "sharpe": 1.50, "max_dd": -0.1294},
            "actual": full_stats,
            "match": (
                abs(full_stats["cagr"] - 0.2361) < 0.005
                and abs(full_stats["sharpe"] - 1.50) < 0.05
                and abs(full_stats["max_dd"] - -0.1294) < 0.005
            ),
        },
        "equity": equity,
        "annual_returns": annual,
        "monthly_heatmap": heatmap,
        "drawdowns": drawdowns,
        "rolling_sharpe": rolling,
        "rolling_excess": excess_roll,
        "key_stats": {"strategy": stats_strat, "spy": stats_spy},
        "regime_breakdown": regime,
        "trade_log": trade_log,
        "attribution": attrib,
        "annotations": annotations,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"[gen] Wrote {OUT_PATH} ({size_kb:.1f} KB)")
    print(f"[gen] Validation: target 23.61/1.50/-12.94  actual "
          f"{full_stats['cagr']*100:.2f}/{full_stats['sharpe']:.2f}/{full_stats['max_dd']*100:.2f}")


if __name__ == "__main__":
    main()
