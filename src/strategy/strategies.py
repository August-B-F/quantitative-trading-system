"""Per-strategy runners for the 9-strategy comparison.

Each `run_*` function consumes a PanelBundle (+ optional classifier output)
and returns ``(monthly_returns, weights_history)``:

    monthly_returns : pd.Series indexed by rebalance date, values are the
                      realized forward-21d portfolio return at that date.
    weights_history : list of (Timestamp, dict[ticker -> weight]) — the
                      target weights at each rebalance, used for the
                      account-level aggregation.

Design: the 4 ML-champion strategies (ROBUST_STACK / ROBUST_VAR / P59 / P57)
are direct promotions of the research scripts in
``tests/autonomous/champions/``. They share a common engine-per-tier setup:
6-ETF stable universe + 10-ETF transition universe, rank-aggregation
momentum signal, classifier-proba gating. The differences between them are
basket weighting, sizing policy, and FOMC window.

The canary (strategy 1, OPTIMIZED) uses ``PortfolioEngine`` directly through
``backtest.engine.run_backtest``; it is not re-implemented here.
"""
from __future__ import annotations

import copy
import logging
import pickle
import types
from pathlib import Path

import numpy as np
import pandas as pd

from strategy.portfolio import PortfolioEngine
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
from strategy.position_sizing import final_weights, inverse_vol_weights
from features.regime_labels import current_regime as _cr

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers shared by the champion adapters
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
P46_CACHE = ROOT / "tests" / "autonomous" / "cache" / "pred_proba_p46.pkl"


def _load_p46_proba():
    """Load the P46 classifier cache (pred_reg + max_proba) used by S2/7/8/9."""
    with open(P46_CACHE, "rb") as f:
        pr_raw, mp_raw = pickle.load(f)
    return pr_raw, mp_raw


def _build_rank_signal(bundle, lookbacks_and_weights):
    """Cross-sectional rank aggregation across multiple lookbacks.

    Mirrors p_robust_champion.build_rank_signal (lines 77-86).
    """
    cm = None
    ranks = None
    total = sum(w for _, w in lookbacks_and_weights)
    for lb, w in lookbacks_and_weights:
        r = bundle.returns[lb]
        if cm is None:
            cm = list(r.columns)
        else:
            r = r[cm]
        ranked = r.rank(axis=1, method="average") * w
        ranks = ranked if ranks is None else ranks + ranked
    return ranks / total


def _make_shim(bundle, rank_sig, lookback_key):
    """Shim the bundle so PortfolioEngine sees rank sig at `lookback_key`."""
    shim = types.SimpleNamespace(**{k: getattr(bundle, k) for k in (
        "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day"
    )})
    nr = dict(bundle.returns)
    nr[lookback_key] = rank_sig
    shim.returns = nr
    return shim


def _make_engine(bundle, pred_gated, cfg_global, rank_sig, uni, top1_w,
                 fomc_pre, fomc_post, fomc_defer):
    """Build a PortfolioEngine with a patched bundle for a (universe, w1) pair."""
    cfg = copy.deepcopy(cfg_global)
    cfg.update({
        "universe": uni,
        "top1_weight": top1_w,
        "top3_weight": 1.0 - top1_w,
        "fomc_window_pre": fomc_pre,
        "fomc_window_after": fomc_post,
        "fomc_defer_days": fomc_defer,
    })
    shim = _make_shim(bundle, rank_sig, cfg["lookback_stable"])
    return PortfolioEngine(shim, pred_gated, cfg)


def _month_last(test_dates, dates):
    positions = pd.Series(dates.get_indexer(test_dates), index=test_dates)
    return positions.groupby(test_dates.to_period("M")).tail(1)


def _champion_gated_pred(pr_raw, mp_raw, cur, sig_gate):
    """L3 — force pred=current when classifier max_proba < SIG_GATE."""
    gated = pr_raw.copy()
    want = (pr_raw != cur) & (pr_raw >= 0)
    low = np.nan_to_num(mp_raw, nan=0.0) < sig_gate
    gated[want & low] = cur[want & low]
    return gated


