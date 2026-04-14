"""Generic layer-aware runner for the OVERFITTING PURGE PROTOCOL.

Supports toggling any of P59's 10 layers on/off, plus per-layer parameter
overrides. Used by TEST1-TEST6 scripts.
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

CANONICAL_UNI = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
DROP_OVERLAP_UNI = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
TRANS_ADD = ["TLT", "AGG", "XLV", "XLF"]

# Caches (loaded once per process)
_CACHE = {}


def _load_all():
    if "loaded" in _CACHE:
        return _CACHE
    _load()
    b = _STATE["bundle"]
    # Canonical CORE-50 classifier predictions
    with open(HERE.parent / "cache" / "pred_proba.pkl", "rb") as f:
        pr_core, mp_core = pickle.load(f)
    # CORE+extras (P46) classifier predictions
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr_ext, mp_ext = pickle.load(f)
    cur_reg = np.asarray(_cr(b.df).index)
    _CACHE.update(dict(
        b=b, pr_core=pr_core, mp_core=mp_core,
        pr_ext=pr_ext, mp_ext=mp_ext, cur_reg=cur_reg,
        spy_63=b.returns[63]["SPY"].values,
        spy_21=b.returns[21]["SPY"].values,
        loaded=True,
    ))
    return _CACHE


def rank_agg_signal():
    _load_all()
    b = _CACHE["b"]
    cm = None; ranks = None
    for lb, w in [(42, 1), (63, 3), (126, 1)]:
        r = b.returns[lb]
        if cm is None:
            cm = list(r.columns)
        else:
            r = r[cm]
        ranked = r.rank(axis=1, method="average") * w
        ranks = ranked if ranks is None else ranks + ranked
    return ranks / 5.0


def make_engine(bundle, pred_reg, universe, top1, top3,
                fomc_pre, fomc_post, fomc_def, sig_override):
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({
        "universe": universe,
        "top1_weight": top1,
        "top3_weight": top3,
        "fomc_window_pre": fomc_pre,
        "fomc_window_after": fomc_post,
        "fomc_defer_days": fomc_def,
    })
    shim = types.SimpleNamespace(**{k: getattr(bundle, k) for k in (
        "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
    new_returns = dict(bundle.returns)
    if sig_override is not None:
        new_returns[cfg["lookback_stable"]] = sig_override
    shim.returns = new_returns
    return PortfolioEngine(shim, pred_reg, cfg)


def default_config():
    """All 10 layers ON. P59 full-stack configuration."""
    return dict(
        L1=True, L2=True, L3=True, L4=True, L5=True, L6=True, L7=True,
        L8=True, L9=True, L10=True,
        # Parameters (used when layer is ON)
        L2_top1=0.62,
        L3_gate=0.40,
        L4_weights=[(42, 1), (63, 3), (126, 1)],
        L5_tier=0.50,
        L7_fomc=(0, 1, 4),
        L8_dd_lb=3, L8_dd_thr=-0.02, L8_wdd=0.40,
        L9_boost_lb=9, L9_boost_thr=0.30, L9_spy_lb=63, L9_spy_thr=0.12, L9_wfull=0.82,
        L10_warm_lb=6, L10_warm_thr=0.25, L10_spy_lb=21, L10_spy_thr=0.10, L10_wwarm=0.70,
    )


def canonical_config():
    """All 10 layers OFF — canonical baseline."""
    cfg = default_config()
    for k in [f"L{i}" for i in range(1, 11)]:
        cfg[k] = False
    return cfg


def run(cfg):
    """Run a P59-ish backtest with the given layer config. Returns (stats, monthly_returns, dates)."""
    cache = _load_all()
    b = cache["b"]
    spy_21 = cache["spy_21"]

    # Layer L6: choose classifier predictions
    if cfg["L6"]:
        pr_raw = cache["pr_ext"]; mp_raw = cache["mp_ext"]
    else:
        pr_raw = cache["pr_core"]; mp_raw = cache["mp_core"]

    # Layer L3: signal-level classifier proba gate
    cur = cache["cur_reg"]
    gated = pr_raw.copy()
    if cfg["L3"]:
        gate_thr = cfg.get("L3_gate", 0.40)
        want = (pr_raw != cur) & (pr_raw >= 0)
        low = np.nan_to_num(mp_raw, nan=0.0) < gate_thr
        gated[want & low] = cur[want & low]

    # Layer L4: momentum signal
    if cfg["L4"]:
        weights = cfg.get("L4_weights", [(42, 1), (63, 3), (126, 1)])
        cm = list(b.returns[63].columns)
        ranks = None
        total = sum(w for _, w in weights)
        for lb, w in weights:
            r = b.returns[lb][cm]
            ranked = r.rank(axis=1, method="average") * w
            ranks = ranked if ranks is None else ranks + ranked
        sig_override = ranks / total
    else:
        sig_override = None  # use bundle.returns[63] as-is (canonical)

    # Layer L1: universe (stable side)
    stable_uni = DROP_OVERLAP_UNI if cfg["L1"] else CANONICAL_UNI
    # Layer L5: transition universe
    if cfg["L5"]:
        trans_uni = stable_uni + TRANS_ADD
    else:
        trans_uni = stable_uni

    # Layer L7: FOMC window params
    if cfg["L7"]:
        fomc_pre, fomc_post, fomc_def = cfg.get("L7_fomc", (0, 1, 4))
    else:
        fomc_pre, fomc_post, fomc_def = 0, 2, 3  # canonical

    # Layer L2: top1 split
    if cfg["L2"]:
        w_norm = cfg.get("L2_top1", 0.62)
    else:
        w_norm = 0.50

    # Sizing weights used by L8/L9/L10
    w_dd = cfg.get("L8_wdd", 0.40)
    w_full = cfg.get("L9_wfull", 0.82)
    w_warm = cfg.get("L10_wwarm", 0.70)
    # Engines at all required weights
    weights_set = {w_norm}
    if cfg["L8"]: weights_set.add(w_dd)
    if cfg["L9"]: weights_set.add(w_full)
    if cfg["L10"]: weights_set.add(w_warm)

    def mk(uni, w1):
        return make_engine(b, gated, uni, w1, 1 - w1, fomc_pre, fomc_post, fomc_def, sig_override)

    engines = {}
    for uni_n, uni in [("s", stable_uni), ("t", trans_uni)]:
        for w1 in weights_set:
            engines[(uni_n, w1)] = mk(uni, w1)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engines[("s", w_norm)].dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    n_days = engines[("s", w_norm)].n_days
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=fomc_pre, post_days=fomc_post)

    # Layer L8/L9/L10 params
    dd_lb = cfg.get("L8_dd_lb", 3)
    dd_thr = cfg.get("L8_dd_thr", -0.02)
    boost_lb = cfg.get("L9_boost_lb", 9)
    boost_thr = cfg.get("L9_boost_thr", 0.30)
    spy_full_lb = cfg.get("L9_spy_lb", 63)
    spy_full_thr = cfg.get("L9_spy_thr", 0.12)
    warm_lb = cfg.get("L10_warm_lb", 6)
    warm_thr = cfg.get("L10_warm_thr", 0.25)
    spy_warm_lb = cfg.get("L10_spy_lb", 21)
    spy_warm_thr = cfg.get("L10_spy_thr", 0.10)

    spy_full_series = b.returns[spy_full_lb]["SPY"].values if spy_full_lb in b.returns else cache["spy_63"]
    spy_warm_series = b.returns[spy_warm_lb]["SPY"].values if spy_warm_lb in b.returns else cache["spy_21"]

    def ret_at(eng, i):
        t1, tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel > 0, sel, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv)
            rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []
    history = []
    dates_out = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), fomc_def, event_mask, n_days)

        # Layer L5: regime-conditional trans universe trigger
        if cfg["L5"]:
            tier = cfg.get("L5_tier", 0.50)
            use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and \
                        (not np.isnan(mp_raw[i])) and (mp_raw[i] >= tier)
        else:
            use_trans = False

        # Compute state variables
        if cfg["L8"]:
            if len(history) >= dd_lb:
                cum_dd = np.prod([1 + h for h in history[-dd_lb:]]) - 1
            else:
                cum_dd = 0.05
        else:
            cum_dd = 1.0  # never triggers
        if cfg["L9"]:
            if len(history) >= boost_lb:
                cum_full = np.prod([1 + h for h in history[-boost_lb:]]) - 1
            else:
                cum_full = 0.05
        else:
            cum_full = -1.0  # never triggers
        if cfg["L10"]:
            if len(history) >= warm_lb:
                cum_warm = np.prod([1 + h for h in history[-warm_lb:]]) - 1
            else:
                cum_warm = 0.05
        else:
            cum_warm = -1.0
        spy_v63 = spy_full_series[i] if not np.isnan(spy_full_series[i]) else -1.0
        spy_v21 = spy_warm_series[i] if not np.isnan(spy_warm_series[i]) else -1.0

        # Sizing logic
        if cfg["L8"] and cum_dd < dd_thr:
            w1 = w_dd
        elif cfg["L9"] and ((cum_full > boost_thr) or (spy_v63 > spy_full_thr)):
            w1 = w_full
        elif cfg["L10"] and ((cum_warm > warm_thr) or (spy_v21 > spy_warm_thr)):
            w1 = w_warm
        else:
            w1 = w_norm

        uni_n = "t" if use_trans else "s"
        r = ret_at(engines[(uni_n, w1)], i)
        history.append(r)
        rets.append(r)
        dates_out.append(rd)

    stats = compute_stats(np.array(rets))
    return stats, pd.Series(rets, index=dates_out)


# Convenience for tests
def fmt_stats(s):
    return f"CAGR={s['cagr']*100:6.2f}%  Sharpe={s['sharpe']:.2f}  MaxDD={s['max_dd']*100:.2f}%"


def edges_by_half(monthly_strategy, monthly_base):
    df = pd.DataFrame({"s": monthly_strategy, "b": monthly_base}).dropna()
    df["half"] = np.where(df.index.year < 2018, "A", "B")
    out = {}
    for half in ("A", "B"):
        sub = df[df["half"] == half]
        if len(sub) < 2:
            out[half] = dict(n=0, mean_edge=0, sharpe=0, ann=0, t=0)
            continue
        edge = (sub["s"] - sub["b"]).values
        s_stats = compute_stats(sub["s"].values)
        ann = ((1 + edge.mean()) ** 12 - 1) * 100
        t = float(edge.mean() / (edge.std(ddof=1) / np.sqrt(len(edge))))
        out[half] = dict(n=len(sub), mean_edge=edge.mean(), ann=ann, t=t,
                          cagr=s_stats["cagr"] * 100, sharpe=s_stats["sharpe"])
    return out
