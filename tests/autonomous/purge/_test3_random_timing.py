"""TEST 3: Random timing test.

For each triggered layer, replace actual firing dates with random dates
at the same frequency. 500 iterations. Measure whether actual trigger
Sharpe is above the 95th percentile of random-timing Sharpe.
"""
from __future__ import annotations
import sys, copy, types, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from _runner import _load_all, rank_agg_signal, make_engine, default_config, CANONICAL_UNI, DROP_OVERLAP_UNI, TRANS_ADD
from utils.base_test import _STATE
from backtest.engine import compute_stats
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index

# We test layers that have triggers:
# - L3 proba gate (classifier signal gate)
# - L5 trans universe trigger (proba >= 0.50)
# - L8 DD trigger (trail3m < -2%)
# - L9 FULL boost trigger (trail9m > 30% OR SPY 63d > 12%)
# - L10 WARM boost trigger (trail6m > 25% OR SPY 21d > 10%)


def prepare():
    c = _load_all()
    b = c["b"]
    sig = rank_agg_signal()
    pr_raw = c["pr_ext"]; mp_raw = c["mp_ext"]; cur = c["cur_reg"]
    gated = pr_raw.copy()
    want = (pr_raw != cur) & (pr_raw >= 0)
    low = np.nan_to_num(mp_raw, nan=0.0) < 0.40
    gated[want & low] = cur[want & low]

    stable_uni = DROP_OVERLAP_UNI
    trans_uni = stable_uni + TRANS_ADD

    def mk(uni, w1):
        return make_engine(b, gated, uni, w1, 1 - w1, 0, 1, 4, sig)

    WS = [0.40, 0.50, 0.62, 0.70, 0.82]
    engs = {}
    for uni_n, uni in [("s", stable_uni), ("t", trans_uni)]:
        for w1 in WS:
            engs[(uni_n, w1)] = mk(uni, w1)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engs[("s", 0.62)].dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    n_days = engs[("s", 0.62)].n_days
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=0, post_days=1)

    exec_idx = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, n_days)
        exec_idx.append(i)
    exec_idx = np.array(exec_idx)

    return dict(engs=engs, exec_idx=exec_idx, month_dates=list(month_last.index),
                pr_raw=pr_raw, mp_raw=mp_raw, cur=cur,
                spy_63=c["spy_63"], spy_21=c["spy_21"])


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


def run_with_masks(env, dd_mask, full_mask, warm_mask, trans_mask):
    """Run the P59 backtest but with given boolean masks for each trigger."""
    engs = env["engs"]; exec_idx = env["exec_idx"]
    w_dd, w_norm, w_warm, w_full = 0.40, 0.62, 0.70, 0.82
    rets = []
    for k_idx, i in enumerate(exec_idx):
        use_t = bool(trans_mask[k_idx])
        uni_n = "t" if use_t else "s"
        if dd_mask[k_idx]:
            w1 = w_dd
        elif full_mask[k_idx]:
            w1 = w_full
        elif warm_mask[k_idx]:
            w1 = w_warm
        else:
            w1 = w_norm
        r = ret_at(engs[(uni_n, w1)], i)
        rets.append(r)
    return compute_stats(np.array(rets))


def compute_actual_masks(env):
    """Compute the actual P59 trigger masks at each rebalance index."""
    exec_idx = env["exec_idx"]
    pr_raw = env["pr_raw"]; mp_raw = env["mp_raw"]; cur = env["cur"]
    spy_63 = env["spy_63"]; spy_21 = env["spy_21"]

    trans_mask = np.zeros(len(exec_idx), dtype=bool)
    for k_idx, i in enumerate(exec_idx):
        tr = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and (not np.isnan(mp_raw[i])) and (mp_raw[i] >= 0.50)
        trans_mask[k_idx] = tr

    # We need to simulate with the correct base (actual trans mask fixed)
    # First pass: run with NO kelly triggers to get the normal-mode equity curve
    # Then use that history to determine dd/full/warm firings
    engs = env["engs"]
    w_norm = 0.62
    history = []
    for k_idx, i in enumerate(exec_idx):
        uni_n = "t" if trans_mask[k_idx] else "s"
        r = ret_at(engs[(uni_n, w_norm)], i)
        history.append(r)
    history_arr = np.array(history)

    # Now we need the actual P59 masks in INTERLEAVED order — the history from
    # THIS CONFIG (with Kelly triggers active) affects subsequent triggers. So
    # we have to run it forward.
    dd_mask = np.zeros(len(exec_idx), dtype=bool)
    full_mask = np.zeros(len(exec_idx), dtype=bool)
    warm_mask = np.zeros(len(exec_idx), dtype=bool)
    hist = []
    w_dd, w_warm, w_full = 0.40, 0.70, 0.82
    for k_idx, i in enumerate(exec_idx):
        cum_dd = np.prod([1 + h for h in hist[-3:]]) - 1 if len(hist) >= 3 else 0.05
        cum_warm_h = np.prod([1 + h for h in hist[-6:]]) - 1 if len(hist) >= 6 else 0.05
        cum_full_h = np.prod([1 + h for h in hist[-9:]]) - 1 if len(hist) >= 9 else 0.05
        spy_v63 = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        spy_v21 = spy_21[i] if not np.isnan(spy_21[i]) else -1.0
        if cum_dd < -0.02:
            dd_mask[k_idx] = True; w1 = w_dd
        elif cum_full_h > 0.30 or spy_v63 > 0.12:
            full_mask[k_idx] = True; w1 = w_full
        elif cum_warm_h > 0.25 or spy_v21 > 0.10:
            warm_mask[k_idx] = True; w1 = w_warm
        else:
            w1 = w_norm
        uni_n = "t" if trans_mask[k_idx] else "s"
        r = ret_at(engs[(uni_n, w1)], i)
        hist.append(r)
    return dd_mask, full_mask, warm_mask, trans_mask


