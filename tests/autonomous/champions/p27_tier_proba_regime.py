"""SUPERSEDED by champions/p42_champion.py on 2026-04-13 16:30 local. Kept for history.

Original champion was P27 (tier-proba50 regime-uni) as of 2026-04-13 16:15 local.

Full stack:
  1. Universe: drop VGT and XLK (6-ETF dropoverlap for stable regime)
  2. Two-tier regime-conditional universe:
     - Stable regime: 6-ETF [SOXX, QQQ, IGV, XLE, GLD, SHY]
     - Transition regime (predicted != current AND max_proba >= 0.50):
       add TLT, AGG, XLV → 9-ETF universe
     - Low-confidence transition (< 0.50): stay in stable universe
  3. 62/38 top-1/top-k split
  4. Signal-level classifier gate at 0.40 (switches to 21d ONLY when proba>=0.40)
  5. Stable momentum signal: rank aggregation across (42d:1, 63d:3, 126d:1)

Stats: CAGR 27.77% / Sharpe 1.75 / MaxDD -12.66%
vs baseline 23.61/1.50/-12.94: +4.16pp / +0.25 / +0.28pp
Post 50% haircut: +2.08pp CAGR.

Sub-period all-win:
  2010-15: 19.12/1.53/-7.88 vs 13.74/1.18/-10.11
  2016-20: 22.72/1.38/-12.66 vs 20.54/1.24/-12.94
  2021-26: 43.15/2.36/-5.12 vs 38.37/2.06/-10.22
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import _load, _STATE, fmt  # noqa
from strategy.portfolio import PortfolioEngine  # noqa
from backtest.engine import compute_stats  # noqa
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa
from features.regime_labels import current_regime as _cr  # noqa

STABLE_UNI = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS_UNI  = STABLE_UNI + ["TLT","AGG","XLV"]
SIG_GATE = 0.40
UNI_TIER = 0.50
RANK_W = [(42,1),(63,3),(126,1)]
SPLIT = (0.62, 0.38)


def build_rank_signal():
    _load(); b = _STATE["bundle"]
    cm=None; ranks=None; total=sum(w for _,w in RANK_W)
    for lb,w in RANK_W:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1,method="average")*w
        ranks = ranked if ranks is None else ranks + ranked
    return ranks/total


def build_gated_pred():
    with open(HERE.parent/"cache"/"pred_proba.pkl","rb") as f: pr, mp = pickle.load(f)
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<SIG_GATE
    out[w&lc]=cur[w&lc]
    return out, pr, mp, cur


def run_champion():
    _load(); b = _STATE["bundle"]
    sig = build_rank_signal()
    gated, pr_raw, mp_raw, cur = build_gated_pred()
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":SPLIT[0],"top3_weight":SPLIT[1]})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
    eng_s = mk_eng(STABLE_UNI); eng_t = mk_eng(TRANS_UNI)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=2)
    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: w=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i]>=0) and \
                    (not np.isnan(mp_raw[i])) and (mp_raw[i] >= UNI_TIER)
        rets.append(ret_at(eng_t if use_trans else eng_s, i))
    return compute_stats(np.array(rets))


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P27 tier-proba50 regime-uni")
    print(fmt(s))
