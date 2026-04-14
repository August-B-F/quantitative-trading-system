"""Phase 36: final round of tweaks to try."""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
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

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS  = STABLE + ["TLT","AGG","XLV"]
PROBA = HERE.parent / "cache" / "pred_proba.pkl"
ROOT = Path(__file__).resolve().parents[3]


def rankagg_custom(signal_frames, weights):
    """Aggregate arbitrary rank signals. First frame defines the column set;
    subsequent frames reindexed to it (missing cols fill w/ NaN)."""
    cm = list(signal_frames[0].columns)
    total = sum(weights); ranks = None
    for r, w in zip(signal_frames, weights):
        rr = r.reindex(columns=cm)
        ranked = rr.rank(axis=1, method="average")
        ranks = ranked*w if ranks is None else ranks + ranked*w
    return ranks/total


def run_full(sig):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]

    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
    eng_s = mk_eng(STABLE); eng_t = mk_eng(TRANS)
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
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        rets.append(ret_at(eng_t if use_t else eng_s, i))
    return compute_stats(np.array(rets))


def main():
    _load(); b = _STATE["bundle"]

    # Load 12_1_mom (classic Asness momentum)
    p12 = pd.read_parquet(ROOT / "data/features/price/returns_12_1_mom.parquet").reindex(b.dates)
    # rel strength 63d
    rs63 = pd.read_parquet(ROOT / "data/features/price/relative_strength_63d.parquet").reindex(b.dates)
    # voladj mom 63d
    va63 = pd.read_parquet(ROOT / "data/features/price/quality_voladj_mom_63d.parquet").reindex(b.dates)

    r42 = b.returns[42]; r63 = b.returns[63]; r126 = b.returns[126]
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase36_final_tweaks  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P36.00_ref",                  rankagg_custom([r42, r63, r126], [1, 3, 1])),
        ("P36.01_+12_1mom",             rankagg_custom([r42, r63, r126, p12], [1, 3, 1, 0.5])),
        ("P36.02_+12_1mom_1",           rankagg_custom([r42, r63, r126, p12], [1, 3, 1, 1])),
        ("P36.03_+rel_str_63",          rankagg_custom([r42, r63, r126, rs63], [1, 3, 1, 0.5])),
        ("P36.04_+voladj_63",           rankagg_custom([r42, r63, r126, va63], [1, 3, 1, 0.5])),
        ("P36.05_+voladj_1",            rankagg_custom([r42, r63, r126, va63], [1, 3, 1, 1])),
        ("P36.06_63_3_126_2",           rankagg_custom([r42, r63, r126], [1, 3, 2])),
        ("P36.07_63_3_126_1p5",         rankagg_custom([r42, r63, r126], [1, 3, 1.5])),
        ("P36.08_42_0p5",               rankagg_custom([r42, r63, r126], [0.5, 3, 1])),
        ("P36.09_42_1p5_63_3_126_1",    rankagg_custom([r42, r63, r126], [1.5, 3, 1])),
    ]

    for name, sig in experiments:
        try: s = run_full(sig)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
