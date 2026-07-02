"""The permanent baseline stable — generates results/BASELINES.md + .json.

Runs every baseline and the two-sleeve candidate through the daily
compounded-ledger engine (src/backtest/ledger.py, CONSTITUTION rule 5)
at 10 bps per side with SHV as the cash sleeve, over two windows:
2005-01-01..latest and 2018-01-01..latest.

Baselines:
    spy_buy_hold     buy-and-hold SPY
    60_40            60% SPY / 40% AGG, month-end rebalance
    equal_weight_8   legacy 8-ETF universe, equal weight monthly (reference)
    gem              Antonacci GEM standalone (12-1, SPY/EFA vs SHV, else AGG)
    spy_sma200       SPY when close > 200d SMA at the decision date else SHY,
                     month-end checks (the honest version of live S5)
    inverse_vol      inverse-63d-vol across the TSMOM universe, monthly
    tsmom            TSMOM sleeve alone (MOP 2012, long-only)
    two_sleeve       the candidate: 0.6*TSMOM + 0.4*GEM, 10% vol target

These numbers are the permanent promotion bars per CONSTITUTION.md rule
4. Regenerate only by re-running this script; never edit the outputs by
hand.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402
from strategy.sleeves import (  # noqa: E402
    CASH,
    GEM_FALLBACK,
    GEM_RISK_ASSETS,
    TRADING_DAYS_PER_YEAR,
    TSMOM_UNIVERSE,
    build_schedule,
    gem_weights,
    tsmom_weights,
    two_sleeve_weights,
)

log = logging.getLogger("baselines")

COST_BPS = 10.0
WINDOWS = [("2005-01-01", None), ("2018-01-01", None)]
LEGACY_8 = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
ALL_TICKERS = sorted(
    set(TSMOM_UNIVERSE) | set(LEGACY_8) | set(GEM_RISK_ASSETS)
    | {CASH, GEM_FALLBACK, "SPY", "SHY"}
)

MD_PATH = ROOT / "results" / "BASELINES.md"
JSON_PATH = ROOT / "results" / "baselines.json"


# ---------- weight functions for the simple baselines ------------------------

def _const_weights(weights: dict[str, float]):
    def fn(prices: dict, as_of: pd.Timestamp) -> dict[str, float]:
        return dict(weights)
    return fn


def _sma_trend_weights(prices: dict, as_of: pd.Timestamp) -> dict[str, float] | None:
    """SPY when close > 200d SMA of close at the decision date, else SHY."""
    s = prices["SPY"]["close"].loc[:as_of].dropna()
    if len(s) < 200:
        return None
    sma = float(s.iloc[-200:].mean())
    return {"SPY": 1.0} if float(s.iloc[-1]) > sma else {"SHY": 1.0}


def _inverse_vol_weights(prices: dict, as_of: pd.Timestamp) -> dict[str, float] | None:
    """Inverse 63d realized vol across the TSMOM universe, fully invested."""
    inv: dict[str, float] = {}
    for t in TSMOM_UNIVERSE:
        s = prices[t]["adj_close"].loc[:as_of].dropna()
        if len(s) < 64:
            continue
        vol = float(s.iloc[-64:].pct_change().dropna().std(ddof=1))
        if vol > 0.0:
            inv[t] = 1.0 / vol
    if not inv:
        return None
    total = sum(inv.values())
    return {t: iv / total for t, iv in inv.items()}


# ---------- runner ------------------------------------------------------------

# name -> (description, calendar tickers for build_schedule, weight fn)
STRATEGIES: list[tuple[str, str, list[str], object]] = [
    ("60_40", "60/40 SPY/AGG, monthly", ["SPY", "AGG"],
     _const_weights({"SPY": 0.6, "AGG": 0.4})),
    ("equal_weight_8", "equal-weight legacy 8-ETF universe, monthly (reference)",
     LEGACY_8, _const_weights({t: 1.0 / len(LEGACY_8) for t in LEGACY_8})),
    ("gem", "GEM dual momentum standalone (Antonacci 12-1)",
     sorted(set(GEM_RISK_ASSETS) | {GEM_FALLBACK, CASH}), gem_weights),
    ("spy_sma200", "SPY/SMA200 trend, month-end checks (honest live S5)",
     ["SPY", "SHY"], _sma_trend_weights),
    ("inverse_vol", "inverse-63d-vol across TSMOM universe, monthly",
     list(TSMOM_UNIVERSE), _inverse_vol_weights),
    ("tsmom", "TSMOM sleeve alone (MOP 2012, long-only, inv-vol)",
     sorted(set(TSMOM_UNIVERSE) | {CASH}), tsmom_weights),
    ("two_sleeve", "candidate: 0.6*TSMOM + 0.4*GEM, 10% vol target",
     sorted(set(TSMOM_UNIVERSE) | {CASH, GEM_FALLBACK}), two_sleeve_weights),
]


def _spy_buy_hold_schedule(prices: dict, start: str) -> list[tuple[pd.Timestamp, dict]]:
    cal = prices["SPY"].index
    cal = cal[cal >= pd.Timestamp(start)]
    return [(pd.Timestamp(cal[0]), {"SPY": 1.0})]


def _run_window(prices: dict, start: str, end) -> dict[str, dict]:
    """All strategies over one window; returns name -> stats dict."""
    out: dict[str, dict] = {}

    runs: list[tuple[str, str, list]] = [
        ("spy_buy_hold", "buy-and-hold SPY", _spy_buy_hold_schedule(prices, start)),
    ]
    for name, desc, cal_tickers, fn in STRATEGIES:
        cal_prices = {t: prices[t] for t in cal_tickers}
        schedule = build_schedule(cal_prices, start, end, fn)
        if not schedule:
            log.warning("%s: empty schedule in window %s..%s — skipped", name, start, end)
            continue
        runs.append((name, desc, schedule))

    for name, desc, schedule in runs:
        res = run_ledger_backtest(
            schedule, prices, cost_bps=COST_BPS, cash_ticker=CASH,
            start=schedule[0][0], end=end, benchmarks=(),
        )
        stats = dict(res.stats)
        stats["start"] = str(stats["start"].date())
        stats["end"] = str(stats["end"].date())
        stats["description"] = desc
        out[name] = stats
        log.info("%-16s %s -> %s  CAGR=%6.2f%%  Sharpe=%5.2f  MaxDD=%7.2f%%",
                 name, stats["start"], stats["end"], stats["cagr"] * 100,
                 stats["sharpe"], stats["max_dd"] * 100)
    return out


def _md_table(stats_by_name: dict[str, dict]) -> str:
    header = (
        "| Strategy | Start | End | CAGR | Vol | Sharpe | MaxDD | "
        "Turnover (x/yr) | Cost drag (bps/yr) | Rebalances |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for name, s in stats_by_name.items():
        rows.append(
            f"| {name} | {s['start']} | {s['end']} | {s['cagr'] * 100:.2f}% | "
            f"{s['vol'] * 100:.2f}% | {s['sharpe']:.2f} | {s['max_dd'] * 100:.2f}% | "
            f"{s['ann_turnover']:.2f} | {s['ann_cost_drag'] * 1e4:.1f} | "
            f"{s['n_rebalances']} |"
        )
    return header + "\n".join(rows) + "\n"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    prices = load_prices(ROOT, ALL_TICKERS)

    results: dict[str, dict] = {}
    for start, end in WINDOWS:
        label = f"{start}..{'latest' if end is None else end}"
        log.info("=== window %s ===", label)
        results[label] = _run_window(prices, start, end)

    generated = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# BASELINES — the permanent promotion bars",
        "",
        f"Generated by `scripts/run_baselines.py` on {generated}. Daily",
        "compounded-ledger engine (`src/backtest/ledger.py`), "
        f"{COST_BPS:.0f} bps per side,",
        f"cash sleeve {CASH}. Do not edit by hand — re-run the script.",
        "",
    ]
    for label, stats_by_name in results.items():
        lines += [f"## Window {label}", "", _md_table(stats_by_name)]
    lines += [
        "## These are the permanent promotion bars",
        "",
        "Per `CONSTITUTION.md` rule 4, every candidate strategy must beat its",
        "named naive baseline **net of costs, on daily-ledger numbers** — the",
        "baselines above (GEM dual momentum, SPY/SMA200, 60/40) are those bars,",
        "and they are permanent: they run in every evaluation window and are",
        "never re-tuned. A candidate that cannot clear them is dropped (no",
        "excuses tier); entry into the paper-trading race additionally requires",
        "the DSR and SPA gates of `EVALUATION.md` §1. Rows built on the TSMOM",
        "universe start no earlier than 2007 because SHV (cash hurdle) lists",
        "2007-01 and DBC lists 2006-02; the SHV hurdle falls back to 0.0 until",
        "SHV has a full 252-day window.",
        "",
    ]
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote %s", MD_PATH)

    payload = {
        "generated": generated,
        "engine": "src/backtest/ledger.py",
        "cost_bps": COST_BPS,
        "cash_ticker": CASH,
        "tsmom_universe": TSMOM_UNIVERSE,
        "legacy_8": LEGACY_8,
        "windows": results,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("wrote %s", JSON_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
