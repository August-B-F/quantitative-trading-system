"""Phase 8:
- Rebalance inertia / weekly-check rule: only rotate top1 if new leader > current by X%
- Dispersion-adaptive top_k: use top1 when dispersion high, top3+ when low
- Dispersion-adaptive split weight
- Combine inertia with the current champion
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


def run_loop(cfg_ov, pred_reg, pick_override=None, size_override=None):
    """Generic rebalance loop with optional per-i pick/size overrides.

    pick_override(i, engine, last_top1) -> (top1, tk) or None to use default
    size_override(i, engine, top1, tk) -> (w1, topk_weights_vec) or None
    """
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(cfg_ov or {})
    bundle = _STATE["bundle"]
    engine = PortfolioEngine(bundle, pred_reg, cfg)
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
    last_top1 = None
    for rebal_date, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days if defer_enabled else 0, event_mask, engine.n_days)
        if pick_override is not None:
            r = pick_override(i, engine, last_top1)
            if r is None:
                top1, tk = engine.pick_at(i)
            else:
                top1, tk = r
        else:
            top1, tk = engine.pick_at(i)
        last_top1 = top1
        r1 = engine.fwd_arr[i, top1] if engine.spy_dist[i] > engine.sma_buffer else engine.cash_fwd[i]
        if size_override is not None:
            w1, wk = size_override(i, engine, top1, tk)
            if wk is None:
                # compute default inv-vol
                sel_atr = engine.atr_arr[i, tk]
                inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
                wk = np.full(len(tk), 1.0/len(tk)) if np.isnan(inv).all() else inv / np.nansum(inv)
            rk = np.nansum(engine.fwd_arr[i, tk] * wk)
            rets.append(w1 * r1 + (1.0 - w1) * rk)
        else:
            sel_atr = engine.atr_arr[i, tk]
            inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
            if np.isnan(inv).all():
                rk = np.nanmean(engine.fwd_arr[i, tk])
            else:
                w = inv / np.nansum(inv)
                rk = np.nansum(engine.fwd_arr[i, tk] * w)
            rets.append(engine.top1_w * r1 + engine.topk_w * rk)
    return compute_stats(np.array(rets))


# --- Inertia: only rotate top1 if new leader margin > X ---
def inertia_pick(margin):
    def _p(i, eng, last):
        row = eng.sf[i]
        if last is None:
            return None  # use default
        if not np.isfinite(row[last]):
            return None
        new_top = int(np.argmax(row))
        if new_top == last:
            return None
        best_val = row[new_top]
        cur_val = row[last]
        if best_val - cur_val < margin:
            # keep current leader as top1, but still re-rank the rest
            tk = np.argsort(-row)[: eng.k]
            # ensure `last` is in tk
            if last not in tk:
                tk = np.concatenate(([last], tk[:-1]))
            return last, tk
        return None
    return _p


# --- Dispersion-adaptive: load dispersion feature ---
def get_dispersion():
    _load()
    d = _STATE["bundle"].df.get("cross_sectional_dispersion_63d__dispersion")
    if d is None:
        return None
    return d.values


DISP = get_dispersion()


def disp_adaptive_size(low_thresh, high_thresh, w_low=0.40, w_high=0.75):
    """When dispersion high → high top1 weight (concentrate); when low → diversify."""
    def _s(i, eng, top1, tk):
        if DISP is None or np.isnan(DISP[i]):
            return eng.top1_w, None
        d = DISP[i]
        if d >= high_thresh: w = w_high
        elif d <= low_thresh: w = w_low
        else:
            # linear interp
            frac = (d - low_thresh) / (high_thresh - low_thresh)
            w = w_low + frac * (w_high - w_low)
        return w, None
    return _s


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase8_adaptive_and_inertia  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]
    _load(); base_pred = _STATE["pred_reg"]
    gated = get_gated_pred(0.40)

    if DISP is not None:
        d_valid = DISP[~np.isnan(DISP)]
        print(f"dispersion pct: 20={np.percentile(d_valid,20):.4f} 50={np.percentile(d_valid,50):.4f} 80={np.percentile(d_valid,80):.4f}")

    experiments = []
    # Inertia on champion
    for m in (0.005, 0.01, 0.015, 0.02, 0.03, 0.05):
        experiments.append((f"P8.01_inertia_{int(m*1000)}bp_champ", CHAMP, gated, inertia_pick(m), None))
    # Inertia on baseline (attribution)
    for m in (0.01, 0.02, 0.03):
        experiments.append((f"P8.02_inertia_{int(m*1000)}bp_base", {}, base_pred, inertia_pick(m), None))
    # Dispersion-adaptive split
    if DISP is not None:
        experiments.append(("P8.03_disp_adapt_champ_0.03_0.06", CHAMP, gated, None,
                            disp_adaptive_size(0.03, 0.06, 0.40, 0.75)))
        experiments.append(("P8.04_disp_adapt_champ_0.02_0.05", CHAMP, gated, None,
                            disp_adaptive_size(0.02, 0.05, 0.40, 0.80)))
        experiments.append(("P8.05_disp_adapt_base_0.03_0.06", {}, base_pred, None,
                            disp_adaptive_size(0.03, 0.06, 0.40, 0.70)))

    for name, ov, pr, pk, sf in experiments:
        try: s = run_loop(ov, pr, pk, sf)
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