def _inv_vol_weights_exp(atr_slice, exp):
    """Generalised inverse-vol weights: w proportional to 1/sigma^exp."""
    sel = np.where(atr_slice > 0, atr_slice, np.nan)
    w = 1.0 / (sel ** exp)
    if np.isnan(w).all():
        k = len(atr_slice)
        return np.full(k, 1.0 / k)
    w = np.where(np.isnan(w), 0.0, w)
    tot = w.sum()
    if tot <= 0:
        k = len(atr_slice)
        return np.full(k, 1.0 / k)
    return w / tot


def _portfolio_weights(eng, i, top1_w, topk_w, vol_exp=1.0):
    """Build target-weight dict at daily index i with SMA-gate override."""
    top1, tk = eng.pick_at(i)
    gate_fired = eng.spy_dist[i] <= eng.sma_buffer
    universe = eng.universe
    weights: dict[str, float] = {t: 0.0 for t in universe}
    if gate_fired:
        weights[eng.cash] = weights.get(eng.cash, 0.0) + top1_w
    else:
        weights[universe[top1]] += top1_w
    w = _inv_vol_weights_exp(eng.atr_arr[i, tk], vol_exp)
    for j, pos in enumerate(tk):
        weights[universe[int(pos)]] += float(topk_w * w[j])
    return weights


