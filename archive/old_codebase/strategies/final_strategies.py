"""
Final iteration strategies. Key insights from previous rounds:
1. 2022 killed all strategies (stocks, bonds, and gold all fell)
2. SHY was the only safe asset in 2022 (short treasury)
3. XLE (energy) rallied 59% in 2022 - could hedge
4. Need faster crash detection (monthly rebal is too slow for crashes)
5. Best base: abs/rel momentum on SOXX/QQQ with 63-day lookback

New approach: FAST crash detection + sector rotation including energy hedge.
"""

import numpy as np
import pandas as pd


def _best_mom(prices, tickers, idx, period=42):
    """Pick ticker with best momentum."""
    best, best_m = None, -np.inf
    for t in tickers:
        if t in prices.columns:
            s = prices[t].iloc[:idx + 1]
            if len(s) > period:
                m = s.iloc[-1] / s.iloc[-period] - 1
                if m > best_m:
                    best_m = m
                    best = t
    return best, best_m


def _wmom(series):
    """Keller weighted momentum."""
    n = len(series)
    r1 = series.iloc[-1] / series.iloc[-21] - 1 if n > 21 else 0
    r3 = series.iloc[-1] / series.iloc[-63] - 1 if n > 63 else 0
    r6 = series.iloc[-1] / series.iloc[-126] - 1 if n > 126 else 0
    r12 = series.iloc[-1] / series.iloc[-252] - 1 if n > 252 else 0
    return 12 * r1 + 4 * r3 + 2 * r6 + r12


# =============================================================================
# FINAL 1: GROWTH + ENERGY ROTATION
# In bull: hold best growth (SOXX/QQQ/XLK)
# In bear: hold XLE (energy) if it has positive momentum, else SHY
# This would have held XLE in 2022 when energy was booming
# =============================================================================

