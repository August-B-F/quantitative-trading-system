"""Phase 40: stable universe variants on champion stack."""
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

PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total


def run_tier(stable_uni, trans_uni, sig, uni_tier=0.50):
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
    eng_s = mk_eng(stable_uni); eng_t = mk_eng(trans_uni)
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
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=uni_tier)
        rets.append(ret_at(eng_t if use_t else eng_s, i))
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    BASE_STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
    BASE_TRANS  = BASE_STABLE + ["TLT","AGG","XLV"]
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase40_stable_uni_variants  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P40.00_ref",            BASE_STABLE, BASE_TRANS),
        ("P40.01_stable_+VGT",    BASE_STABLE + ["VGT"], BASE_STABLE + ["VGT","TLT","AGG","XLV"]),
        ("P40.02_stable_+XLK",    BASE_STABLE + ["XLK"], BASE_STABLE + ["XLK","TLT","AGG","XLV"]),
        ("P40.03_stable_+XLV",    BASE_STABLE + ["XLV"], BASE_STABLE + ["XLV","TLT","AGG"]),
        ("P40.04_stable_-SOXX",   [t for t in BASE_STABLE if t!="SOXX"], [t for t in BASE_TRANS if t!="SOXX"]),
        ("P40.05_stable_-IGV",    [t for t in BASE_STABLE if t!="IGV"], [t for t in BASE_TRANS if t!="IGV"]),
        ("P40.06_stable_-XLE",    [t for t in BASE_STABLE if t!="XLE"], [t for t in BASE_TRANS if t!="XLE"]),
        ("P40.07_stable_-GLD",    [t for t in BASE_STABLE if t!="GLD"], [t for t in BASE_TRANS if t!="GLD"]),
        ("P40.08_stable_-QQQ",    [t for t in BASE_STABLE if t!="QQQ"], [t for t in BASE_TRANS if t!="QQQ"]),
        ("P40.09_stable_+IWM",    BASE_STABLE + ["IWM"], BASE_STABLE + ["IWM","TLT","AGG","XLV"]),
        ("P40.10_stable_+XLI",    BASE_STABLE + ["XLI"], BASE_STABLE + ["XLI","TLT","AGG","XLV"]),
        ("P40.11_stable_+DBC",    BASE_STABLE + ["DBC"], BASE_STABLE + ["DBC","TLT","AGG","XLV"]),
    ]
    for name, su, tu in experiments:
        try: s = run_tier(su, tu, sig)
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
