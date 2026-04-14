"""Phase 9: two-leg divergent momentum.

Idea: top-1 leg captures leadership (use shorter signal = 21d), top-k leg provides
diversification (use 63d stable signal regardless of regime).
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"


def get_gated_pred(thr=0.40):
    with open(PROBA, "rb") as f:
        pred_reg, maxp = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pred_reg.copy()
    want = (pred_reg != cur) & (pred_reg >= 0)
    low = np.nan_to_num(maxp, nan=0.0) < thr
    out[want & low] = cur[want & low]
    return out


def run_twoleg(cfg_ov, pred_reg, top1_lb, topk_lb):
    """Run with top1 using one lookback signal, top-k using another."""
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(cfg_ov or {})
    bundle = _STATE["bundle"]
    engine = PortfolioEngine(bundle, pred_reg, cfg)

    # Build alt momentum arrays for top1 and topk legs
    from strategy.momentum import build_momentum_array
    universe = list(cfg["universe"])
    dates = bundle.dates
    m1 = build_momentum_array(bundle.returns[top1_lb], universe, dates)
    mk = build_momentum_array(bundle.returns[topk_lb], universe, dates)
    sf1 = np.where(np.isnan(m1), -np.inf, m1)
    sfk = np.where(np.isnan(mk), -np.inf, mk)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engine.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    defer_enabled = bool(cfg.get("fomc_defer_enabled", True))
    defer_days = int(cfg.get("fomc_defer_days", 3))
    pre = int(cfg.get("fomc_window_pre", 0))
    post = int(cfg.get("fomc_window_after", 2))
    fomc_idx = np.where(bundle.is_fomc_day)[0]
    event_mask = fomc_window_mask(engine.n_days, fomc_idx, pre_days=pre, post_days=post) if defer_enabled else None

    rets = []
    for rebal_date, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days if defer_enabled else 0, event_mask, engine.n_days)
        top1 = int(np.argmax(sf1[i]))
        tk = np.argsort(-sfk[i])[: engine.k]
        r1 = engine.fwd_arr[i, top1] if engine.spy_dist[i] > engine.sma_buffer else engine.cash_fwd[i]
        sel_atr = engine.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(engine.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(engine.fwd_arr[i, tk] * w)
        rets.append(engine.top1_w * r1 + engine.topk_w * rk)
    return compute_stats(np.array(rets))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase9_twoleg_signals  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    _load()
    base_pred = _STATE["pred_reg"]
    gated = get_gated_pred(0.40)

    experiments = []
    # top1=21d (fast), topk=63d (slow) on champion
    experiments.append(("P9.01_t1_21_tk_63_champ", CHAMP, gated, 21, 63))
    experiments.append(("P9.02_t1_63_tk_21_champ", CHAMP, gated, 63, 21))
    experiments.append(("P9.03_t1_42_tk_63_champ", CHAMP, gated, 42, 63))
    experiments.append(("P9.04_t1_21_tk_126_champ", CHAMP, gated, 21, 126))
    experiments.append(("P9.05_t1_63_tk_126_champ", CHAMP, gated, 63, 126))
    experiments.append(("P9.06_t1_21_tk_63_base", {}, base_pred, 21, 63))
    experiments.append(("P9.07_t1_21_tk_42_champ", CHAMP, gated, 21, 42))

    for name, ov, pr, t1, tk in experiments:
        try: s = run_twoleg(ov, pr, t1, tk)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
