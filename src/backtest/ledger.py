"""Daily compounded-ledger backtester — the honest measurement engine.

Replaces the fwd21-proxy backtest with a NAV ledger that live trading can
converge to:

- A decision dated ``d`` (known at the CLOSE of ``d``) trades at the NEXT
  trading day's OPEN. Fills use dividend/split-consistent prices:
  ``adj_open = open * (adj_close / close)`` per row.
- Daily position returns are adj_close-to-adj_close; on a fill day the
  return is spliced correctly — pre-trade holdings earn prev adj_close ->
  adj_open, post-trade holdings earn adj_open -> adj_close.
- Positions DRIFT between rebalances with each ticker's adjusted return
  (weights renormalize by performance; no phantom daily rebalancing).
- Transaction cost = ``cost_bps/1e4 * sum(|target_notional -
  drifted_notional|)`` deducted from NAV on the fill day (proportionally
  across post-trade positions). The cash sleeve (``cash_ticker``) is a
  real tradable ETF when present in ``prices`` — its legs incur costs like
  any other ticker; when absent it is pure zero-return cash and its legs
  are free.
- Schedule weights that sum to < 1 leave the remainder in ``cash_ticker``.
  Negative weights raise ValueError; weights summing to > 1 raise
  ValueError (would imply negative cash); a scheduled ticker missing from
  ``prices`` raises KeyError naming the ticker.
- Benchmarks run THROUGH THE SAME ENGINE at the same ``cost_bps``:
  ``'SPY'`` = buy-and-hold SPY from the start of the NAV window;
  ``'60_40'`` = 60% SPY / 40% AGG rebalanced at each month-end.

Sharpe is computed on daily NAV returns with rf = 0.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25

_TRADE_COLUMNS = ["date", "ticker", "side", "notional_frac", "cost_frac"]
_REQUIRED_PRICE_COLUMNS = ("open", "close", "adj_close")


@dataclass
class LedgerResult:
    """Bundle returned by :func:`run_ledger_backtest`."""
    nav: pd.Series                    # daily NAV, starts at 1.0, DatetimeIndex
    weights: pd.DataFrame             # daily post-close weights per ticker (drifted between rebalances)
    trades: pd.DataFrame              # columns: date, ticker, side, notional_frac, cost_frac
    stats: dict                       # keys: cagr, vol, sharpe, max_dd, ann_turnover, ann_cost_drag, n_rebalances, start, end
    benchmarks: dict = field(default_factory=dict)   # name -> NAV pd.Series aligned to nav.index


def load_prices(root, tickers) -> dict[str, pd.DataFrame]:
    """Read data/clean/prices/<t>.parquet for each ticker (columns include open/close/adj_close).

    Raises FileNotFoundError naming the ticker if a parquet is missing, and
    ValueError if a required column is absent.
    """
    root = Path(root)
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        path = root / "data" / "clean" / "prices" / f"{t}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"price file for ticker '{t}' not found: {path}")
        df = pd.read_parquet(path)
        missing = [c for c in _REQUIRED_PRICE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"'{t}': price file missing columns {missing}")
        if not isinstance(df.index, pd.DatetimeIndex):
            # A string index would sort lexicographically and silently break
            # every Timestamp comparison in the simulator.
            df.index = pd.to_datetime(df.index)
        out[t] = df.sort_index()
    return out


def _validate_schedule(
    weight_schedule, prices: dict[str, pd.DataFrame]
) -> list[tuple[pd.Timestamp, dict[str, float]]]:
    """Normalize/validate the schedule; sorted by decision date ascending."""
    if not weight_schedule:
        raise ValueError("weight_schedule is empty")
    norm: list[tuple[pd.Timestamp, dict[str, float]]] = []
    for d, w in weight_schedule:
        ts = pd.Timestamp(d)
        total = 0.0
        for t, x in w.items():
            if t not in prices:
                raise KeyError(f"unknown ticker '{t}' in weight_schedule at {ts.date()} (not in prices)")
            if x < 0:
                raise ValueError(f"negative weight {x} for ticker '{t}' at {ts.date()}")
            total += float(x)
        if total > 1.0 + 1e-9:
            raise ValueError(f"weights at {ts.date()} sum to {total:.6f} > 1 (negative cash not allowed)")
        norm.append((ts, {t: float(x) for t, x in w.items()}))
    norm.sort(key=lambda e: e[0])
    return norm


def _build_return_frames(
    tickers: list[str], prices: dict[str, pd.DataFrame], cash_ticker: str
) -> tuple[pd.DatetimeIndex, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aligned (close_ret, overnight_ret, intraday_ret) frames on the union calendar.

    Missing rows are forward-filled on adj_close (zero return); a missing
    open falls back to the previous adj_close (zero overnight move). A
    ``cash_ticker`` absent from ``prices`` gets an all-zero return column.
    Guaranteed identity: (1 + overnight) * (1 + intraday) == 1 + close_ret.
    """
    closes: dict[str, pd.Series] = {}
    opens: dict[str, pd.Series] = {}
    for t in tickers:
        if t not in prices:
            continue  # absent cash_ticker — zero-return column added below
        df = prices[t]
        adj_close = df["adj_close"].astype(float)
        adj_open = df["open"].astype(float) * adj_close / df["close"].astype(float)
        closes[t] = adj_close
        opens[t] = adj_open
    adj_close = pd.DataFrame(closes).sort_index()   # union calendar
    calendar = pd.DatetimeIndex(adj_close.index)
    # ffill bridges vendor gaps, but a ticker whose data ENDS before the
    # window does must not silently become a flat 0%-return asset — that
    # would corrupt the promotion-bar numbers exactly the way stale panel
    # data corrupted live signals.
    for t, s in closes.items():
        last_real = s.dropna().index.max()
        gap = (calendar > last_real).sum()
        if gap > 5:
            log.warning(
                "ledger: '%s' has no price data for the last %d calendar rows "
                "(ends %s) — its return is ffilled flat over that span",
                t, int(gap), last_real.date(),
            )
    adj_close = adj_close.ffill()
    prev_close = adj_close.shift(1)
    adj_open = pd.DataFrame(opens).reindex(calendar).fillna(prev_close)

    close_ret = (adj_close / prev_close - 1.0).fillna(0.0)
    overnight_ret = (adj_open / prev_close - 1.0).fillna(0.0)
    intraday_ret = (adj_close / adj_open - 1.0).fillna(0.0)
    for frame in (close_ret, overnight_ret, intraday_ret):
        for t in tickers:
            if t not in frame.columns:
                frame[t] = 0.0
    cols = list(tickers)
    return calendar, close_ret[cols], overnight_ret[cols], intraday_ret[cols]


