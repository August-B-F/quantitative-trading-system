"""Phase 21:
- Measure champion turnover vs baseline
- Try volatility-target scaling: scale gross exposure by target_vol / realized_vol
- Try equal-vol contribution sizing between top-1 and top-k legs
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats, run_backtest  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def gated(thr=0.40):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<thr
    out[w&lc]=cur[w&lc]; return out

def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total


def measure_turnover_and_run(cfg_ov, sig, pred, vol_target=None):
    """Run backtest but also measure turnover (sum of |delta| between months).
    Optionally scale exposure to a target vol.
    """
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(cfg_ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    defer_enabled = bool(cfg.get("fomc_defer_enabled", True))
    defer_days = int(cfg.get("fomc_defer_days", 3))
    pre = int(cfg.get("fomc_window_pre", 0)); post = int(cfg.get("fomc_window_after", 2))
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng.n_days, fomc_idx, pre_days=pre, post_days=post) if defer_enabled else None

    # precompute trailing 63d vol for vol_target scaling
    if vol_target is not None:
        fwd_arr = eng.fwd_arr  # for portfolio composite vol we'd need the monthly series — approximate with SPY vol
        spy_ret = b.df.get("vol_63d__SPY")

    prev_weights = None
    rets = []
    turnover = 0.0
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days if defer_enabled else 0, event_mask, eng.n_days)
        top1, tk = eng.pick_at(i)
        # build weight vector across universe
        w = np.zeros(eng.n_uni)
        r1 = eng.fwd_arr[i, top1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        cash_idx = eng.universe.index(eng.cash) if eng.spy_dist[i] <= eng.sma_buffer else None
        if cash_idx is not None:
            w[cash_idx] += eng.top1_w
        else:
            w[top1] += eng.top1_w
        sel_atr = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            wts = np.full(len(tk), 1.0/len(tk))
        else:
            wts = inv / np.nansum(inv)
        rk_wt = wts * eng.topk_w
        for j, ti in enumerate(tk):
            w[int(ti)] += rk_wt[j]

        # scale exposure
        if vol_target is not None and spy_ret is not None:
            sv = spy_ret.iloc[i] if not np.isnan(spy_ret.iloc[i]) else 0.15
            scale = min(vol_target / max(sv, 0.05), 1.2)
            w_scaled = w * scale
        else:
            w_scaled = w

        # compute portfolio return using w
        r_port = 0.0
        for j in range(eng.n_uni):
            if w_scaled[j] > 0:
                r_port += w_scaled[j] * eng.fwd_arr[i, j]
        rets.append(r_port)

        if prev_weights is not None:
            turnover += np.abs(w - prev_weights).sum()
        prev_weights = w
    stats = compute_stats(np.array(rets))
    stats["turnover"] = turnover / len(rets) if rets else 0.0
    return stats


def main():
    g = gated(0.40)
    _load(); base_pred = _STATE["pred_reg"]
    sig = rankagg([(42,1),(63,3),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase21_turnover_and_volscale  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | avg turnover | verdict |",
             "|---|---|---|---|---|---|"]

    experiments = [
        ("P21.01_champ_turnover", CHAMP, sig, g, None),
        ("P21.02_base_turnover",  {}, None, base_pred, None),
        ("P21.03_champ_voltgt15", CHAMP, sig, g, 0.15),
        ("P21.04_champ_voltgt20", CHAMP, sig, g, 0.20),
        ("P21.05_champ_voltgt12", CHAMP, sig, g, 0.12),
    ]
    for name, ov, sg, pr, vt in experiments:
        if sg is None:
            # use default engine, no custom sig
            _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
            eng = PortfolioEngine(_STATE["bundle"], pr, cfg)
            res = run_backtest(eng, _STATE["test_dates"], cfg)
            s = dict(res.stats); s["turnover"] = float("nan")
        else:
            try: s = measure_turnover_and_run(ov, sg, pr, vol_target=vt)
            except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | | ERR |"); continue
        t = s.get("turnover", float("nan"))
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), f"turnover={t:.2f}", v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {t:.2f} | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
