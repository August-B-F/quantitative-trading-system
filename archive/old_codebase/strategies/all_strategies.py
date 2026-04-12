"""
Comprehensive systematic strategy library.
Each strategy is a function: strategy_fn(prices, date) -> {ticker: weight}
"""

import numpy as np
import pandas as pd
from backtest_engine import compute_momentum, compute_volatility, compute_sma, compute_rsi


# =============================================================================
# STRATEGY 1: DUAL MOMENTUM (Antonacci, 2012)
# Academic basis: "Risk Premia Harvesting Through Dual Momentum" (SSRN)
# Logic: Relative momentum picks best asset class, absolute momentum filters regime.
# =============================================================================

def dual_momentum_strategy(prices: pd.DataFrame, date: pd.Timestamp,
                           lookback: int = 252, skip: int = 21,
                           us_ticker: str = "SPY", intl_ticker: str = "EFA",
                           bond_ticker: str = "AGG", tbill_ticker: str = "BIL") -> dict:
    """Classic dual momentum: US vs International equities, bonds as safe haven."""
    tickers = [us_ticker, intl_ticker, bond_ticker, tbill_ticker]
    available = [t for t in tickers if t in prices.columns]
    if len(available) < 3:
        return None

    idx = prices.index.get_loc(date)
    if idx < lookback:
        return None

    # Compute 12-month momentum (skip recent month)
    mom = {}
    for t in available:
        series = prices[t].iloc[:idx + 1]
        if len(series) > lookback:
            if skip > 0 and len(series) > skip:
                mom[t] = series.iloc[-skip - 1] / series.iloc[-lookback] - 1
            else:
                mom[t] = series.iloc[-1] / series.iloc[-lookback] - 1

    if not mom:
        return None

    # Absolute momentum: is equity momentum positive?
    us_mom = mom.get(us_ticker, 0)
    intl_mom = mom.get(intl_ticker, 0)
    tbill_mom = mom.get(tbill_ticker, 0)

    # Relative momentum: pick best between US and international
    if us_mom > intl_mom:
        best_equity = us_ticker
        best_mom = us_mom
    else:
        best_equity = intl_ticker
        best_mom = intl_mom

    # Absolute momentum filter: if best equity < t-bills, go to bonds
    if best_mom > tbill_mom:
        return {best_equity: 1.0}
    else:
        return {bond_ticker: 1.0}


# =============================================================================
# STRATEGY 2: SECTOR MOMENTUM ROTATION
# Academic basis: Moskowitz & Grinblatt (1999) "Do Industries Explain Momentum?"
# Logic: Rotate into top-K sectors by momentum, with trend filter.
# =============================================================================

def sector_momentum_strategy(prices: pd.DataFrame, date: pd.Timestamp,
                             lookback: int = 252, skip: int = 21,
                             top_k: int = 3, trend_filter: bool = True,
                             sectors: list = None, bond_ticker: str = "AGG") -> dict:
    """Rotate into top-K sectors by 12-month momentum with trend filter."""
    if sectors is None:
        sectors = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC"]

    available = [s for s in sectors if s in prices.columns]
    if len(available) < top_k:
        return None

    idx = prices.index.get_loc(date)
    if idx < lookback:
        return None

    # Compute momentum for each sector
    mom = {}
    for s in available:
        series = prices[s].iloc[:idx + 1]
        if len(series) > lookback:
            if skip > 0:
                mom[s] = series.iloc[-skip - 1] / series.iloc[-lookback] - 1
            else:
                mom[s] = series.iloc[-1] / series.iloc[-lookback] - 1

    if len(mom) < top_k:
        return None

    # Rank and select top-K
    ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
    top_sectors = ranked[:top_k]

    # Trend filter: only invest if sector is above 200-day SMA
    weights = {}
    if trend_filter:
        for ticker, m in top_sectors:
            series = prices[ticker].iloc[:idx + 1]
            sma200 = series.rolling(200).mean().iloc[-1]
            if series.iloc[-1] > sma200:
                weights[ticker] = 1.0 / top_k
    else:
        for ticker, m in top_sectors:
            weights[ticker] = 1.0 / top_k

    # If all filtered out, go to bonds
    if not weights and bond_ticker in prices.columns:
        return {bond_ticker: 1.0}

    # Normalize weights
    if weights:
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

    return weights


