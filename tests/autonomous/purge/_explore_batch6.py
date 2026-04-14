"""Round-6:
H27: acceleration signal (mom of mom) added to rank-agg
H28: static bond/cash sleeve on top (80% Robust-VAR + 20% bond)
H29: signal short-circuit — if rank-gap between top1 and top6 is small, go to cash
H30: de-weight during bear markets (SPY below SMA200)
H31: ATR-scaled top1 weight (inversely proportional to top1's own vol)
"""
from __future__ import annotations
import sys, pickle, copy, types, warnings
from pathlib import Path
import numpy as np, pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

STABLE=["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS=STABLE+["TLT","AGG","XLV","XLF"]
W_NORM=0.50; W_FULL=0.82
BOOST_LB_M=9; BOOST_THR=0.30; SPY_FAST_LB=63; SPY_FAST_THR=0.12
FOMC_PRE,FOMC_POST,FOMC_DEFER=0,2,3
P_EXP=2.0


def build_sig_standard():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def build_sig_accel(alpha):
    """Base rank-agg + alpha * acceleration proxy (rank42 - rank126)."""
    b=_STATE["bundle"]
    cm = list(b.returns[63].columns)
    base = build_sig_standard()
    r42 = b.returns[42][cm].rank(axis=1, method="average")
    r126 = b.returns[126][cm].rank(axis=1, method="average")
    accel = (r42 - r126) / len(cm)  # normalized
    return base + alpha * accel


def run(sig_variant="standard", accel_alpha=0.5,
        bond_overlay=None, bond_w=0.20,
        cash_on_bear=False,
        atr_scaled_top1=False, atr_scale=0.5,
        short_circuit=False, sc_min_gap=0.15):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    if sig_variant == "accel":
        sig = build_sig_accel(accel_alpha)
    else:
        sig = build_sig_standard()
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values
    fwd21_arr = b.fwd21

    def mk(uni,w1):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    engs={}
    ws = {W_NORM, W_FULL}
    if atr_scaled_top1:
        for w in np.arange(0.35, 0.85, 0.05):
            ws.add(round(float(w), 2))
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in ws:
            engs[(uni_n,w1)] = mk(uni,w1)
    td=_STATE["test_dates"]; eng0=engs[("s",W_NORM)]
    ps=pd.Series(eng0.dates.get_indexer(td),index=td)
    ml=ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    # Bond overlay series
    if bond_overlay:
        bond_col = b.returns[21][bond_overlay]  # 21d return for bond
        bond_fwd21 = bond_col.values

    def ret_at(eng,i):
        t1,tk=eng.pick_at(i)
        r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk]
        v=np.where(sel>0,sel,np.nan)
        w=1.0/(v**P_EXP)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk, t1, tk

    rets=[]; hist=[]; dts=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (c9>BOOST_THR) or (sv>SPY_FAST_THR)
        w1 = W_FULL if boost else W_NORM

        if cash_on_bear:
            # Use engine's spy_dist gate
            pass  # already in pick

        uni_n="t" if use_t else "s"
        eng_ref = engs[(uni_n, w1)]

        if atr_scaled_top1:
            # Scale top1 weight based on top1 ETF's ATR
            t1_idx, _ = eng_ref.pick_at(i)
            top1_atr = eng_ref.atr_arr[i, t1_idx]
            base_atr = 0.015  # empirical midpoint
            if not np.isnan(top1_atr) and top1_atr > 0:
                scale = base_atr / top1_atr
                w1_adj = round(max(0.35, min(0.80, 0.50 * (0.5 + 0.5*scale))), 2)
                if (uni_n, w1_adj) not in engs:
                    engs[(uni_n, w1_adj)] = mk(STABLE if uni_n=="s" else TRANS, w1_adj)
                eng_ref = engs[(uni_n, w1_adj)]

        r, _, _ = ret_at(eng_ref, i)

        if short_circuit:
            uni_now = STABLE if uni_n == "s" else TRANS
            sv_row = sig.iloc[i].reindex(uni_now).values
            ranks = pd.Series(sv_row).rank(method="average").values
            if not np.isnan(ranks).all():
                r1_rank = np.nanmax(ranks)
                r_last = np.nanmin(ranks)
                gap = (r1_rank - r_last) / len(uni_now)
                if gap < sc_min_gap:
                    r = eng_ref.cash_fwd[i]

        if bond_overlay:
            r = (1 - bond_w) * r + bond_w * bond_fwd21[i]

        hist.append(r); rets.append(r); dts.append(rd)
    return pd.Series(rets,index=pd.Index(dts)).dropna()


def per_half(ser):
    sA=ser[ser.index.map(lambda d:d.year<2018)]
    sB=ser[ser.index.map(lambda d:d.year>=2018)]
    return compute_stats(ser.values), compute_stats(sA.values), compute_stats(sB.values)


def show(label, ser, base):
    f,a,b_=per_half(ser)
    f0,a0,b0=base
    dSh=f['sharpe']-f0['sharpe']; dA=a['sharpe']-a0['sharpe']; dB=b_['sharpe']-b0['sharpe']
    tag=""
    if dA>=-0.02 and dB>=-0.02 and dSh>=0.04: tag="  PASS"
    elif dA>=-0.02 and dB>=-0.02 and dSh>=0:  tag="  +"
    print(f"{label:<44}  {f['cagr']*100:>6.2f}%  Sh {f['sharpe']:.3f}  A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  dSh {dSh:+.3f}{tag}")


def main():
    base = per_half(run())
    print(f"baseline (Robust-VAR): CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()

    print("=== H27: acceleration signal ===")
    for a in [0.2, 0.5, 1.0, 2.0]:
        show(f"accel alpha={a}", run(sig_variant="accel", accel_alpha=a), base)

    print()
    print("=== H28: bond overlay (80% strategy + 20% bond) ===")
    for bond in ["TLT","AGG","SHY"]:
        for bw in [0.10, 0.15, 0.20, 0.25]:
            show(f"overlay {bond} w={bw}", run(bond_overlay=bond, bond_w=bw), base)

    print()
    print("=== H29: short-circuit to cash on low rank spread ===")
    for mg in [0.10, 0.15, 0.20, 0.25]:
        show(f"short_circuit gap<{mg}", run(short_circuit=True, sc_min_gap=mg), base)

    print()
    print("=== H31: ATR-scaled top1 weight ===")
    show("atr_scaled_top1", run(atr_scaled_top1=True), base)


if __name__ == "__main__":
    main()