def growth_energy_rotation(prices: pd.DataFrame, date: pd.Timestamp,
                            growth: list = None, energy: str = "XLE",
                            sma_period: int = 150) -> dict:
    """Growth in bull markets, energy/SHY in bear markets."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None
    if spy is None:
        return None

    # Regime
    above_sma = spy.iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]
    mom_6m = spy.iloc[-1] / spy.iloc[-126] - 1 if len(spy) > 126 else 0
    risk_on = above_sma and mom_6m > -0.05

    if risk_on:
        best, _ = _best_mom(prices, growth, idx, 42)
        return {best: 1.0} if best else None
    else:
        # Defensive: check if energy has positive momentum
        if energy in prices.columns:
            e = prices[energy].iloc[:idx + 1]
            e_mom = e.iloc[-1] / e.iloc[-63] - 1 if len(e) > 63 else 0
            e_sma = e.rolling(sma_period).mean().iloc[-1]
            if e_mom > 0 and e.iloc[-1] > e_sma:
                return {energy: 1.0}

        # Fallback: SHY (only truly safe asset in 2022)
        if "SHY" in prices.columns:
            return {"SHY": 1.0}
        return None


# =============================================================================
# FINAL 2: MULTI-REGIME ROTATION
# 3 regimes: growth bull, commodity bull, defensive
# Growth bull: SOXX/QQQ
# Commodity bull (inflation): XLE/GLD
# Defensive: SHY
# =============================================================================

def multi_regime_rotation(prices: pd.DataFrame, date: pd.Timestamp,
                           sma_period: int = 150) -> dict:
    """3-regime rotation: growth / commodity / defensive."""
    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None
    if spy is None:
        return None

    # Growth regime: SPY above SMA and positive 3-month momentum
    spy_above_sma = spy.iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]
    spy_mom_3m = spy.iloc[-1] / spy.iloc[-63] - 1 if len(spy) > 63 else 0

    if spy_above_sma and spy_mom_3m > 0:
        # Growth mode: best growth ETF
        best, _ = _best_mom(prices, ["SOXX", "QQQ", "XLK"], idx, 42)
        return {best: 1.0} if best else None

    # Check commodity/inflation regime
    commodity_bullish = False
    for c in ["XLE", "GLD"]:
        if c in prices.columns:
            s = prices[c].iloc[:idx + 1]
            if len(s) > sma_period:
                if s.iloc[-1] > s.rolling(sma_period).mean().iloc[-1]:
                    commodity_bullish = True
                    break

    if commodity_bullish:
        # Pick best commodity/inflation hedge
        best, bm = _best_mom(prices, ["XLE", "GLD"], idx, 63)
        if best and bm > 0:
            return {best: 1.0}

    # Pure defensive
    return {"SHY": 1.0} if "SHY" in prices.columns else None


# =============================================================================
# FINAL 3: ABSOLUTE MOMENTUM GROWTH + ENERGY HEDGE
# Abs momentum on growth ETFs. When abs momentum is negative, check energy.
# =============================================================================

def abs_mom_growth_energy(prices: pd.DataFrame, date: pd.Timestamp,
                           growth: list = None, lookback: int = 63,
                           cash: str = "SHY") -> dict:
    """Absolute momentum on growth, with energy as alternative."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK", "VGT", "IGV"]

    idx = prices.index.get_loc(date)
    if idx < max(lookback, 252):
        return None

    # Cash momentum
    cash_mom = 0
    if cash in prices.columns:
        s = prices[cash].iloc[:idx + 1]
        if len(s) > lookback:
            cash_mom = s.iloc[-1] / s.iloc[-lookback] - 1

    # Growth momentum
    growth_scores = {}
    for t in growth:
        if t in prices.columns:
            s = prices[t].iloc[:idx + 1]
            if len(s) > lookback:
                growth_scores[t] = s.iloc[-1] / s.iloc[-lookback] - 1

    if growth_scores:
        best_growth = max(growth_scores, key=growth_scores.get)
        if growth_scores[best_growth] > cash_mom:
            return {best_growth: 1.0}

    # Growth failed absolute momentum. Check energy/commodities.
    alt_scores = {}
    for t in ["XLE", "GLD"]:
        if t in prices.columns:
            s = prices[t].iloc[:idx + 1]
            if len(s) > lookback:
                m = s.iloc[-1] / s.iloc[-lookback] - 1
                if m > cash_mom:
                    alt_scores[t] = m

    if alt_scores:
        best_alt = max(alt_scores, key=alt_scores.get)
        return {best_alt: 1.0}

    return {cash: 1.0}


# =============================================================================
# FINAL 4: FAST DRAWDOWN DETECTION + GROWTH
# Instead of SMA-based regime, use drawdown from recent high.
# If SPY drops > 8% from 42-day high: risk-off.
# This catches crashes much faster than SMA crossovers.
# =============================================================================

