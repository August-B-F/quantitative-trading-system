"""Same cost grid for the canonical baseline, for apples-to-apples comparison."""
from __future__ import annotations
import sys, copy, types
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402

CANON = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]


def run_canonical():
    _load(); b = _STATE["bundle"]
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe": CANON, "top1_weight": 0.50, "top3_weight": 0.50,
                "fomc_window_pre": 0, "fomc_window_after": 2, "fomc_defer_days": 3})
    shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
        "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
    shim.returns = b.returns
    eng = PortfolioEngine(shim, _STATE["pred_reg"], cfg)

    td = _STATE["test_dates"]
    pos = pd.Series(eng.dates.get_indexer(td), index=td)
    month_last = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng.n_days, fomc_idx, pre_days=0, post_days=2)

    all_tickers = sorted(set(CANON))
    rows = []; rets = []; dates = []
    for rd, p in month_last.items():
        i, _ = resolve_rebalance_index(int(p), 3, evm, eng.n_days)
        t1, tk = eng.pick_at(i)
        w_row = {t: 0.0 for t in all_tickers}
        if eng.spy_dist[i] > eng.sma_buffer:
            w_row[eng.universe[t1]] += eng.top1_w
        else:
            w_row[eng.cash] += eng.top1_w
        sel = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel > 0, sel, np.nan)
        if np.isnan(inv).all():
            wk = np.ones_like(inv) / len(inv)
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            wk = inv / np.nansum(inv)
            rk = np.nansum(eng.fwd_arr[i, tk] * wk)
        for j, kk in enumerate(tk):
            if not np.isnan(wk[j]):
                w_row[eng.universe[kk]] += eng.topk_w * wk[j]
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        rows.append(w_row); rets.append(eng.top1_w*r1 + eng.topk_w*rk); dates.append(rd)

    W = pd.DataFrame(rows, index=pd.Index(dates), columns=all_tickers).fillna(0.0)
    gross = pd.Series(rets, index=pd.Index(dates))
    return W, gross


def main():
    W, gross = run_canonical()
    prev = W.shift(1).fillna(0.0)
    to = 0.5 * (W - prev).abs().sum(axis=1)
    print(f"Canonical rebalances: {len(W)}")
    print(f"Avg 1-way turnover: {to.mean():.3f}")
    print(f"Annualized:         {to.mean()*12:.2f}x")
    print()
    print(f"{'cost_bps':>10} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8}")
    for bps in [0, 1, 2, 5, 10, 20, 40]:
        nr = (gross - (bps/10_000.0)*2.0*to).values
        s = compute_stats(nr)
        print(f"{bps:>10}bps {s['cagr']*100:>7.2f}% {s['sharpe']:>8.2f} {s['max_dd']*100:>7.2f}%")


if __name__ == "__main__":
    main()