def _simulate(
    schedule: list[tuple[pd.Timestamp, dict[str, float]]],
    prices: dict[str, pd.DataFrame],
    cost_bps: float,
    cash_ticker: str,
    start,
    end,
) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame, dict]:
    """Core daily ledger loop. Returns (nav, weights, trades, fill_totals)."""
    sched = _validate_schedule(schedule, prices)
    columns = sorted({t for _, w in sched for t in w} | {cash_ticker})
    calendar, close_ret, overnight_ret, intraday_ret = _build_return_frames(columns, prices, cash_ticker)

    window_start = pd.Timestamp(start) if start is not None else sched[0][0]
    window_end = pd.Timestamp(end) if end is not None else calendar[-1]
    cal_win = calendar[(calendar >= window_start) & (calendar <= window_end)]
    if len(cal_win) < 2:
        raise ValueError(f"window [{window_start.date()}, {window_end.date()}] has < 2 trading days")

    # Decisions dated before the window: carry forward the LAST one, re-dated
    # to the first window day (position enters at the open of the second day).
    pre = [e for e in sched if e[0] < window_start]
    live = [e for e in sched if e[0] >= window_start]
    if pre:
        live = [(cal_win[0], pre[-1][1])] + live

    # Map decision date -> fill index (first trading day strictly after it).
    fill_map: dict[int, dict[str, float]] = {}
    for ts, w in live:
        pos = int(cal_win.searchsorted(ts, side="right"))
        if pos >= len(cal_win):
            log.info("decision at %s has no fill day before window end — dropped", ts.date())
            continue
        pos = max(pos, 1)  # NAV is defined as 1.0 at the close of day 0; earliest fill is day 1's open
        if pos in fill_map:
            log.warning("multiple decisions fill on %s — the later decision wins", cal_win[pos].date())
        fill_map[pos] = w

    n_days, n_cols = len(cal_win), len(columns)
    cr = close_ret.loc[cal_win].to_numpy()
    on = overnight_ret.loc[cal_win].to_numpy()
    intra = intraday_ret.loc[cal_win].to_numpy()
    cash_idx = columns.index(cash_ticker)
    # Cash legs are free only when cash_ticker is pure cash (absent from prices).
    trade_mask = np.ones(n_cols, dtype=bool)
    if cash_ticker not in prices:
        trade_mask[cash_idx] = False

    cost_rate = cost_bps / 1e4
    pos_val = np.zeros(n_cols)
    pos_val[cash_idx] = 1.0
    nav_vals = np.empty(n_days)
    weight_vals = np.empty((n_days, n_cols))
    nav_vals[0] = 1.0
    weight_vals[0] = pos_val
    trade_rows: list[dict] = []
    n_rebalances = 0
    total_traded_frac = 0.0
    total_cost_frac = 0.0

    for i in range(1, n_days):
        target_w = fill_map.get(i)
        if target_w is None:
            pos_val = pos_val * (1.0 + cr[i])
        else:
            pos_val = pos_val * (1.0 + on[i])          # drift prev close -> today's open
            nav_open = pos_val.sum()
            w_vec = np.zeros(n_cols)
            for t, x in target_w.items():
                w_vec[columns.index(t)] += x
            w_vec[cash_idx] += max(0.0, 1.0 - w_vec.sum())
            target_val = w_vec * nav_open
            delta = target_val - pos_val
            traded = float(np.abs(delta[trade_mask]).sum())
            cost = cost_rate * traded
            date_i = cal_win[i]
            for j in np.flatnonzero(trade_mask):
                notional_frac = abs(delta[j]) / nav_open
                if notional_frac < 1e-12:
                    continue
                trade_rows.append({
                    "date": date_i,
                    "ticker": columns[j],
                    "side": "buy" if delta[j] > 0 else "sell",
                    "notional_frac": notional_frac,
                    "cost_frac": cost_rate * notional_frac,
                })
            pos_val = target_val * (1.0 - cost / nav_open)  # cost deducted proportionally on fill day
            pos_val = pos_val * (1.0 + intra[i])            # earn today's open -> close
            n_rebalances += 1
            total_traded_frac += traded / nav_open
            total_cost_frac += cost / nav_open
        nav_vals[i] = pos_val.sum()
        weight_vals[i] = pos_val / nav_vals[i]

    nav = pd.Series(nav_vals, index=cal_win, name="nav")
    weights = pd.DataFrame(weight_vals, index=cal_win, columns=columns)
    trades = pd.DataFrame(trade_rows, columns=_TRADE_COLUMNS)
    fill_totals = {
        "n_rebalances": n_rebalances,
        "total_traded_frac": total_traded_frac,
        "total_cost_frac": total_cost_frac,
    }
    return nav, weights, trades, fill_totals


