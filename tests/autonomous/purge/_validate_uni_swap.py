"""Universe perturbation test for the ROBUST champion.

Hypothesis: the Robust stack shouldn't rely on the exact ETF symbols. Swap
semantically-equivalent tickers (SOXX<->SMH, QQQ<->QQQE, GLD<->IAU, XLE<->VDE,
IGV<->IGM) and re-run. If Sharpe collapses on any single substitution, that
ticker carries idiosyncratic alpha (bad). If Sharpe is similar across swaps,
the strategy is universe-robust (good).

Run from tests/autonomous/:
    py -3 purge/_validate_uni_swap.py
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

SIG_GATE = 0.40
UNI_TIER = 0.50
RANK_W = [(42, 1), (63, 3), (126, 1)]
W_NORM = 0.50
W_FULL = 0.82
BOOST_LB_M = 9
BOOST_THR = 0.30
SPY_FAST_LB = 63
SPY_FAST_THR = 0.12
FOMC_PRE, FOMC_POST, FOMC_DEFER = 0, 2, 3


def run_with_uni(stable_uni, trans_uni):
    _load(); b = _STATE["bundle"]
    # Check availability
    cols = set(b.returns[63].columns)
    for t in set(stable_uni) | set(trans_uni):
        if t not in cols:
            return {"error": f"{t} not in panel"}
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur) & (pr >= 0)
    low = np.nan_to_num(mp, nan=0.0) < SIG_GATE
    gated[want & low] = cur[want & low]

    # Rank agg signal (over all panel tickers)
    cm = None; ranks = None; total = sum(w for _, w in RANK_W)
    for lb, w in RANK_W:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        rk = r.rank(axis=1, method="average") * w
        ranks = rk if ranks is None else ranks + rk
    sig = ranks / total
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    def mk(uni, w1):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe": uni, "top1_weight": w1, "top3_weight": 1 - w1,
                    "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
                    "fomc_defer_days": FOMC_DEFER})
        shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
            "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    engs = {}
    for uni_n, uni in [("s", stable_uni), ("t", trans_uni)]:
        for w1 in (W_NORM, W_FULL):
            engs[(uni_n, w1)] = mk(uni, w1)

    td = _STATE["test_dates"]
    eng0 = engs[("s", W_NORM)]
    pos = pd.Series(eng0.dates.get_indexer(td), index=td)
    month_last = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng0.n_days, fomc_idx, pre_days=FOMC_PRE, post_days=FOMC_POST)

    def ret_at(eng, i):
        t1, tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel > 0, sel, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []; history = []
    for rd, p in month_last.items():
        i, _ = resolve_rebalance_index(int(p), FOMC_DEFER, evm, eng0.n_days)
        use_t = (pr[i] != cur[i]) and (pr[i] >= 0) and \
                (not np.isnan(mp[i])) and (mp[i] >= UNI_TIER)
        if len(history) >= BOOST_LB_M:
            c9 = np.prod([1 + h for h in history[-BOOST_LB_M:]]) - 1
        else:
            c9 = 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = W_FULL if (c9 > BOOST_THR or sv > SPY_FAST_THR) else W_NORM
        uni_n = "t" if use_t else "s"
        r = ret_at(engs[(uni_n, w1)], i)
        history.append(r); rets.append(r)
    return compute_stats(np.array(rets))


BASE_STABLE = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
BASE_TRANS_ADD = ["TLT", "AGG", "XLV", "XLF"]

SWAPS = [
    ("baseline", BASE_STABLE, BASE_STABLE + BASE_TRANS_ADD),
    ("SOXX->SMH", [t if t != "SOXX" else "SMH" for t in BASE_STABLE],
                   [t if t != "SOXX" else "SMH" for t in BASE_STABLE] + BASE_TRANS_ADD),
    ("QQQ->QQQE", [t if t != "QQQ" else "QQQE" for t in BASE_STABLE],
                   [t if t != "QQQ" else "QQQE" for t in BASE_STABLE] + BASE_TRANS_ADD),
    ("GLD->IAU",  [t if t != "GLD" else "IAU" for t in BASE_STABLE],
                   [t if t != "GLD" else "IAU" for t in BASE_STABLE] + BASE_TRANS_ADD),
    ("XLE->VDE",  [t if t != "XLE" else "VDE" for t in BASE_STABLE],
                   [t if t != "XLE" else "VDE" for t in BASE_STABLE] + BASE_TRANS_ADD),
    ("IGV->IGM",  [t if t != "IGV" else "IGM" for t in BASE_STABLE],
                   [t if t != "IGV" else "IGM" for t in BASE_STABLE] + BASE_TRANS_ADD),
    ("SHY->BIL",  [t if t != "SHY" else "BIL" for t in BASE_STABLE],
                   [t if t != "SHY" else "BIL" for t in BASE_STABLE] + BASE_TRANS_ADD),
    ("TLT->IEF",  BASE_STABLE, BASE_STABLE + [t if t != "TLT" else "IEF" for t in BASE_TRANS_ADD]),
    ("AGG->BND",  BASE_STABLE, BASE_STABLE + [t if t != "AGG" else "BND" for t in BASE_TRANS_ADD]),
    ("+DBC",      BASE_STABLE, BASE_STABLE + BASE_TRANS_ADD + ["DBC"]),
    ("+USMV",     BASE_STABLE, BASE_STABLE + BASE_TRANS_ADD + ["USMV"]),
    ("drop XLE",  [t for t in BASE_STABLE if t != "XLE"],
                   [t for t in BASE_STABLE if t != "XLE"] + BASE_TRANS_ADD),
    ("drop GLD",  [t for t in BASE_STABLE if t != "GLD"],
                   [t for t in BASE_STABLE if t != "GLD"] + BASE_TRANS_ADD),
    ("drop IGV",  [t for t in BASE_STABLE if t != "IGV"],
                   [t for t in BASE_STABLE if t != "IGV"] + BASE_TRANS_ADD),
]


def main():
    print(f"{'variant':<14} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>9}")
    for name, s, t in SWAPS:
        r = run_with_uni(s, t)
        if "error" in r:
            print(f"{name:<14}  SKIPPED ({r['error']})")
        else:
            print(f"{name:<14} {r['cagr']*100:>7.2f}% {r['sharpe']:>8.2f} {r['max_dd']*100:>8.2f}%")


if __name__ == "__main__":
    main()
