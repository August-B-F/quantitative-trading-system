"""Phase 3b: overlays on top of the champion (dropoverlap + 60/40).

- VIX level gate: force SHY when VIX > threshold
- VIX-breakout gate: force SHY when VIX > 20d MA * 1.2
- VIX-combined with SMA: both must fire (or either must fire)
- Correlation gate: if all tech correlate > thresh → prefer non-tech
- Drawdown-lookback gate: if 63d return of SPY < 0 AND SMA fires → deeper cash
- Regime confidence gate: require classifier argmax prob > 0.7 to switch to 21d
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


def run_gated(cfg_overrides=None, gate_fn=None):
    """Run a full backtest but apply a custom gate at each rebalance.

    gate_fn(i, engine) -> "force_shy" (applies to top1 leg) | None
    """
    _load()
    cfg = copy.deepcopy(_STATE["cfg"])
    if cfg_overrides:
        cfg.update(cfg_overrides)
    bundle = _STATE["bundle"]
    engine = PortfolioEngine(bundle, _STATE["pred_reg"], cfg)

    test_dates = _STATE["test_dates"]
    td_positions = pd.Series(engine.dates.get_indexer(test_dates), index=test_dates)
    month_last = td_positions.groupby(test_dates.to_period("M")).tail(1)

    defer_enabled = bool(cfg.get("fomc_defer_enabled", True))
    defer_days = int(cfg.get("fomc_defer_days", 3))
    pre = int(cfg.get("fomc_window_pre", 0))
    post = int(cfg.get("fomc_window_after", 2))
    fomc_idx = np.where(bundle.is_fomc_day)[0]
    event_mask = fomc_window_mask(engine.n_days, fomc_idx, pre_days=pre, post_days=post) if defer_enabled else None

    rets = []
    for rebal_date, pos in month_last.items():
        sched_pos = int(pos)
        exec_pos, _ = resolve_rebalance_index(sched_pos, defer_days if defer_enabled else 0, event_mask, engine.n_days)
        i = exec_pos
        top1, tk = engine.pick_at(i)
        # base forward return
        if gate_fn is not None and gate_fn(i, engine):
            # force SHY on top1 leg regardless of SMA
            r1 = engine.cash_fwd[i]
        else:
            r1 = engine.fwd_arr[i, top1] if engine.spy_dist[i] > engine.sma_buffer else engine.cash_fwd[i]
        sel_atr = engine.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(engine.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv)
            rk = np.nansum(engine.fwd_arr[i, tk] * w)
        rets.append(engine.top1_w * r1 + engine.topk_w * rk)

    return compute_stats(np.array(rets))


# --- Define gates ---
def _get_vix():
    _load()
    df = _STATE["bundle"].df
    for col in ("vol_features__vix", "vix", "VIX"):
        if col in df.columns:
            return df[col].values
    return None

VIX = _get_vix()
VIX_20 = pd.Series(VIX).rolling(20).mean().values if VIX is not None else None

def gate_vix_gt(thresh):
    def _g(i, eng):
        return VIX is not None and not np.isnan(VIX[i]) and VIX[i] > thresh
    return _g

def gate_vix_breakout(mult):
    def _g(i, eng):
        if VIX is None or VIX_20 is None or np.isnan(VIX[i]) or np.isnan(VIX_20[i]): return False
        return VIX[i] > VIX_20[i] * mult
    return _g

def gate_combo_or(*gates):
    def _g(i, eng):
        return any(g(i, eng) for g in gates)
    return _g

def gate_combo_and(*gates):
    def _g(i, eng):
        return all(g(i, eng) for g in gates)
    return _g


EXPERIMENTS = []
EXPERIMENTS.append(("P3b.00_champ_sanity", None))
EXPERIMENTS.append(("P3b.01_vix_gt_30", gate_vix_gt(30)))
EXPERIMENTS.append(("P3b.02_vix_gt_25", gate_vix_gt(25)))
EXPERIMENTS.append(("P3b.03_vix_gt_28", gate_vix_gt(28)))
EXPERIMENTS.append(("P3b.04_vix_bo_1.2", gate_vix_breakout(1.2)))
EXPERIMENTS.append(("P3b.05_vix_bo_1.3", gate_vix_breakout(1.3)))
EXPERIMENTS.append(("P3b.06_vix_bo_1.15", gate_vix_breakout(1.15)))
# combined: vix>25 OR sma (already native) — use OR to check if VIX>25 captures extra
# The SMA gate is already applied natively; gates here are ADDITIONAL (tighten risk).
# So VIX > 25 forces SHY ALSO when SMA is fine.
EXPERIMENTS.append(("P3b.07_vix_breakout_1.25", gate_vix_breakout(1.25)))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase3b_gates_overlays  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]
    for name, gate in EXPERIMENTS:
        try:
            s = run_gated(CHAMP, gate)
        except Exception as e:
            s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} | | | | ERR {s['error'][:40]} |")
            continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