# =============================================================================
# STRATEGY 3: TREND FOLLOWING (Time-Series Momentum)
# Academic basis: Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum" (JFE)
# Logic: Go long assets with positive trend, scale by inverse volatility.
# =============================================================================

def trend_following_strategy(prices: pd.DataFrame, date: pd.Timestamp,
                             lookback: int = 252, vol_window: int = 63,
                             assets: list = None, bond_ticker: str = "TLT",
                             cash_ticker: str = "BIL") -> dict:
    """Multi-asset trend following with volatility targeting."""
    if assets is None:
        assets = ["SPY", "EFA", "EEM", "TLT", "GLD", "DBC"]

    available = [a for a in assets if a in prices.columns]
    if len(available) < 2:
        return None

    idx = prices.index.get_loc(date)
    if idx < lookback:
        return None

    weights = {}
    inv_vols = {}

    for ticker in available:
        series = prices[ticker].iloc[:idx + 1]
        if len(series) < lookback:
            continue

        # Trend signal: 12-month return
        ret_12m = series.iloc[-1] / series.iloc[-lookback] - 1

        # Volatility for position sizing
        daily_ret = series.pct_change().dropna()
        if len(daily_ret) < vol_window:
            continue
        vol = daily_ret.iloc[-vol_window:].std() * np.sqrt(252)

        if vol > 0 and ret_12m > 0:
            inv_vols[ticker] = 1.0 / vol

    # Inverse volatility weighting for assets with positive trend
    if inv_vols:
        total_inv_vol = sum(inv_vols.values())
        for ticker, iv in inv_vols.items():
            weights[ticker] = iv / total_inv_vol
    else:
        # All negative trend: go to cash/bonds
        if cash_ticker in prices.columns:
            weights = {cash_ticker: 1.0}

    return weights


# =============================================================================
# STRATEGY 4: VIGILANT ASSET ALLOCATION (Keller & Keuning, 2016)
# Academic basis: "Breadth Momentum and Vigilant Asset Allocation" (SSRN)
# Logic: Crash protection via breadth momentum across offensive/defensive assets.
# =============================================================================

def vigilant_asset_allocation(prices: pd.DataFrame, date: pd.Timestamp,
                              offensive: list = None, defensive: list = None,
                              top_n: int = 5, breadth_n: int = 4) -> dict:
    """VAA: switch to defensive if any offensive asset has negative momentum."""
    if offensive is None:
        offensive = ["SPY", "EFA", "EEM", "AGG"]
    if defensive is None:
        defensive = ["SHY", "IEF", "LQD"]

    all_tickers = offensive + defensive
    available_off = [t for t in offensive if t in prices.columns]
    available_def = [t for t in defensive if t in prices.columns]

    if len(available_off) < 2 or len(available_def) < 1:
        return None

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    def weighted_momentum(series):
        """Weighted average of 1, 3, 6, 12-month momentum."""
        r1 = series.iloc[-1] / series.iloc[-21] - 1 if len(series) > 21 else 0
        r3 = series.iloc[-1] / series.iloc[-63] - 1 if len(series) > 63 else 0
        r6 = series.iloc[-1] / series.iloc[-126] - 1 if len(series) > 126 else 0
        r12 = series.iloc[-1] / series.iloc[-252] - 1 if len(series) > 252 else 0
        return 12 * r1 + 4 * r3 + 2 * r6 + r12

    # Compute momentum for all offensive assets
    off_mom = {}
    for t in available_off:
        series = prices[t].iloc[:idx + 1]
        off_mom[t] = weighted_momentum(series)

    # Breadth signal: how many offensive assets have negative momentum?
    neg_count = sum(1 for m in off_mom.values() if m < 0)

    # Crash protection fraction
    cp = min(neg_count / breadth_n, 1.0)

    if cp >= 1.0:
        # Full defensive mode
        def_mom = {}
        for t in available_def:
            series = prices[t].iloc[:idx + 1]
            def_mom[t] = weighted_momentum(series)
        best_def = max(def_mom, key=def_mom.get)
        return {best_def: 1.0}
    elif cp > 0:
        # Partial: mix offensive and defensive
        # Pick best offensive
        ranked_off = sorted(off_mom.items(), key=lambda x: x[1], reverse=True)
        best_off = ranked_off[0][0]

        # Pick best defensive
        def_mom = {}
        for t in available_def:
            series = prices[t].iloc[:idx + 1]
            def_mom[t] = weighted_momentum(series)
        best_def = max(def_mom, key=def_mom.get)

        return {best_off: 1.0 - cp, best_def: cp}
    else:
        # All clear: pick best offensive
        ranked_off = sorted(off_mom.items(), key=lambda x: x[1], reverse=True)
        best_off = ranked_off[0][0]
        return {best_off: 1.0}