def main():
    env = prepare()
    n = len(env["exec_idx"])
    dd_mask, full_mask, warm_mask, trans_mask = compute_actual_masks(env)
    n_dd, n_full, n_warm, n_trans = dd_mask.sum(), full_mask.sum(), warm_mask.sum(), trans_mask.sum()
    print(f"Actual firings: DD={n_dd}, FULL={n_full}, WARM={n_warm}, TRANS={n_trans}, n_months={n}")

    # Baseline: actual P59 stats
    actual = run_with_masks(env, dd_mask, full_mask, warm_mask, trans_mask)
    print(f"Actual P59 Sharpe: {actual['sharpe']:.3f}  CAGR: {actual['cagr']*100:.2f}")

    # No-kelly reference (all-off)
    zero_mask = np.zeros(n, dtype=bool)
    no_kelly = run_with_masks(env, zero_mask, zero_mask, zero_mask, trans_mask)
    print(f"No-Kelly reference (trans_mask kept): Sharpe {no_kelly['sharpe']:.3f}  CAGR {no_kelly['cagr']*100:.2f}")

    rng = np.random.default_rng(42)
    ITER = 500
    rows = []

    # Test each trigger by randomizing its timing while keeping others at actual
    for layer_name, actual_mask, cnt in [
        ("L8 DD", dd_mask, n_dd),
        ("L9 FULL", full_mask, n_full),
        ("L10 WARM", warm_mask, n_warm),
        ("L5 TRANS", trans_mask, n_trans),
    ]:
        # Actual Sharpe with only this trigger (others off) — to isolate its contribution
        if layer_name == "L8 DD":
            s_actual = run_with_masks(env, actual_mask, zero_mask, zero_mask, trans_mask)
        elif layer_name == "L9 FULL":
            s_actual = run_with_masks(env, zero_mask, actual_mask, zero_mask, trans_mask)
        elif layer_name == "L10 WARM":
            s_actual = run_with_masks(env, zero_mask, zero_mask, actual_mask, trans_mask)
        else:  # L5 TRANS
            s_actual = run_with_masks(env, zero_mask, zero_mask, zero_mask, actual_mask)

        if layer_name == "L5 TRANS":
            # Compare to all-stable (no trans)
            no_layer = run_with_masks(env, zero_mask, zero_mask, zero_mask, np.zeros(n, dtype=bool))
        else:
            no_layer = no_kelly
        actual_delta_sharpe = s_actual["sharpe"] - no_layer["sharpe"]

        # Randomize: pick `cnt` months at random
        rand_sharpes = []
        for _ in range(ITER):
            idx = rng.choice(n, size=int(cnt), replace=False)
            rmask = np.zeros(n, dtype=bool); rmask[idx] = True
            if layer_name == "L8 DD":
                s_rand = run_with_masks(env, rmask, zero_mask, zero_mask, trans_mask)
            elif layer_name == "L9 FULL":
                s_rand = run_with_masks(env, zero_mask, rmask, zero_mask, trans_mask)
            elif layer_name == "L10 WARM":
                s_rand = run_with_masks(env, zero_mask, zero_mask, rmask, trans_mask)
            else:
                s_rand = run_with_masks(env, zero_mask, zero_mask, zero_mask, rmask)
            rand_sharpes.append(s_rand["sharpe"])
        rand_deltas = np.array(rand_sharpes) - no_layer["sharpe"]
        p50 = float(np.percentile(rand_deltas, 50))
        p75 = float(np.percentile(rand_deltas, 75))
        p95 = float(np.percentile(rand_deltas, 95))
        pct = float((rand_deltas < actual_delta_sharpe).mean() * 100)
        if pct >= 95: verdict = "**KEEP** — timing matters (>p95)"
        elif pct >= 75: verdict = "marginal — between p75 and p95"
        else: verdict = "REMOVE — random dates would do at least as well"
        print(f"  {layer_name}: actual d_sharpe={actual_delta_sharpe:+.4f}  rand p50={p50:+.4f}  p75={p75:+.4f}  p95={p95:+.4f}  pct={pct:.1f}  -> {verdict}")
        rows.append((layer_name, actual_delta_sharpe, p50, p75, p95, pct, verdict))

    lines = ["# TEST 3 — Random timing test\n",
             "For each triggered layer, we compute the actual Sharpe improvement\n"
             "from enabling just that layer (trans_mask held constant), and compare\n"
             "against the Sharpe distribution when the same number of firings are\n"
             "placed at RANDOM dates (500 iterations).\n",
             f"Actual firings: DD={n_dd}, FULL={n_full}, WARM={n_warm}, TRANS={n_trans}  (n_months={n})\n",
             "| Layer | Actual Δ Sharpe | Rand p50 | Rand p75 | Rand p95 | Percentile | Verdict |",
             "|-------|------------------|----------|----------|----------|------------|---------|"]
    for L, a, p50, p75, p95, pct, v in rows:
        lines.append(f"| {L} | {a:+.4f} | {p50:+.4f} | {p75:+.4f} | {p95:+.4f} | {pct:.1f}% | {v} |")
    out = "\n".join(lines) + "\n"
    with open(HERE / "TEST3_random_timing.md", "w", encoding="utf-8") as f:
        f.write(out)
    print("\nSaved TEST3_random_timing.md")


if __name__ == "__main__":
    main()