def _compute_stats(nav: pd.Series, fill_totals: dict) -> dict:
    """cagr / vol / sharpe (rf=0) / max_dd / ann_turnover / ann_cost_drag from the NAV path."""
    start, end = nav.index[0], nav.index[-1]
    years = max((end - start).days / CALENDAR_DAYS_PER_YEAR, 1e-9)
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0)
    daily = (nav / nav.shift(1) - 1.0).dropna()
    sd = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    vol = float(sd * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float(daily.mean() / sd * np.sqrt(TRADING_DAYS_PER_YEAR)) if sd > 0 else float("nan")
    max_dd = float((nav / nav.cummax() - 1.0).min())
    return {
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "ann_turnover": float(fill_totals["total_traded_frac"] / years),
        "ann_cost_drag": float(fill_totals["total_cost_frac"] / years),
        "n_rebalances": fill_totals["n_rebalances"],
        "start": start,
        "end": end,
    }


def _month_end_dates(calendar: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Last trading date of each month in the calendar."""
    return list(calendar.to_series().groupby(calendar.to_period("M")).last())


def _benchmark_navs(
    names,
    prices: dict[str, pd.DataFrame],
    cost_bps: float,
    cash_ticker: str,
    nav_index: pd.DatetimeIndex,
) -> dict[str, pd.Series]:
    """Benchmark NAVs through the same engine, aligned to nav_index."""
    out: dict[str, pd.Series] = {}
    for name in names:
        if name == "SPY":
            need, weights = ["SPY"], {"SPY": 1.0}
        elif name == "60_40":
            need, weights = ["SPY", "AGG"], {"SPY": 0.6, "AGG": 0.4}
        else:
            raise ValueError(f"unknown benchmark '{name}' (supported: 'SPY', '60_40')")
        missing = [t for t in need if t not in prices]
        if missing:
            log.warning("benchmark '%s' skipped — tickers %s not in prices", name, missing)
            continue
        schedule = [(nav_index[0], weights)]
        if name == "60_40":
            cal = pd.DatetimeIndex(sorted(set().union(*(prices[t].index for t in need))))
            cal = cal[(cal >= nav_index[0]) & (cal <= nav_index[-1])]
            schedule += [
                (me, weights) for me in _month_end_dates(cal)
                if nav_index[0] < me < nav_index[-1]
            ]
        bnav, _, _, _ = _simulate(schedule, prices, cost_bps, cash_ticker, nav_index[0], nav_index[-1])
        out[name] = bnav.reindex(nav_index).ffill().fillna(1.0).rename(name)
    return out


def run_ledger_backtest(
    weight_schedule,                  # list[tuple[pd.Timestamp, dict[str, float]]] — decision known at CLOSE of that date
    prices,                           # dict[str, pd.DataFrame]
    cost_bps: float = 10.0,           # per side, applied to traded notional
    cash_ticker: str = "SHV",         # un-invested weight earns this ETF's return; if ticker absent, earns 0
    start=None, end=None,
    benchmarks: tuple = ("SPY", "60_40"),
) -> LedgerResult:
    """Run the daily compounded-ledger backtest over the weight schedule.

    See the module docstring for the full fill/cost/drift semantics. The NAV
    series starts at 1.0 at the close of the first window day (portfolio held
    in ``cash_ticker``); the first decision fills at the next day's open.
    ``start``/``end`` clip the simulation window; the last decision at or
    before ``start`` is carried forward so the portfolio enters its intended
    position at the start of the window. Sharpe uses rf = 0.
    """
    nav, weights, trades, fill_totals = _simulate(
        weight_schedule, prices, cost_bps, cash_ticker, start, end
    )
    stats = _compute_stats(nav, fill_totals)
    bench = _benchmark_navs(benchmarks or (), prices, cost_bps, cash_ticker, nav.index)
    log.info(
        "ledger backtest %s -> %s: CAGR=%.2f%%  vol=%.2f%%  Sharpe=%.2f  MaxDD=%.2f%%  "
        "turnover=%.2fx/yr  cost_drag=%.1f bps/yr  n_rebalances=%d",
        stats["start"].date(), stats["end"].date(), stats["cagr"] * 100, stats["vol"] * 100,
        stats["sharpe"], stats["max_dd"] * 100, stats["ann_turnover"],
        stats["ann_cost_drag"] * 1e4, stats["n_rebalances"],
    )
    return LedgerResult(nav=nav, weights=weights, trades=trades, stats=stats, benchmarks=bench)