def fast_dd_growth(prices: pd.DataFrame, date: pd.Timestamp,
                    growth: list = None, dd_threshold: float = -0.08,
                    dd_window: int = 42) -> dict:
    """Growth rotation with fast drawdown-based crash detection."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None
    if spy is None:
        return None

    # Fast drawdown check
    recent_high = spy.iloc[-dd_window:].max()
    dd = (spy.iloc[-1] - recent_high) / recent_high

    # Also check if recovering (price above 50-day SMA after drawdown)
    sma50 = spy.rolling(50).mean().iloc[-1]
    recovering = spy.iloc[-1] > sma50

    if dd > dd_threshold or recovering:
        # Risk-on
        best, _ = _best_mom(prices, growth, idx, 42)
        return {best: 1.0} if best else None
    else:
        # Risk-off: XLE if bullish, else SHY
        if "XLE" in prices.columns:
            xle = prices["XLE"].iloc[:idx + 1]
            xle_mom = xle.iloc[-1] / xle.iloc[-63] - 1 if len(xle) > 63 else 0
            if xle_mom > 0:
                return {"XLE": 1.0}
        return {"SHY": 1.0} if "SHY" in prices.columns else None


# =============================================================================
# FINAL 5: ULTIMATE FINAL - All Learnings Combined
# 1. Fast drawdown detection (catches 2022 faster)
# 2. Energy sector as inflation hedge (worked in 2022)
# 3. SHY as pure defensive (only safe asset in 2022)
# 4. Growth concentration (SOXX/QQQ/XLK best performers)
# 5. 42-day momentum for asset selection (optimal from sweeps)
# =============================================================================

def ultimate_final(prices: pd.DataFrame, date: pd.Timestamp,
                    growth: list = None, sma_period: int = 150,
                    dd_threshold: float = -0.08) -> dict:
    """All learnings combined: growth + energy hedge + fast crash detection."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None
    if spy is None:
        return None

    # Multi-layer regime detection
    above_sma = spy.iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]
    golden_cross = spy.rolling(50).mean().iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]
    recent_high = spy.iloc[-42:].max()
    dd = (spy.iloc[-1] - recent_high) / recent_high
    no_crash = dd > dd_threshold
    mom_3m = spy.iloc[-1] / spy.iloc[-63] - 1 if len(spy) > 63 else 0

    regime_score = sum([above_sma, golden_cross, no_crash, mom_3m > 0])

    if regime_score >= 3:
        # Strong bull: 100% best growth
        best, _ = _best_mom(prices, growth, idx, 42)
        return {best: 1.0} if best else None

    elif regime_score == 2:
        # Mixed: check if growth or commodities are working
        best_g, g_mom = _best_mom(prices, growth, idx, 42)
        best_c, c_mom = _best_mom(prices, ["XLE", "GLD"], idx, 63)

        if g_mom > 0 and g_mom > c_mom:
            return {best_g: 0.7, "SHY": 0.3} if "SHY" in prices.columns else {best_g: 1.0}
        elif c_mom > 0:
            return {best_c: 0.7, "SHY": 0.3} if "SHY" in prices.columns else {best_c: 1.0}
        else:
            return {"SHY": 1.0} if "SHY" in prices.columns else None

    else:
        # Bear: defensive with possible energy hedge
        if "XLE" in prices.columns:
            xle = prices["XLE"].iloc[:idx + 1]
            xle_mom = xle.iloc[-1] / xle.iloc[-63] - 1 if len(xle) > 63 else 0
            if xle_mom > 0.1:  # Strong energy momentum
                return {"XLE": 0.6, "SHY": 0.4}

        return {"SHY": 1.0} if "SHY" in prices.columns else None


# =============================================================================
# FINAL 6: ABSOLUTE MOMENTUM GROWTH + ENERGY (BEST VERSION)
# Optimized version of abs_mom_growth_energy with tuned parameters
# =============================================================================

def abs_mom_optimized(prices: pd.DataFrame, date: pd.Timestamp,
                       growth: list = None, lookback: int = 63) -> dict:
    """Optimized absolute momentum across growth + energy universe."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK", "VGT", "IGV"]

    all_assets = growth + ["XLE", "GLD"]
    idx = prices.index.get_loc(date)
    if idx < max(lookback, 252):
        return None

    cash = "SHY"
    cash_mom = 0
    if cash in prices.columns:
        s = prices[cash].iloc[:idx + 1]
        if len(s) > lookback:
            cash_mom = s.iloc[-1] / s.iloc[-lookback] - 1

    # Compute momentum for all assets
    scores = {}
    for t in all_assets:
        if t in prices.columns:
            s = prices[t].iloc[:idx + 1]
            if len(s) > lookback:
                m = s.iloc[-1] / s.iloc[-lookback] - 1
                if m > cash_mom:  # Must beat cash (absolute momentum)
                    scores[t] = m

    if scores:
        best = max(scores, key=scores.get)
        return {best: 1.0}

    return {cash: 1.0}


# =============================================================================
# FINAL 7: RISK-ON/OFF WITH SECTOR DIVERSIFICATION
# In risk-on: split between top-2 growth ETFs (reduces concentration risk)
# In risk-off: XLE if trending, else SHY
# =============================================================================

def diversified_growth_energy(prices: pd.DataFrame, date: pd.Timestamp,
                                growth: list = None, top_n: int = 2,
                                sma_period: int = 150) -> dict:
    """Diversified growth (top-2) in bull, energy/SHY in bear."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK", "VGT"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None
    if spy is None:
        return None

    above_sma = spy.iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]
    mom_pos = spy.iloc[-1] / spy.iloc[-63] - 1 > 0 if len(spy) > 63 else False

    if above_sma or mom_pos:
        # Top-N growth by momentum
        scores = {}
        for t in growth:
            if t in prices.columns:
                s = prices[t].iloc[:idx + 1]
                if len(s) > 63:
                    scores[t] = s.iloc[-1] / s.iloc[-42] - 1
        if scores:
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top = ranked[:top_n]
            # Only positive momentum
            top = [(t, m) for t, m in top if m > 0]
            if top:
                w = 1.0 / len(top)
                return {t: w for t, _ in top}

    # Bear: energy or SHY
    if "XLE" in prices.columns:
        xle = prices["XLE"].iloc[:idx + 1]
        xle_sma = xle.rolling(sma_period).mean().iloc[-1] if len(xle) > sma_period else 0
        if xle.iloc[-1] > xle_sma:
            return {"XLE": 1.0}
    return {"SHY": 1.0} if "SHY" in prices.columns else None


