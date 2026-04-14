"""Phase 14: add 252d horizon, check 252 inclusion. Plus Monte Carlo bootstrap
of champion vs baseline monthly return series to validate the edge statistically."""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def gated(thr=0.40):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<thr
    out[w&lc]=cur[w&lc]; return out


def load_extra_returns(n_list):
    """Load additional returns_{n}d parquet files into bundle.returns dict if missing."""
    _load(); b = _STATE["bundle"]
    ROOT = Path(__file__).resolve().parents[3]
    for n in n_list:
        if n in b.returns: continue
        p = ROOT / f"data/features/price/returns_{n}d.parquet"
        if p.exists():
            b.returns[n] = pd.read_parquet(p).reindex(b.dates)


def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm = None; total = sum(w for _,w in weights); ranks = None
    for lb, w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total

def run_sig(sig, ov, pred):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats, run_backtest(eng, _STATE["test_dates"], cfg).monthly_returns


def run_baseline_monthly():
    _load(); cfg = _STATE["cfg"]
    eng = PortfolioEngine(_STATE["bundle"], _STATE["pred_reg"], cfg)
    res = run_backtest(eng, _STATE["test_dates"], cfg)
    return res.stats, res.monthly_returns


def main():
    load_extra_returns([252])
    g = gated(0.40)
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase14_long_horizon_and_bootstrap  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    _load()
    # Test variants including 252d
    grids = [
        ("V1_42_63_126_252", [(42,1),(63,3),(126,1),(252,0.5)]),
        ("V2_42_63_126_252_eq", [(42,1),(63,3),(126,1),(252,1)]),
        ("V3_63_126_252", [(63,3),(126,1),(252,1)]),
        ("V4_42_63_126_252_heavy252", [(42,1),(63,3),(126,1),(252,2)]),
    ]
    for name, w in grids:
        try: sig = rankagg(w); s,_ = run_sig(sig, CHAMP, g)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")

    # Monte Carlo bootstrap: are champ monthly returns significantly different?
    sig_champ = rankagg([(42,1),(63,3),(126,1)])
    s_c, m_c = run_sig(sig_champ, CHAMP, g)
    s_b, m_b = run_baseline_monthly()
    # Align by index
    common = m_c.index.intersection(m_b.index)
    ret_c = m_c.reindex(common).values
    ret_b = m_b.reindex(common).values
    diff = ret_c - ret_b
    print(f"\nMonthly return diff: mean={diff.mean()*100:.3f}pp/mo  std={diff.std()*100:.3f}pp/mo  n={len(diff)}")
    t_stat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
    print(f"t-stat (paired): {t_stat:.2f}")

    # Bootstrap 5000x
    rng = np.random.default_rng(42)
    n_months = len(diff)
    bs_means = []
    for _ in range(5000):
        idx = rng.integers(0, n_months, n_months)
        bs_means.append(diff[idx].mean())
    bs_means = np.array(bs_means)
    pct_pos = (bs_means > 0).mean()
    ci_lo, ci_hi = np.percentile(bs_means, [2.5, 97.5])
    print(f"Bootstrap: P(mean diff > 0) = {pct_pos*100:.1f}%   95% CI = [{ci_lo*100:.3f}, {ci_hi*100:.3f}] pp/mo")

    lines.append("\n**Monte Carlo bootstrap (paired monthly returns champion − baseline)**\n")
    lines.append(f"- n={n_months} months")
    lines.append(f"- mean diff = {diff.mean()*100:.3f}pp/mo ({((1+diff.mean())**12-1)*100:+.2f}pp/yr)")
    lines.append(f"- paired t-stat = {t_stat:.2f}")
    lines.append(f"- bootstrap P(mean>0) = {pct_pos*100:.1f}%")
    lines.append(f"- 95% CI mean diff = [{ci_lo*100:+.3f}, {ci_hi*100:+.3f}] pp/mo")

    with open(log_path,"a",encoding="utf-8") as f:
        f.write("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
