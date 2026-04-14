"""Phase 48: measure P46 turnover and concentration vs baseline."""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from utils.base_test import _load, _STATE
from strategy.portfolio import PortfolioEngine
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
from features.regime_labels import current_regime as _cr

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]; TRANS = STABLE + ["TLT","AGG","XLV"]


def weights_per_month(which="p46"):
    """Return DataFrame of monthly weights. which in {'p46','baseline'}."""
    _load(); b = _STATE["bundle"]

    if which == "p46":
        with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
            pr, mp = pickle.load(f)
        cur = np.asarray(_cr(b.df).index)
        gated = pr.copy()
        w = (pr != cur) & (pr >= 0); lc = np.nan_to_num(mp, nan=0) < 0.40
        gated[w & lc] = cur[w & lc]
        cm = list(b.returns[63].columns); ranks = None
        for lb, wt in [(42,1),(63,3),(126,1)]:
            r = b.returns[lb][cm].rank(axis=1, method="average")
            ranks = r * wt if ranks is None else ranks + r * wt
        sig = ranks / 5

        def mk_eng(uni):
            cfg = copy.deepcopy(_STATE["cfg"])
            cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38,
                        "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4})
            shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
            nr = dict(b.returns); nr[63]=sig; shim.returns=nr
            return PortfolioEngine(shim, gated, cfg)

        eng_s = mk_eng(STABLE); eng_t = mk_eng(TRANS)
        td = _STATE["test_dates"]
        td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
        month_last = td_positions.groupby(td.to_period("M")).tail(1)
        fomc_idx = np.where(b.is_fomc_day)[0]
        event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=1)

        all_tickers = sorted(set(STABLE) | set(TRANS))
        rows = []; dates = []
        for rd, pos in month_last.items():
            i, _ = resolve_rebalance_index(int(pos), 4, event_mask, eng_s.n_days)
            use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
            eng = eng_t if use_t else eng_s
            top1, tk = eng.pick_at(i)
            w_row = {t: 0.0 for t in all_tickers}
            # SMA gate
            if eng.spy_dist[i] > eng.sma_buffer:
                w_row[eng.universe[top1]] += eng.top1_w
            else:
                w_row[eng.cash] += eng.top1_w
            sel = eng.atr_arr[i, tk]
            inv = 1.0 / np.where(sel > 0, sel, np.nan)
            if np.isnan(inv).all():
                wts = np.full(len(tk), 1.0 / len(tk))
            else:
                wts = inv / np.nansum(inv)
            for j, ti in enumerate(tk):
                w_row[eng.universe[int(ti)]] += wts[j] * eng.topk_w
            rows.append(w_row); dates.append(rd)
        return pd.DataFrame(rows, index=dates)

    else:
        # Baseline with canonical 8-universe
        cfg = _STATE["cfg"]
        eng = PortfolioEngine(b, _STATE["pred_reg"], cfg)
        td = _STATE["test_dates"]
        td_positions = pd.Series(eng.dates.get_indexer(td), index=td)
        month_last = td_positions.groupby(td.to_period("M")).tail(1)
        fomc_idx = np.where(b.is_fomc_day)[0]
        defer = int(cfg.get("fomc_defer_days", 3))
        pre = int(cfg.get("fomc_window_pre", 0)); post = int(cfg.get("fomc_window_after", 2))
        event_mask = fomc_window_mask(eng.n_days, fomc_idx, pre_days=pre, post_days=post)
        all_tickers = list(eng.universe)
        rows = []; dates = []
        for rd, pos in month_last.items():
            i, _ = resolve_rebalance_index(int(pos), defer, event_mask, eng.n_days)
            top1, tk = eng.pick_at(i)
            w_row = {t: 0.0 for t in all_tickers}
            if eng.spy_dist[i] > eng.sma_buffer:
                w_row[eng.universe[top1]] += eng.top1_w
            else:
                w_row[eng.cash] += eng.top1_w
            sel = eng.atr_arr[i, tk]
            inv = 1.0 / np.where(sel > 0, sel, np.nan)
            if np.isnan(inv).all():
                wts = np.full(len(tk), 1.0 / len(tk))
            else:
                wts = inv / np.nansum(inv)
            for j, ti in enumerate(tk):
                w_row[eng.universe[int(ti)]] += wts[j] * eng.topk_w
            rows.append(w_row); dates.append(rd)
        return pd.DataFrame(rows, index=dates)


def main():
    w_p46 = weights_per_month("p46")
    w_base = weights_per_month("baseline")

    # Turnover: sum of |delta weight| per month
    def turnover(w):
        return w.diff().abs().sum(axis=1).dropna()

    t_p46 = turnover(w_p46)
    t_base = turnover(w_base)

    print("Turnover (sum |d_w| per rebalance month):")
    print(f"  P46:      mean={t_p46.mean():.3f}  median={t_p46.median():.3f}  max={t_p46.max():.3f}")
    print(f"  baseline: mean={t_base.mean():.3f}  median={t_base.median():.3f}  max={t_base.max():.3f}")
    print(f"  ratio (P46/base): {t_p46.mean() / t_base.mean():.3f}")

    # Concentration: max weight per month
    conc_p46 = w_p46.max(axis=1)
    conc_base = w_base.max(axis=1)
    print("\nMax-single-ETF weight per month:")
    print(f"  P46:      mean={conc_p46.mean():.3f}  p95={conc_p46.quantile(0.95):.3f}  max={conc_p46.max():.3f}")
    print(f"  baseline: mean={conc_base.mean():.3f}  p95={conc_base.quantile(0.95):.3f}  max={conc_base.max():.3f}")

    # Number of distinct top-1 selections
    print(f"\nDistinct top-1 picks (P46): {w_p46.idxmax(axis=1).nunique()}")
    print(f"Distinct top-1 picks (base): {w_base.idxmax(axis=1).nunique()}")

    # Cost impact estimate: turnover * bps round-trip
    for bps in (5, 10, 20, 30):
        p46_cost = t_p46.mean() * (bps / 1e4)
        base_cost = t_base.mean() * (bps / 1e4)
        p46_ann = (1 - p46_cost) ** 12 - 1
        print(f"  @ {bps}bps cost: P46 monthly drag {p46_cost*100:.3f}pp → annual ~{(1-p46_cost)**12*100 - 100:.2f}pp")

    # Log summary
    log_path = HERE.parent / "LOG.md"
    import datetime as dt
    ts = dt.datetime.now().isoformat(timespec="seconds")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n### phase48_turnover_p46  {ts}\n")
        f.write(f"- P46 mean turnover: {t_p46.mean():.3f} per month (|Δw| sum)\n")
        f.write(f"- Baseline mean turnover: {t_base.mean():.3f} per month\n")
        f.write(f"- Ratio P46/baseline: {t_p46.mean()/t_base.mean():.3f}\n")
        f.write(f"- P46 mean max-single-ETF weight: {conc_p46.mean():.3f}\n")
        f.write(f"- Baseline mean max-single-ETF weight: {conc_base.mean():.3f}\n")


if __name__ == "__main__":
    main()
