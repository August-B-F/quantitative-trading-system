"""Phase 29: intra-month drawdown stop.

When the portfolio position has drawn down by X% from its max since last rebalance,
forcibly exit to SHY for the remainder of the month. Uses daily prices.

We simulate by computing daily equity path within each month from the held weights
and checking vs running max.
"""
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
TRANS = STABLE + ["TLT","AGG","XLV"]
PROBA = HERE.parent / "cache" / "pred_proba.pkl"
ROOT = Path(__file__).resolve().parents[3]

def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total


def load_prices():
    _load(); b = _STATE["bundle"]
    needed = set(STABLE) | set(TRANS) | {"SPY"}
    px = {}
    for t in needed:
        p = ROOT / f"data/clean/prices/{t}.parquet"
        if p.exists():
            px[t] = pd.read_parquet(p)["adj_close"].reindex(b.dates).ffill()
    return pd.DataFrame(px)


def run_with_stop(stable_uni, trans_uni, sig, stop_thresh=0.08, uni_tier=0.50, sig_gate=0.40):
    """stop_thresh: intra-month drawdown % that triggers SHY exit."""
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<sig_gate
    gated[w&lc]=cur[w&lc]

    px = load_prices()

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

    month_ends = list(month_last.items())
    rets = []
    for k, (rd, pos) in enumerate(month_ends):
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=uni_tier)
        eng = eng_t if use_t else eng_s
        t1, tk = eng.pick_at(i)
        # build weights
        w_vec = np.zeros(len(eng.universe))
        if eng.spy_dist[i] > eng.sma_buffer:
            w_vec[t1] += eng.top1_w
        else:
            cash_i = eng.universe.index(eng.cash)
            w_vec[cash_i] += eng.top1_w
        sel_atr = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            wts = np.full(len(tk), 1.0/len(tk))
        else:
            wts = inv / np.nansum(inv)
        for j, ti in enumerate(tk):
            w_vec[int(ti)] += wts[j] * eng.topk_w

        # Simulate intra-month daily path
        end_i = int(month_ends[k+1][1]) if k+1 < len(month_ends) else i + 21
        end_i = min(end_i, len(b.dates) - 1)
        if end_i <= i:
            rets.append(0.0); continue

        # holdings -> daily return
        eq = 1.0; peak = 1.0; stopped = False
        stop_day = None
        for day in range(i+1, end_i+1):
            daily_r = 0.0
            for j, tk_name in enumerate(eng.universe):
                wj = w_vec[j]
                if wj <= 0: continue
                if tk_name not in px.columns: continue
                p_prev = px[tk_name].iloc[day-1]; p_now = px[tk_name].iloc[day]
                if np.isnan(p_prev) or np.isnan(p_now) or p_prev == 0: continue
                daily_r += wj * (p_now/p_prev - 1)
            eq *= (1 + daily_r)
            if eq > peak: peak = eq
            if (eq / peak - 1) < -stop_thresh and not stopped:
                stopped = True; stop_day = day
                break

        if stopped:
            # From stop_day onwards, park in SHY (earn SHY daily returns)
            shy = px.get("SHY")
            if shy is not None:
                for day in range(stop_day+1, end_i+1):
                    p_prev = shy.iloc[day-1]; p_now = shy.iloc[day]
                    if np.isnan(p_prev) or np.isnan(p_now) or p_prev == 0: continue
                    eq *= (p_now / p_prev)
            rets.append(eq - 1.0)
        else:
            rets.append(eq - 1.0)
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase29_intramonth_stop  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    for stop in (0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20):
        try: s = run_with_stop(STABLE, TRANS, sig, stop_thresh=stop)
        except Exception as e: s = {"error": str(e)}
        name = f"P29.01_stop{int(stop*100)}"
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