def _portfolio_fwd_return(eng, i, top1_w, topk_w, vol_exp=1.0):
    """Forward-21d portfolio return at daily index i, matching the champions."""
    top1, tk = eng.pick_at(i)
    r1 = eng.fwd_arr[i, top1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
    w = _inv_vol_weights_exp(eng.atr_arr[i, tk], vol_exp)
    rk = float(np.nansum(eng.fwd_arr[i, tk] * w))
    return float(top1_w * r1 + topk_w * rk)


# ---------------------------------------------------------------------------
# Strategy 1 — OPTIMIZED (canary). Thin wrapper around the canonical engine.
# ---------------------------------------------------------------------------

def run_optimized(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """Canary strategy — reuses the stock PortfolioEngine + run_backtest."""
    from backtest.engine import run_backtest

    cfg = copy.deepcopy(cfg_global)
    # OPTIMIZED uses the same universe / lookbacks as cfg_global already.
    engine = PortfolioEngine(bundle, pred_reg, cfg)
    res = run_backtest(engine, test_dates, cfg, cost_bps=0.0)

    # Build weights_history by re-running the decision loop (cheap).
    dates = engine.dates
    n_days = engine.n_days
    fomc_idx = np.where(bundle.is_fomc_day)[0]
    event_mask = fomc_window_mask(
        n_days, fomc_idx,
        pre_days=int(cfg.get("fomc_window_pre", 0)),
        post_days=int(cfg.get("fomc_window_after", 2)),
    )
    defer_days = int(cfg.get("fomc_defer_days", 3))
    month_last = _month_last(test_dates, dates)
    weights_history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days, event_mask, n_days)
        w = _portfolio_weights(engine, i, engine.top1_w, engine.topk_w, vol_exp=1.0)
        weights_history.append((rd, w))
    return res.monthly_returns, weights_history


# ---------------------------------------------------------------------------
# Strategy 3 — DROPOVERLAP. OPTIMIZED with a trimmed universe.
# ---------------------------------------------------------------------------

def run_dropoverlap(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """Remove VGT/XLK from the universe; everything else unchanged."""
    from backtest.engine import run_backtest

    cfg = copy.deepcopy(cfg_global)
    cfg["universe"] = list(cfg_file["universe"])  # 6-ETF universe from the yaml
    engine = PortfolioEngine(bundle, pred_reg, cfg)
    res = run_backtest(engine, test_dates, cfg, cost_bps=0.0)

    dates = engine.dates
    n_days = engine.n_days
    fomc_idx = np.where(bundle.is_fomc_day)[0]
    event_mask = fomc_window_mask(
        n_days, fomc_idx,
        pre_days=int(cfg.get("fomc_window_pre", 0)),
        post_days=int(cfg.get("fomc_window_after", 2)),
    )
    defer_days = int(cfg.get("fomc_defer_days", 3))
    month_last = _month_last(test_dates, dates)
    weights_history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days, event_mask, n_days)
        w = _portfolio_weights(engine, i, engine.top1_w, engine.topk_w, vol_exp=1.0)
        weights_history.append((rd, w))
    return res.monthly_returns, weights_history


# ---------------------------------------------------------------------------
# Strategy 4 — T2_BALANCED. Rules-only, 63d momentum, equal-weight top3.
# ---------------------------------------------------------------------------

def run_t2_balanced(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """Rules momentum runner-up. No regime switch, no FOMC defer, eq-wt top3."""
    cfg = copy.deepcopy(cfg_global)
    cfg.update({
        "universe": list(cfg_file["universe"]),
        "top1_weight": 0.50,
        "top3_weight": 0.50,
        "top_k": 3,
        # Force both lookbacks to 63 so the regime-switch is a no-op (always 63d).
        "lookback_stable": 63,
        "lookback_transition": 63,
    })
    # Disable FOMC defer entirely.
    cfg["fomc_defer_enabled"] = False

    engine = PortfolioEngine(bundle, pred_reg, cfg)
    dates = engine.dates
    n_days = engine.n_days
    month_last = _month_last(test_dates, dates)

    out = {}
    weights_history = []
    for rd, pos in month_last.items():
        i = int(pos)
        top1, tk = engine.pick_at(i)
        # top-1 with SMA override
        if engine.spy_dist[i] > engine.sma_buffer:
            r1 = engine.fwd_arr[i, top1]
        else:
            r1 = engine.cash_fwd[i]
        # top-k equal-weight (T2 override)
        rk = float(np.nanmean(engine.fwd_arr[i, tk]))
        r = float(0.50 * r1 + 0.50 * rk)
        out[rd] = r

        # weights: equal-weight top3
        gate_fired = engine.spy_dist[i] <= engine.sma_buffer
        w = {t: 0.0 for t in engine.universe}
        if gate_fired:
            w[engine.cash] = w.get(engine.cash, 0.0) + 0.50
        else:
            w[engine.universe[top1]] += 0.50
        eqw = 0.50 / len(tk)
        for pos_j in tk:
            w[engine.universe[int(pos_j)]] += eqw
        weights_history.append((rd, w))

    monthly = pd.Series(out).sort_index()
    return monthly, weights_history


# ---------------------------------------------------------------------------
# Strategy 5 — TREND_SIMPLE. SPY > SMA200 -> SPY, else SHY.
# ---------------------------------------------------------------------------

def run_trend_simple(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """200-day SMA switcher on SPY; monthly rebalance."""
    dates = bundle.dates
    spy_dist = bundle.spy_dist_sma200  # distance from SMA200; >0 means above
    spy_fwd = bundle.fwd21["SPY"]
    shy_fwd = bundle.fwd21["SHY"]
    month_last = _month_last(test_dates, dates)

    out = {}
    weights_history = []
    for rd, pos in month_last.items():
        i = int(pos)
        above = spy_dist[i] > 0
        r = float(spy_fwd[i] if above else shy_fwd[i])
        out[rd] = r
        weights_history.append((rd, {"SPY": 1.0, "SHY": 0.0} if above else {"SPY": 0.0, "SHY": 1.0}))
    return pd.Series(out).sort_index(), weights_history


# ---------------------------------------------------------------------------
# Strategy 6 — DUAL_MOMENTUM. 12-1m relative + absolute filter.
# ---------------------------------------------------------------------------

def run_dual_momentum(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """Antonacci dual momentum on the 8-ETF universe.

    The pre-computed 12-1m momentum parquet is loaded directly; the bundle's
    default ``returns`` dict only carries {10,21,42,63,126}.
    """
    rdir = ROOT / "data" / "features" / "price"
    mom_df = pd.read_parquet(rdir / "returns_12_1_mom.parquet").reindex(bundle.dates)

    universe = list(cfg_file["universe"])
    cash = cfg_file.get("cash_proxy", "SHY")
    # Build aligned momentum + forward-return matrices.
    mom_arr = np.full((len(bundle.dates), len(universe)), np.nan)
    fwd_arr = np.full_like(mom_arr, np.nan)
    for j, t in enumerate(universe):
        if t in mom_df.columns:
            mom_arr[:, j] = mom_df[t].values
        fwd_arr[:, j] = bundle.fwd21[t]
    cash_fwd = bundle.fwd21[cash]

    month_last = _month_last(test_dates, bundle.dates)
    out = {}
    weights_history = []
    for rd, pos in month_last.items():
        i = int(pos)
        row = mom_arr[i]
        safe = np.where(np.isnan(row), -np.inf, row)
        # Relative winner
        winner_idx = int(np.argmax(safe))
        winner_mom = safe[winner_idx]
        # Absolute filter: if the best ETF isn't positive, go to cash
        if winner_mom <= 0 or not np.isfinite(winner_mom):
            r = float(cash_fwd[i])
            w = {t: 0.0 for t in universe}
            w[cash] = 1.0
        else:
            r = float(fwd_arr[i, winner_idx])
            w = {t: 0.0 for t in universe}
            w[universe[winner_idx]] = 1.0
        out[rd] = r
        weights_history.append((rd, w))
    return pd.Series(out).sort_index(), weights_history


# ---------------------------------------------------------------------------
# Champion core — shared loop for S2/S7/S8/S9
# ---------------------------------------------------------------------------

def _run_champion_loop(bundle, cfg_global, test_dates, *,
                       stable_uni, trans_uni,
                       sig_gate, uni_tier, rank_w,
                       fomc_pre, fomc_post, fomc_defer,
                       w_choices, sizing_rule, vol_exp,
                       pr_raw, mp_raw):
    """Shared per-rebalance loop. ``sizing_rule`` is a callable that takes
    ``(i, history, spy_63_i, spy_21_i, pr_raw, mp_raw, cur_i)`` and returns
    the top1 weight to use for this rebalance.
    """
    cur = np.asarray(_cr(bundle.df).index)
    gated = _champion_gated_pred(pr_raw, mp_raw, cur, sig_gate)
    sig = _build_rank_signal(bundle, rank_w)

    spy_63 = bundle.returns[63]["SPY"].values
    spy_21 = bundle.returns[21]["SPY"].values

    engines: dict[tuple, PortfolioEngine] = {}
    for uni_n, uni in [("s", stable_uni), ("t", trans_uni)]:
        for w1 in w_choices:
            engines[(uni_n, w1)] = _make_engine(
                bundle, gated, cfg_global, sig, uni, w1,
                fomc_pre, fomc_post, fomc_defer,
            )

    any_eng = engines[("s", w_choices[0])]
    dates = any_eng.dates
    n_days = any_eng.n_days
    fomc_idx = np.where(bundle.is_fomc_day)[0]
    event_mask = fomc_window_mask(n_days, fomc_idx,
                                  pre_days=fomc_pre, post_days=fomc_post)
    month_last = _month_last(test_dates, dates)

    out = {}
    weights_history = []
    history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), fomc_defer, event_mask, n_days)
        use_trans = (
            (pr_raw[i] != cur[i])
            and (pr_raw[i] >= 0)
            and (not np.isnan(mp_raw[i]))
            and (mp_raw[i] >= uni_tier)
        )
        spy_v63 = spy_63[i] if not np.isnan(spy_63[i]) else 0.0
        spy_v21 = spy_21[i] if not np.isnan(spy_21[i]) else 0.0
        w1 = sizing_rule(i, history, spy_v63, spy_v21, pr_raw, mp_raw, cur[i])
        uni_n = "t" if use_trans else "s"
        eng = engines[(uni_n, w1)]
        r = _portfolio_fwd_return(eng, i, w1, 1.0 - w1, vol_exp=vol_exp)
        w = _portfolio_weights(eng, i, w1, 1.0 - w1, vol_exp=vol_exp)
        out[rd] = r
        weights_history.append((rd, w))
        history.append(r)
    return pd.Series(out).sort_index(), weights_history


# ---------------------------------------------------------------------------
# Strategy 2 — ROBUST_STACK
# ---------------------------------------------------------------------------

def run_robust_stack(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """6-layer post-purge winner. Sizing: normal 0.50, full-boost 0.82."""
    pr_raw, mp_raw = _load_p46_proba()

    W_NORM, W_FULL = 0.50, 0.82
    BOOST_LB_M = 9
    BOOST_THR = 0.30
    SPY_FAST_THR = 0.12

    def sizing(i, hist, spy_v63, spy_v21, pr, mp, cur_i):
        if len(hist) >= BOOST_LB_M:
            cum_9 = float(np.prod([1 + h for h in hist[-BOOST_LB_M:]]) - 1)
        else:
            cum_9 = 0.05
        return W_FULL if (cum_9 > BOOST_THR or spy_v63 > SPY_FAST_THR) else W_NORM

    return _run_champion_loop(
        bundle, cfg_global, test_dates,
        stable_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"],
        trans_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY", "TLT", "AGG", "XLV", "XLF"],
        sig_gate=0.40, uni_tier=0.50,
        rank_w=[(42, 1), (63, 3), (126, 1)],
        fomc_pre=0, fomc_post=2, fomc_defer=3,
        w_choices=(W_NORM, W_FULL),
        sizing_rule=sizing, vol_exp=1.0,
        pr_raw=pr_raw, mp_raw=mp_raw,
    )


# ---------------------------------------------------------------------------
# Strategy 7 — ROBUST_VAR. Same as S2 but basket inverse-variance (exp=2).
# ---------------------------------------------------------------------------

def run_robust_var(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    pr_raw, mp_raw = _load_p46_proba()

    W_NORM, W_FULL = 0.50, 0.82
    BOOST_LB_M = 9
    BOOST_THR = 0.30
    SPY_FAST_THR = 0.12

    def sizing(i, hist, spy_v63, spy_v21, pr, mp, cur_i):
        if len(hist) >= BOOST_LB_M:
            cum_9 = float(np.prod([1 + h for h in hist[-BOOST_LB_M:]]) - 1)
        else:
            cum_9 = 0.05
        return W_FULL if (cum_9 > BOOST_THR or spy_v63 > SPY_FAST_THR) else W_NORM

    return _run_champion_loop(
        bundle, cfg_global, test_dates,
        stable_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"],
        trans_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY", "TLT", "AGG", "XLV", "XLF"],
        sig_gate=0.40, uni_tier=0.50,
        rank_w=[(42, 1), (63, 3), (126, 1)],
        fomc_pre=0, fomc_post=2, fomc_defer=3,
        w_choices=(W_NORM, W_FULL),
        sizing_rule=sizing, vol_exp=2.0,
        pr_raw=pr_raw, mp_raw=mp_raw,
    )


# ---------------------------------------------------------------------------
# Strategy 8 — P59_FULL_STACK. 10-layer control; 4-state sizing + FOMC (0,1,4).
# ---------------------------------------------------------------------------

def run_p59(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    pr_raw, mp_raw = _load_p46_proba()

    W_DD, W_NORM, W_WARM, W_FULL = 0.40, 0.62, 0.70, 0.82
    DD_LB_M, DD_THR = 3, -0.02
    WARM_LB_M, WARM_THR = 6, 0.25
    FULL_LB_M, FULL_THR = 9, 0.30
    SPY_WARM_THR, SPY_FULL_THR = 0.10, 0.12

    def cum(hist, k):
        if len(hist) >= k:
            return float(np.prod([1 + h for h in hist[-k:]]) - 1)
        return 0.05

    def sizing(i, hist, spy_v63, spy_v21, pr, mp, cur_i):
        cum_dd = cum(hist, DD_LB_M)
        cum_warm = cum(hist, WARM_LB_M)
        cum_full = cum(hist, FULL_LB_M)
        if cum_dd < DD_THR:
            return W_DD
        if (cum_full > FULL_THR) or (spy_v63 > SPY_FULL_THR):
            return W_FULL
        if (cum_warm > WARM_THR) or (spy_v21 > SPY_WARM_THR):
            return W_WARM
        return W_NORM

    return _run_champion_loop(
        bundle, cfg_global, test_dates,
        stable_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"],
        trans_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY", "TLT", "AGG", "XLV", "XLF"],
        sig_gate=0.40, uni_tier=0.50,
        rank_w=[(42, 1), (63, 3), (126, 1)],
        fomc_pre=0, fomc_post=1, fomc_defer=4,
        w_choices=(W_DD, W_NORM, W_WARM, W_FULL),
        sizing_rule=sizing, vol_exp=1.0,
        pr_raw=pr_raw, mp_raw=mp_raw,
    )


# ---------------------------------------------------------------------------
# Strategy 9 — P57_FRONTLOADED. P53 4-state + stagflation/high-conf/own-vol.
# ---------------------------------------------------------------------------

STAGFLATION_CLASS = 3  # regime_lg_hi_stagflation — see features/regime_labels.py

def run_p57(cfg_file, bundle, pred_reg, test_dates, cfg_global):
    """P57 reconstruction from BEST.md: P55 + high-conf-trans defend + own-vol.

    The champion script for P57 was never checked in; this implementation
    stacks the three overrides described in ``tests/autonomous/BEST.md`` on
    the P53 4-state sizing baseline.
    """
    pr_raw, mp_raw = _load_p46_proba()

    W_DD, W_NORM, W_WARM, W_FULL = 0.45, 0.62, 0.70, 0.78
    W_DEFEND = 0.45
    W_LOWVOL = 0.75
    W_HIGHVOL = 0.45
    DD_LB_M, DD_THR = 3, -0.02
    WARM_LB_M, WARM_THR = 6, 0.25
    FULL_LB_M, FULL_THR = 9, 0.30
    SPY_WARM_THR, SPY_FULL_THR = 0.10, 0.12
    HIGH_CONF_THR = 0.82
    VOL_WIN_M = 12
    VOL_LOW, VOL_HIGH = 0.12, 0.25

    def cum(hist, k):
        if len(hist) >= k:
            return float(np.prod([1 + h for h in hist[-k:]]) - 1)
        return 0.05

    cur_full = np.asarray(_cr(bundle.df).index)

    def sizing(i, hist, spy_v63, spy_v21, pr, mp, cur_i):
        # Stagflation defend — current regime (not predicted)
        if int(cur_i) == STAGFLATION_CLASS:
            return W_DEFEND
        # High-confidence transition defend
        if (
            (not np.isnan(mp[i]))
            and (mp[i] > HIGH_CONF_THR)
            and (pr[i] >= 0)
            and (pr[i] != cur_i)
        ):
            return W_DEFEND
        # P53-style 4-state
        cum_dd = cum(hist, DD_LB_M)
        cum_warm = cum(hist, WARM_LB_M)
        cum_full = cum(hist, FULL_LB_M)
        if cum_dd < DD_THR:
            base = W_DD
        elif (cum_full > FULL_THR) or (spy_v63 > SPY_FULL_THR):
            base = W_FULL
        elif (cum_warm > WARM_THR) or (spy_v21 > SPY_WARM_THR):
            base = W_WARM
        else:
            base = W_NORM
        # Own-vol regime override — annualised std of trailing 12m history
        if len(hist) >= VOL_WIN_M:
            rv = float(np.std(hist[-VOL_WIN_M:], ddof=1)) * np.sqrt(12)
            if rv < VOL_LOW:
                return max(base, W_LOWVOL)
            if rv > VOL_HIGH:
                return min(base, W_HIGHVOL)
        return base

    # sizing may return any float in a discrete set; pre-build engines
    # for every possible value.
    w_choices = (W_DD, W_NORM, W_WARM, W_FULL, W_DEFEND, W_LOWVOL, W_HIGHVOL)
    # dedupe while preserving numeric identity
    w_choices = tuple(sorted(set(w_choices)))

    # wrap sizing so it sees the cur array directly
    def sizing_wrapped(i, hist, spy_v63, spy_v21, pr, mp, cur_i):
        return sizing(i, hist, spy_v63, spy_v21, pr, mp, cur_full[i])

    return _run_champion_loop(
        bundle, cfg_global, test_dates,
        stable_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"],
        trans_uni=["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY", "TLT", "AGG", "XLV", "XLF"],
        sig_gate=0.40, uni_tier=0.50,
        rank_w=[(42, 1), (63, 3), (126, 1)],
        fomc_pre=0, fomc_post=1, fomc_defer=4,
        w_choices=w_choices,
        sizing_rule=sizing_wrapped, vol_exp=1.0,
        pr_raw=pr_raw, mp_raw=mp_raw,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

STRATEGY_DISPATCH = {
    "OPTIMIZED": run_optimized,
    "ROBUST_STACK": run_robust_stack,
    "DROPOVERLAP": run_dropoverlap,
    "T2_BALANCED": run_t2_balanced,
    "TREND_SIMPLE": run_trend_simple,
    "DUAL_MOMENTUM": run_dual_momentum,
    "ROBUST_VAR": run_robust_var,
    "P59_FULL_STACK": run_p59,
    "P57_FRONTLOADED": run_p57,
}