# =============================================================================
# FINAL 8: PURE SECTOR ROTATION (GROWTH + ENERGY + DEFENSIVE)
# Rotate among ALL sectors including energy. When energy leads = inflation.
# When tech leads = growth. When utilities lead = defensive.
# =============================================================================

def broad_sector_rotation(prices: pd.DataFrame, date: pd.Timestamp,
                           top_n: int = 2, sma_period: int = 200) -> dict:
    """Broad sector rotation including energy/commodity sectors."""
    sectors = ["SOXX", "QQQ", "XLK", "XLE", "XLI", "XLY", "XLF", "VGT", "GLD"]
    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    # SPY trend filter
    spy_ok = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        spy_ok = spy.iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]

    available = [s for s in sectors if s in prices.columns]
    if not available:
        return None

    scores = {}
    for t in available:
        s = prices[t].iloc[:idx + 1]
        if len(s) > 252:
            r3m = s.iloc[-1] / s.iloc[-63] - 1
            r6m = s.iloc[-1] / s.iloc[-126] - 1
            # Trend filter: above own SMA
            above_own_sma = s.iloc[-1] > s.rolling(sma_period).mean().iloc[-1]
            if above_own_sma:
                scores[t] = 0.6 * r3m + 0.4 * r6m

    if scores and (spy_ok or any(s in scores for s in ["XLE", "GLD"])):
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = ranked[:top_n]
        top = [(t, m) for t, m in top if m > 0]
        if top:
            w = 1.0 / len(top)
            return {t: w for t, _ in top}

    return {"SHY": 1.0} if "SHY" in prices.columns else None


# =============================================================================
# REGISTRY
# =============================================================================

FINAL_REGISTRY = {
    "growth_energy_rot": {
        "fn": growth_energy_rotation,
        "tickers": ["SOXX", "QQQ", "XLK", "XLE", "GLD", "SHY", "SPY"],
    },
    "multi_regime_rot": {
        "fn": multi_regime_rotation,
        "tickers": ["SOXX", "QQQ", "XLK", "XLE", "GLD", "SHY", "SPY"],
    },
    "abs_mom_growth_energy": {
        "fn": abs_mom_growth_energy,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"],
    },
    "fast_dd_growth": {
        "fn": fast_dd_growth,
        "tickers": ["SOXX", "QQQ", "XLK", "XLE", "SHY", "SPY"],
    },
    "ultimate_final": {
        "fn": ultimate_final,
        "tickers": ["SOXX", "QQQ", "XLK", "XLE", "GLD", "SHY", "SPY"],
    },
    "abs_mom_optimized": {
        "fn": abs_mom_optimized,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"],
    },
    "diversified_growth_energy": {
        "fn": diversified_growth_energy,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "XLE", "SHY", "SPY"],
    },
    "broad_sector_rot": {
        "fn": broad_sector_rotation,
        "tickers": ["SOXX", "QQQ", "XLK", "XLE", "XLI", "XLY", "XLF", "VGT", "GLD", "SHY", "SPY"],
    },
}
