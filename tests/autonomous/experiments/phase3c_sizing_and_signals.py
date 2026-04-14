"""Phase 3c: alternative signals and sizing.

- Equal-weight top-3 (vs inverse vol)
- Momentum-score weighted top-3
- voladj_mom_63d as the stable signal (precomputed feature, already shifted)
- cross-sectional rank as signal
- Adaptive top_k by dispersion regime
- Classifier confidence-gated switching (needs proba — skip if unavail)
"""
from __future__ import annotations
import sys, datetime as dt, copy
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.60, "top3_weight":0.40}


def run_custom_engine(cfg_overrides, sizing_fn=None, pick_fn=None, stable_signal=None):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update(cfg_overrides)
    bundle = _STATE["bundle"]
    if stable_signal is not None:
        import types
        shim = types.SimpleNamespace(**{k: getattr(bundle, k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        newret = dict(bundle.returns); newret[cfg["lookback_stable"]] = stable_signal
        shim.returns = newret
        engine = PortfolioEngine(shim, _STATE["pred_reg"], cfg)
    else:
        engine = PortfolioEngine(bundle, _STATE["pred_reg"], cfg)

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
        sched_pos = int(pos)
        i, _ = resolve_rebalance_index(int(pos), defer_days if defer_enabled else 0, event_mask, engine.n_days)
        if pick_fn is not None:
            top1, tk = pick_fn(i, engine)
        else:
            top1, tk = engine.pick_at(i)
        r1 = engine.fwd_arr[i, top1] if engine.spy_dist[i] > engine.sma_buffer else engine.cash_fwd[i]
        if sizing_fn is not None:
            w = sizing_fn(i, engine, tk)
            rk = np.nansum(engine.fwd_arr[i, tk] * w)
        else:
            sel_atr = engine.atr_arr[i, tk]
            inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
            if np.isnan(inv).all():
                rk = np.nanmean(engine.fwd_arr[i, tk])
            else:
                w = inv / np.nansum(inv); rk = np.nansum(engine.fwd_arr[i, tk] * w)
        rets.append(engine.top1_w * r1 + engine.topk_w * rk)
    return compute_stats(np.array(rets))


# Sizing functions
def sz_equal(i, eng, tk):
    return np.full(len(tk), 1.0/len(tk))

def sz_momentum_weighted(i, eng, tk):
    s = eng.sf[i, tk]
    s = np.where(np.isfinite(s), s, 0)
    s = np.clip(s, 1e-6, None)  # negative/zero → tiny weight
    return s / s.sum()

def sz_inv_atr_normalized(i, eng, tk):
    # percent-ATR (price-normalized) instead of raw dollar ATR
    atr = eng.atr_arr[i, tk]
    # Need close prices — use atr21 / px. We don't have px here easily.
    # Approximation: use inv(atr/close_proxy). Use atr itself — this is champ default.
    inv = 1.0 / np.where(atr > 0, atr, np.nan)
    if np.isnan(inv).all():
        return np.full(len(tk), 1.0/len(tk))
    return inv / np.nansum(inv)


def pick_biggest_drop(i, eng):
    """Mean reversion: rank by NEGATIVE momentum (worst becomes top-1)."""
    row = eng.sf[i]
    top1 = int(np.argmin(row))
    tk = np.argsort(row)[:eng.k]
    return top1, tk


# Try voladj momentum as stable signal
def _load_voladj_signal():
    _load()
    bundle = _STATE["bundle"]
    p = Path(__file__).resolve().parents[3] / "data/features/price/quality_voladj_mom_63d.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p).reindex(bundle.dates)
    # Align columns to universe + extras
    return df


EXPERIMENTS = []
EXPERIMENTS.append(("P3c.00_sanity", {}, None, None, None))
EXPERIMENTS.append(("P3c.01_equal_topk", {}, sz_equal, None, None))
EXPERIMENTS.append(("P3c.02_mom_weighted", {}, sz_momentum_weighted, None, None))
EXPERIMENTS.append(("P3c.03_mean_reversion", {}, None, pick_biggest_drop, None))

voladj_sig = _load_voladj_signal()
if voladj_sig is not None:
    EXPERIMENTS.append(("P3c.04_voladj63_signal", {}, None, None, voladj_sig))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase3c_sizing_and_signals  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]
    for name, overr, sf, pf, sig in EXPERIMENTS:
        ov = copy.deepcopy(CHAMP); ov.update(overr or {})
        try: s = run_custom_engine(ov, sizing_fn=sf, pick_fn=pf, stable_signal=sig)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} | | | | ERR |"); continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