# =============================================================================
# STRATEGY 5: PROTECTIVE ASSET ALLOCATION (Keller & Keuning, 2016)
# Academic basis: "Breadth Momentum and the Canary Universe" (SSRN)
# Logic: Use "canary" assets to detect crashes, rotate among broad assets.
# =============================================================================

def protective_asset_allocation(prices: pd.DataFrame, date: pd.Timestamp,
                                 canary: list = None, universe: list = None,
                                 safe: list = None, top_n: int = 6) -> dict:
    """PAA: canary universe triggers crash protection."""
    if canary is None:
        canary = ["EEM", "AGG"]  # Canary: EM + bonds
    if universe is None:
        universe = ["SPY", "QQQ", "IWM", "VGK", "EWJ", "EEM",
                    "VNQ", "GLD", "TLT", "HYG", "LQD", "TIP"]
    if safe is None:
        safe = ["SHY", "IEF", "BIL"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    def weighted_momentum(series):
        r1 = series.iloc[-1] / series.iloc[-21] - 1 if len(series) > 21 else 0
        r3 = series.iloc[-1] / series.iloc[-63] - 1 if len(series) > 63 else 0
        r6 = series.iloc[-1] / series.iloc[-126] - 1 if len(series) > 126 else 0
        r12 = series.iloc[-1] / series.iloc[-252] - 1 if len(series) > 252 else 0
        return 12 * r1 + 4 * r3 + 2 * r6 + r12

    # Check canary assets
    canary_available = [c for c in canary if c in prices.columns]
    neg_canary = 0
    for c in canary_available:
        series = prices[c].iloc[:idx + 1]
        if weighted_momentum(series) < 0:
            neg_canary += 1

    # Bond fraction = neg_canary / len(canary)
    bond_frac = neg_canary / max(len(canary_available), 1)

    # Compute momentum for universe
    uni_available = [u for u in universe if u in prices.columns]
    uni_mom = {}
    for u in uni_available:
        series = prices[u].iloc[:idx + 1]
        uni_mom[u] = weighted_momentum(series)

    # Top N by momentum
    ranked = sorted(uni_mom.items(), key=lambda x: x[1], reverse=True)
    top = ranked[:top_n]

    # Equity allocation
    equity_frac = 1.0 - bond_frac
    weights = {}

    if equity_frac > 0 and top:
        per_asset = equity_frac / len(top)
        for ticker, _ in top:
            weights[ticker] = per_asset

    if bond_frac > 0:
        # Pick best safe asset
        safe_available = [s for s in safe if s in prices.columns]
        if safe_available:
            safe_mom = {}
            for s in safe_available:
                series = prices[s].iloc[:idx + 1]
                safe_mom[s] = weighted_momentum(series)
            best_safe = max(safe_mom, key=safe_mom.get)
            weights[best_safe] = weights.get(best_safe, 0) + bond_frac

    return weights


# =============================================================================
# STRATEGY 6: ADAPTIVE ASSET ALLOCATION (Butler, Philbrick, Gordillo, 2012)
# Academic basis: "Adaptive Asset Allocation" (ReSolve Asset Management)
# Logic: Momentum ranking + minimum variance optimization among top assets.
# =============================================================================

def adaptive_asset_allocation(prices: pd.DataFrame, date: pd.Timestamp,
                               assets: list = None, top_n: int = 5,
                               lookback: int = 126, vol_lookback: int = 21) -> dict:
    """AAA: pick top momentum assets, then minimum variance weight them."""
    if assets is None:
        assets = ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ", "QQQ"]

    available = [a for a in assets if a in prices.columns]
    if len(available) < top_n:
        top_n = len(available)

    idx = prices.index.get_loc(date)
    if idx < max(lookback, 252):
        return None

    # Momentum ranking (6-month)
    mom = {}
    for a in available:
        series = prices[a].iloc[:idx + 1]
        if len(series) > lookback:
            mom[a] = series.iloc[-1] / series.iloc[-lookback] - 1

    if len(mom) < top_n:
        return None

    ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
    top = [r[0] for r in ranked[:top_n]]

    # Minimum variance weighting among top assets
    returns_data = prices[top].iloc[max(0, idx - vol_lookback):idx + 1].pct_change().dropna()
    if len(returns_data) < 10:
        # Equal weight fallback
        return {t: 1.0 / len(top) for t in top}

    cov = returns_data.cov().values
    try:
        inv_cov = np.linalg.inv(cov)
        ones = np.ones(len(top))
        raw_weights = inv_cov @ ones
        raw_weights = np.maximum(raw_weights, 0)  # No short selling
        total = raw_weights.sum()
        if total > 0:
            weights = raw_weights / total
        else:
            weights = np.ones(len(top)) / len(top)
    except np.linalg.LinAlgError:
        weights = np.ones(len(top)) / len(top)

    return {top[i]: float(weights[i]) for i in range(len(top)) if weights[i] > 0.01}


# =============================================================================
# STRATEGY 7: LEVERAGED RISK PARITY
# Academic basis: Asness, Frazzini, Pedersen (2012) "Leverage Aversion and Risk Parity"
# Logic: Equal risk contribution across asset classes, scale to target vol.
# =============================================================================

def risk_parity_strategy(prices: pd.DataFrame, date: pd.Timestamp,
                         assets: list = None, target_vol: float = 0.10,
                         vol_lookback: int = 63) -> dict:
    """Inverse-volatility (simplified risk parity) across diversified assets."""
    if assets is None:
        assets = ["SPY", "TLT", "GLD", "VNQ", "EFA"]

    available = [a for a in assets if a in prices.columns]
    if len(available) < 2:
        return None

    idx = prices.index.get_loc(date)
    if idx < vol_lookback + 20:
        return None

    inv_vols = {}
    for a in available:
        returns = prices[a].iloc[:idx + 1].pct_change().dropna()
        if len(returns) >= vol_lookback:
            vol = returns.iloc[-vol_lookback:].std() * np.sqrt(252)
            if vol > 0:
                inv_vols[a] = 1.0 / vol

    if not inv_vols:
        return None

    total = sum(inv_vols.values())
    weights = {k: v / total for k, v in inv_vols.items()}

    # Scale to target volatility (but cap at 100% - no leverage)
    port_returns = pd.DataFrame()
    for a in weights:
        r = prices[a].iloc[:idx + 1].pct_change().dropna()
        port_returns[a] = r * weights[a]
    if len(port_returns) > vol_lookback:
        port_vol = port_returns.sum(axis=1).iloc[-vol_lookback:].std() * np.sqrt(252)
        if port_vol > 0:
            scale = min(target_vol / port_vol, 1.0)
            weights = {k: v * scale for k, v in weights.items()}

    return weights


# =============================================================================
# STRATEGY 8: COMPOSITE MOMENTUM + MEAN REVERSION
# Logic: Long momentum winners at monthly frequency, but use short-term mean
# reversion for entry timing. Combines two well-documented anomalies.
# =============================================================================

def composite_momentum_mr(prices: pd.DataFrame, date: pd.Timestamp,
                          assets: list = None, mom_lookback: int = 252,
                          mr_lookback: int = 5, top_k: int = 3,
                          bond_ticker: str = "AGG") -> dict:
    """Long momentum winners, timed by short-term mean reversion dips."""
    if assets is None:
        assets = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC"]

    available = [a for a in assets if a in prices.columns]
    if len(available) < top_k:
        return None

    idx = prices.index.get_loc(date)
    if idx < mom_lookback:
        return None

    # 12-month momentum ranking
    mom = {}
    for a in available:
        series = prices[a].iloc[:idx + 1]
        if len(series) > mom_lookback:
            mom[a] = series.iloc[-22] / series.iloc[-mom_lookback] - 1  # skip recent month

    if len(mom) < top_k:
        return None

    ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
    top = [r[0] for r in ranked[:top_k]]

    # Among top momentum, prefer those with short-term pullback (mean reversion)
    scores = {}
    for t in top:
        series = prices[t].iloc[:idx + 1]
        ret_5d = series.iloc[-1] / series.iloc[-mr_lookback] - 1
        # Lower recent return = better entry (mean reversion within momentum)
        scores[t] = -ret_5d  # Negative because we want to buy dips

    # Weight: higher weight to better (more oversold) entries within momentum winners
    total_score = sum(max(s, 0.01) for s in scores.values())
    weights = {}
    for t in top:
        w = max(scores[t], 0.01) / total_score
        weights[t] = w

    # Trend filter on SPY
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma200 = spy.rolling(200).mean().iloc[-1]
        if spy.iloc[-1] < sma200:
            # Market downtrend: reduce equity, add bonds
            bond_w = 0.5
            if bond_ticker in prices.columns:
                weights = {k: v * (1 - bond_w) for k, v in weights.items()}
                weights[bond_ticker] = bond_w

    return weights


# =============================================================================
# STRATEGY 9: BOLD ASSET ALLOCATION (Keller, 2014)
# Logic: Concentrate in single best momentum asset with crash protection.
# =============================================================================

def bold_asset_allocation(prices: pd.DataFrame, date: pd.Timestamp,
                          universe: list = None, safe: list = None) -> dict:
    """Concentrate 100% in single best momentum asset; bail to safe if all negative."""
    if universe is None:
        universe = ["SPY", "QQQ", "EFA", "EEM", "VNQ", "GLD", "TLT", "HYG"]
    if safe is None:
        safe = ["SHY", "BIL", "IEF"]

    available = [u for u in universe if u in prices.columns]
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    def weighted_momentum(series):
        r1 = series.iloc[-1] / series.iloc[-21] - 1 if len(series) > 21 else 0
        r3 = series.iloc[-1] / series.iloc[-63] - 1 if len(series) > 63 else 0
        r6 = series.iloc[-1] / series.iloc[-126] - 1 if len(series) > 126 else 0
        r12 = series.iloc[-1] / series.iloc[-252] - 1 if len(series) > 252 else 0
        return 12 * r1 + 4 * r3 + 2 * r6 + r12

    mom = {}
    for a in available:
        series = prices[a].iloc[:idx + 1]
        mom[a] = weighted_momentum(series)

    # If best momentum is positive, go all in
    best = max(mom, key=mom.get)
    if mom[best] > 0:
        return {best: 1.0}
    else:
        safe_available = [s for s in safe if s in prices.columns]
        if safe_available:
            safe_mom = {}
            for s in safe_available:
                series = prices[s].iloc[:idx + 1]
                safe_mom[s] = weighted_momentum(series)
            best_safe = max(safe_mom, key=safe_mom.get)
            return {best_safe: 1.0}
        return None


# =============================================================================
# STRATEGY 10: ACCELERATING DUAL MOMENTUM
# Enhancement of Antonacci's original: use acceleration (rate of change of momentum)
# to get earlier signals.
# =============================================================================

def accelerating_dual_momentum(prices: pd.DataFrame, date: pd.Timestamp,
                                us_ticker: str = "SPY", intl_ticker: str = "EFA",
                                bond_ticker: str = "AGG", safe_ticker: str = "BIL") -> dict:
    """Dual momentum with acceleration signal for faster regime changes."""
    idx = prices.index.get_loc(date)
    if idx < 252 + 21:
        return None

    def get_accel_momentum(series):
        """12-month momentum + its 1-month change (acceleration)."""
        if len(series) < 274:
            return 0, 0
        mom_now = series.iloc[-22] / series.iloc[-252] - 1  # 12m mom, skip 1m
        mom_prev = series.iloc[-43] / series.iloc[-273] - 1  # Same, 1 month ago
        accel = mom_now - mom_prev
        return mom_now, accel

    results = {}
    for t in [us_ticker, intl_ticker]:
        if t in prices.columns:
            series = prices[t].iloc[:idx + 1]
            m, a = get_accel_momentum(series)
            results[t] = {"momentum": m, "acceleration": a, "composite": m + 0.5 * a}

    if len(results) < 2:
        return None

    # Pick best by composite score
    best = max(results, key=lambda t: results[t]["composite"])
    best_score = results[best]["composite"]

    # Absolute momentum: composite must be positive
    if best_score > 0:
        return {best: 1.0}
    else:
        return {bond_ticker: 1.0} if bond_ticker in prices.columns else {safe_ticker: 1.0}


# =============================================================================
# STRATEGY 11: MULTI-ASSET MOMENTUM WITH VOLATILITY FILTER
# Logic: Broad asset momentum + vol targeting + drawdown control.
# =============================================================================

def multi_asset_momentum_vol(prices: pd.DataFrame, date: pd.Timestamp,
                              assets: list = None, top_n: int = 4,
                              target_vol: float = 0.12,
                              max_dd_threshold: float = -0.15) -> dict:
    """Multi-asset momentum with vol targeting and drawdown control."""
    if assets is None:
        assets = ["SPY", "QQQ", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ", "HYG"]

    available = [a for a in assets if a in prices.columns]
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Momentum scores
    mom = {}
    for a in available:
        series = prices[a].iloc[:idx + 1]
        if len(series) > 252:
            r3 = series.iloc[-1] / series.iloc[-63] - 1 if len(series) > 63 else 0
            r6 = series.iloc[-1] / series.iloc[-126] - 1 if len(series) > 126 else 0
            r12 = series.iloc[-1] / series.iloc[-252] - 1 if len(series) > 252 else 0
            mom[a] = (r3 + r6 + r12) / 3

    if len(mom) < top_n:
        return None

    # Select top N
    ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
    top = [r[0] for r in ranked[:top_n] if r[1] > 0]  # Only positive momentum

    if not top:
        # All negative: go to safe assets
        for safe in ["IEF", "SHY", "BIL"]:
            if safe in prices.columns:
                return {safe: 1.0}
        return None

    # Inverse volatility weighting
    inv_vols = {}
    for t in top:
        rets = prices[t].iloc[:idx + 1].pct_change().dropna()
        if len(rets) >= 63:
            vol = rets.iloc[-63:].std() * np.sqrt(252)
            if vol > 0:
                inv_vols[t] = 1.0 / vol

    if not inv_vols:
        return {t: 1.0 / len(top) for t in top}

    total_iv = sum(inv_vols.values())
    weights = {k: v / total_iv for k, v in inv_vols.items()}

    return weights


# =============================================================================
# STRATEGY 12: GROWTH-TREND TIMING (Faber-style)
# Academic basis: Faber (2007) "A Quantitative Approach to Tactical Asset Allocation"
# Logic: Hold QQQ/growth when above 200 SMA, else bonds. Simple but effective.
# =============================================================================

def growth_trend_timing(prices: pd.DataFrame, date: pd.Timestamp,
                        growth_ticker: str = "QQQ", bond_ticker: str = "TLT",
                        sma_period: int = 200) -> dict:
    """Simple trend timing: QQQ above SMA = long growth, below = long bonds."""
    if growth_ticker not in prices.columns:
        return None

    idx = prices.index.get_loc(date)
    if idx < sma_period + 20:
        return None

    series = prices[growth_ticker].iloc[:idx + 1]
    sma = series.rolling(sma_period).mean().iloc[-1]

    if series.iloc[-1] > sma:
        return {growth_ticker: 1.0}
    else:
        if bond_ticker in prices.columns:
            return {bond_ticker: 1.0}
        return None


# =============================================================================
# STRATEGY 13: ENHANCED GROWTH TREND (Dual signal: SMA + momentum)
# =============================================================================

def enhanced_growth_trend(prices: pd.DataFrame, date: pd.Timestamp,
                          growth_tickers: list = None,
                          bond_tickers: list = None,
                          sma_period: int = 200, mom_period: int = 126) -> dict:
    """Enhanced trend: pick best growth ETF when trending up, best bond when not."""
    if growth_tickers is None:
        growth_tickers = ["QQQ", "SPY", "VUG", "MTUM"]
    if bond_tickers is None:
        bond_tickers = ["TLT", "IEF", "AGG"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, mom_period) + 20:
        return None

    # Check broad market trend
    spy_available = "SPY" in prices.columns
    market_up = True
    if spy_available:
        spy = prices["SPY"].iloc[:idx + 1]
        spy_sma = spy.rolling(sma_period).mean().iloc[-1]
        market_up = spy.iloc[-1] > spy_sma

    if market_up:
        # Pick best growth ETF by momentum
        best = None
        best_mom = -np.inf
        for t in growth_tickers:
            if t in prices.columns:
                series = prices[t].iloc[:idx + 1]
                if len(series) > mom_period:
                    m = series.iloc[-1] / series.iloc[-mom_period] - 1
                    if m > best_mom:
                        best_mom = m
                        best = t
        if best:
            return {best: 1.0}
    else:
        # Pick best bond by momentum
        best = None
        best_mom = -np.inf
        for t in bond_tickers:
            if t in prices.columns:
                series = prices[t].iloc[:idx + 1]
                if len(series) > 63:
                    m = series.iloc[-1] / series.iloc[-63] - 1
                    if m > best_mom:
                        best_mom = m
                        best = t
        if best:
            return {best: 1.0}

    return None


# =============================================================================
# STRATEGY 14: LEVERAGED-GROWTH MOMENTUM ROTATION
# Logic: Rotate among leveraged and unleveraged growth ETFs based on momentum,
# with strict drawdown protection.
# =============================================================================

def leveraged_growth_rotation(prices: pd.DataFrame, date: pd.Timestamp,
                               aggressive: list = None, defensive: list = None) -> dict:
    """Rotate among growth/tech ETFs with bond fallback."""
    if aggressive is None:
        aggressive = ["QQQ", "XLK", "VGT", "IGV", "SOXX"]
    if defensive is None:
        defensive = ["TLT", "IEF", "SHY"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Market regime check
    spy_up = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma50 = spy.rolling(50).mean().iloc[-1]
        sma200 = spy.rolling(200).mean().iloc[-1]
        spy_up = sma50 > sma200  # Golden cross

    if spy_up:
        # Pick best aggressive by composite momentum
        best = None
        best_score = -np.inf
        for t in aggressive:
            if t in prices.columns:
                series = prices[t].iloc[:idx + 1]
                if len(series) > 252:
                    r1m = series.iloc[-1] / series.iloc[-21] - 1
                    r3m = series.iloc[-1] / series.iloc[-63] - 1
                    r6m = series.iloc[-1] / series.iloc[-126] - 1
                    score = r1m * 0.4 + r3m * 0.35 + r6m * 0.25
                    if score > best_score:
                        best_score = score
                        best = t
        if best and best_score > 0:
            return {best: 1.0}

    # Defensive
    best_def = None
    best_def_mom = -np.inf
    for t in defensive:
        if t in prices.columns:
            series = prices[t].iloc[:idx + 1]
            if len(series) > 63:
                m = series.iloc[-1] / series.iloc[-63] - 1
                if m > best_def_mom:
                    best_def_mom = m
                    best_def = t
    if best_def:
        return {best_def: 1.0}
    return None


# =============================================================================
# STRATEGY 15: HYBRID MOMENTUM-QUALITY
# Logic: Combine price momentum with quality (profitability) factors.
# =============================================================================

def hybrid_momentum_quality(prices: pd.DataFrame, date: pd.Timestamp,
                             assets: list = None, bond_ticker: str = "AGG") -> dict:
    """Price momentum rotation among quality-tilted factor ETFs."""
    if assets is None:
        # Factor ETFs: quality, momentum, growth, value
        assets = ["QUAL", "MTUM", "VUG", "VLUE", "USMV", "SIZE"]

    available = [a for a in assets if a in prices.columns]
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    mom = {}
    for a in available:
        series = prices[a].iloc[:idx + 1]
        if len(series) > 252:
            r6 = series.iloc[-1] / series.iloc[-126] - 1
            r12 = series.iloc[-22] / series.iloc[-252] - 1
            mom[a] = 0.5 * r6 + 0.5 * r12

    if not mom:
        return None

    # Top 2 factors
    ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
    top = ranked[:2]

    # Market regime filter
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma200 = spy.rolling(200).mean().iloc[-1]
        if spy.iloc[-1] < sma200 * 0.97:  # 3% below SMA as buffer
            if bond_ticker in prices.columns:
                return {bond_ticker: 0.5, top[0][0]: 0.25, top[1][0]: 0.25}

    if len(top) >= 2:
        return {top[0][0]: 0.5, top[1][0]: 0.5}
    elif len(top) == 1:
        return {top[0][0]: 1.0}
    return None


# =============================================================================
# STRATEGY REGISTRY
# =============================================================================

STRATEGY_REGISTRY = {
    "dual_momentum": {
        "fn": dual_momentum_strategy,
        "tickers": ["SPY", "EFA", "AGG", "BIL"],
        "description": "Classic dual momentum (Antonacci): US vs Intl equities, bonds as haven",
    },
    "sector_momentum": {
        "fn": sector_momentum_strategy,
        "tickers": ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC", "AGG", "SPY"],
        "description": "Sector rotation: top-3 sectors by 12m momentum with 200-SMA trend filter",
    },
    "trend_following": {
        "fn": trend_following_strategy,
        "tickers": ["SPY", "EFA", "EEM", "TLT", "GLD", "DBC", "BIL"],
        "description": "Multi-asset trend following with inverse-vol weighting",
    },
    "vigilant_aa": {
        "fn": vigilant_asset_allocation,
        "tickers": ["SPY", "EFA", "EEM", "AGG", "SHY", "IEF", "LQD"],
        "description": "Vigilant Asset Allocation: breadth momentum crash protection",
    },
    "protective_aa": {
        "fn": protective_asset_allocation,
        "tickers": ["SPY", "QQQ", "IWM", "VGK", "EWJ", "EEM", "VNQ", "GLD", "TLT", "HYG", "LQD", "TIP", "SHY", "IEF", "BIL", "AGG"],
        "description": "Protective Asset Allocation: canary universe triggers crash protection",
    },
    "adaptive_aa": {
        "fn": adaptive_asset_allocation,
        "tickers": ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ", "QQQ"],
        "description": "Adaptive AA: momentum ranking + minimum variance optimization",
    },
    "risk_parity": {
        "fn": risk_parity_strategy,
        "tickers": ["SPY", "TLT", "GLD", "VNQ", "EFA"],
        "description": "Simplified risk parity: inverse-vol weighting with vol targeting",
    },
    "composite_mom_mr": {
        "fn": composite_momentum_mr,
        "tickers": ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC", "AGG", "SPY"],
        "description": "Sector momentum + mean reversion entry timing",
    },
    "bold_aa": {
        "fn": bold_asset_allocation,
        "tickers": ["SPY", "QQQ", "EFA", "EEM", "VNQ", "GLD", "TLT", "HYG", "SHY", "BIL", "IEF"],
        "description": "Bold AA: 100% in single best momentum asset with crash protection",
    },
    "accel_dual_momentum": {
        "fn": accelerating_dual_momentum,
        "tickers": ["SPY", "EFA", "AGG", "BIL"],
        "description": "Accelerating dual momentum: momentum + acceleration signal",
    },
    "multi_asset_mom_vol": {
        "fn": multi_asset_momentum_vol,
        "tickers": ["SPY", "QQQ", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ", "HYG", "SHY", "BIL"],
        "description": "Multi-asset momentum with vol targeting + drawdown control",
    },
    "growth_trend": {
        "fn": growth_trend_timing,
        "tickers": ["QQQ", "TLT"],
        "description": "Simple growth trend: QQQ above 200-SMA = long, else TLT",
    },
    "enhanced_growth_trend": {
        "fn": enhanced_growth_trend,
        "tickers": ["QQQ", "SPY", "VUG", "MTUM", "TLT", "IEF", "AGG"],
        "description": "Enhanced growth trend: best growth ETF when trending, best bond otherwise",
    },
    "leveraged_growth": {
        "fn": leveraged_growth_rotation,
        "tickers": ["QQQ", "XLK", "VGT", "IGV", "SOXX", "TLT", "IEF", "SHY", "SPY"],
        "description": "Growth/tech rotation with golden cross regime filter",
    },
    "hybrid_mom_quality": {
        "fn": hybrid_momentum_quality,
        "tickers": ["QUAL", "MTUM", "VUG", "VLUE", "USMV", "SIZE", "SPY", "AGG"],
        "description": "Factor ETF rotation: momentum among quality/growth/value/low-vol factors",
    },
}
