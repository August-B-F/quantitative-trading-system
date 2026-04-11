"""
Elite strategies targeting 2x SPY with consistency.
Key improvements over enhanced:
1. Better defensive assets (GLD + SHY instead of TLT which crashed in 2022)
2. Faster regime detection
3. Multiple timeframe confirmation
4. Ensemble approaches
"""

import numpy as np
import pandas as pd


def _best_by_momentum(prices, tickers, idx, period=63):
    """Helper: pick ticker with best momentum."""
    best, best_mom = None, -np.inf
    for t in tickers:
        if t in prices.columns:
            s = prices[t].iloc[:idx + 1]
            if len(s) > period:
                m = s.iloc[-1] / s.iloc[-period] - 1
                if m > best_mom:
                    best_mom = m
                    best = t
    return best, best_mom


def _weighted_mom(series):
    """Keller-style weighted momentum: 12*r1 + 4*r3 + 2*r6 + r12."""
    n = len(series)
    r1 = series.iloc[-1] / series.iloc[-21] - 1 if n > 21 else 0
    r3 = series.iloc[-1] / series.iloc[-63] - 1 if n > 63 else 0
    r6 = series.iloc[-1] / series.iloc[-126] - 1 if n > 126 else 0
    r12 = series.iloc[-1] / series.iloc[-252] - 1 if n > 252 else 0
    return 12 * r1 + 4 * r3 + 2 * r6 + r12


# =============================================================================
# ELITE 1: SOXX ROTATION WITH GOLD HEDGE
# Key insight: in 2022, both stocks and bonds fell. GLD was roughly flat.
# Use GLD + SHY blend as defensive instead of TLT.
# =============================================================================

def soxx_gold_hedge(prices: pd.DataFrame, date: pd.Timestamp,
                     growth: list = None, sma_period: int = 150,
                     mom_period: int = 42) -> dict:
    """SOXX/QQQ rotation with GLD+SHY defensive blend."""
    if growth is None:
        growth = ["SOXX", "QQQ"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    # Regime: SPY above SMA
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma = spy.rolling(sma_period).mean().iloc[-1]
        risk_on = spy.iloc[-1] > sma

    if risk_on:
        best, _ = _best_by_momentum(prices, growth, idx, mom_period)
        if best:
            return {best: 1.0}

    # Defensive: GLD + SHY blend (50/50)
    weights = {}
    for d, w in [("GLD", 0.5), ("SHY", 0.5)]:
        if d in prices.columns:
            weights[d] = w
    return weights if weights else None


# =============================================================================
# ELITE 2: MULTI-SIGNAL SOXX WITH ADAPTIVE DEFENSIVE
# 3 independent risk signals. Risk-off if 2+ are negative.
# Defensive: pick best of GLD, SHY, TLT by recent momentum.
# =============================================================================

def multi_signal_soxx(prices: pd.DataFrame, date: pd.Timestamp,
                       sma_short: int = 50, sma_long: int = 200) -> dict:
    """SOXX with 3-signal regime filter and adaptive defensive."""
    idx = prices.index.get_loc(date)
    if idx < max(sma_long, 252) + 20:
        return None

    if "SPY" not in prices.columns:
        return None

    spy = prices["SPY"].iloc[:idx + 1]

    # Signal 1: Price above long SMA
    sig1 = spy.iloc[-1] > spy.rolling(sma_long).mean().iloc[-1]
    # Signal 2: Short SMA above long SMA
    sig2 = spy.rolling(sma_short).mean().iloc[-1] > spy.rolling(sma_long).mean().iloc[-1]
    # Signal 3: 6-month return positive
    sig3 = spy.iloc[-1] / spy.iloc[-126] - 1 > 0 if len(spy) > 126 else False

    risk_score = sum([sig1, sig2, sig3])

    if risk_score >= 2:
        # Risk-on: best of SOXX, QQQ, XLK
        best, _ = _best_by_momentum(prices, ["SOXX", "QQQ", "XLK"], idx, 42)
        if best:
            return {best: 1.0}

    # Adaptive defensive: pick best of GLD, SHY, TLT, IEF
    best_def, _ = _best_by_momentum(prices, ["GLD", "SHY", "TLT", "IEF"], idx, 63)
    if best_def:
        return {best_def: 1.0}
    return None


# =============================================================================
# ELITE 3: SOXX TREND WITH DRAWDOWN STOP
# Hold SOXX in uptrend. Emergency exit if recent drawdown exceeds threshold.
# =============================================================================

def soxx_trend_ddstop(prices: pd.DataFrame, date: pd.Timestamp,
                       sma_period: int = 150, dd_threshold: float = -0.12) -> dict:
    """SOXX trend following with drawdown-based emergency stop."""
    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    growth = ["SOXX", "QQQ"]
    available = [g for g in growth if g in prices.columns]
    if not available:
        return None

    # Check SPY regime
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma = spy.rolling(sma_period).mean().iloc[-1]
        risk_on = spy.iloc[-1] > sma

        # Drawdown stop: if SPY down more than threshold from recent high
        recent_high = spy.iloc[-63:].max()
        dd = (spy.iloc[-1] - recent_high) / recent_high
        if dd < dd_threshold:
            risk_on = False

    if risk_on:
        best, _ = _best_by_momentum(prices, available, idx, 42)
        if best:
            return {best: 1.0}

    # Defensive
    best_def, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
    if best_def:
        return {best_def: 1.0}
    return None


# =============================================================================
# ELITE 4: CANARY GROWTH WITH GOLD FALLBACK
# PAA-style canary (EEM, AGG) but use GLD as defensive in rising rate env.
# =============================================================================

def canary_growth_gold(prices: pd.DataFrame, date: pd.Timestamp,
                        growth: list = None) -> dict:
    """Canary-based protection with adaptive defensive (GLD vs bonds)."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Canary check
    canary_bad = 0
    for c in ["EEM", "AGG"]:
        if c in prices.columns:
            s = prices[c].iloc[:idx + 1]
            if _weighted_mom(s) < 0:
                canary_bad += 1

    if canary_bad == 0:
        # All clear: best growth
        best, _ = _best_by_momentum(prices, growth, idx, 42)
        if best:
            return {best: 1.0}
    elif canary_bad == 1:
        # Partial: 50% growth, 50% defensive
        best_g, _ = _best_by_momentum(prices, growth, idx, 42)
        best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
        weights = {}
        if best_g:
            weights[best_g] = 0.5
        if best_d:
            weights[best_d] = 0.5
        return weights if weights else None
    else:
        # Full defensive
        best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF", "TLT"], idx, 63)
        if best_d:
            return {best_d: 1.0}

    return None


# =============================================================================
# ELITE 5: AGGRESSIVE MOMENTUM ROTATION (Growth + Sectors)
# Rotate among growth ETFs AND best sectors. Wider universe = more opportunities.
# =============================================================================

def aggressive_rotation(prices: pd.DataFrame, date: pd.Timestamp,
                         universe: list = None, top_n: int = 2,
                         sma_period: int = 200) -> dict:
    """Aggressive rotation among growth + sector ETFs with crash protection."""
    if universe is None:
        universe = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLY", "XLI"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    # Regime check
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma = spy.rolling(sma_period).mean().iloc[-1]
        risk_on = spy.iloc[-1] > sma

    if risk_on:
        available = [u for u in universe if u in prices.columns]
        mom = {}
        for t in available:
            s = prices[t].iloc[:idx + 1]
            if len(s) > 252:
                r3 = s.iloc[-1] / s.iloc[-63] - 1
                r6 = s.iloc[-1] / s.iloc[-126] - 1
                mom[t] = 0.6 * r3 + 0.4 * r6

        if len(mom) >= top_n:
            ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
            top = ranked[:top_n]
            # Only include if positive momentum
            top = [(t, m) for t, m in top if m > 0]
            if top:
                per_asset = 1.0 / len(top)
                return {t: per_asset for t, _ in top}

    best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
    if best_d:
        return {best_d: 1.0}
    return None


# =============================================================================
# ELITE 6: COMPOUND MOMENTUM (Mixing Fast and Slow)
# Use fast momentum for asset selection, slow for regime.
# =============================================================================

def compound_momentum(prices: pd.DataFrame, date: pd.Timestamp,
                       growth: list = None, fast_period: int = 21,
                       slow_period: int = 252) -> dict:
    """Fast momentum for selection, slow for regime confirmation."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK", "VGT"]

    idx = prices.index.get_loc(date)
    if idx < slow_period + 20:
        return None

    # Slow regime: 12-month SPY return
    regime_ok = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        ret_12m = spy.iloc[-1] / spy.iloc[-slow_period] - 1
        sma200 = spy.rolling(200).mean().iloc[-1]
        regime_ok = ret_12m > 0 or spy.iloc[-1] > sma200

    if regime_ok:
        # Fast momentum selection among growth
        available = [g for g in growth if g in prices.columns]
        if available:
            best, best_mom = _best_by_momentum(prices, available, idx, fast_period)
            if best:
                return {best: 1.0}

    best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
    if best_d:
        return {best_d: 1.0}
    return None


# =============================================================================
# ELITE 7: VOLATILITY-ADJUSTED GROWTH ROTATION
# Scale position size by inverse vol. More exposure in calm markets.
# =============================================================================

def vol_adjusted_growth(prices: pd.DataFrame, date: pd.Timestamp,
                         growth: list = None, target_vol: float = 0.20,
                         max_exposure: float = 1.0) -> dict:
    """Growth rotation with vol-based position sizing."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Regime
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma200 = spy.rolling(200).mean().iloc[-1]
        risk_on = spy.iloc[-1] > sma200

    if not risk_on:
        best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
        return {best_d: 1.0} if best_d else None

    # Best growth ETF
    best, _ = _best_by_momentum(prices, growth, idx, 42)
    if not best:
        return None

    # Vol-adjust position size
    series = prices[best].iloc[:idx + 1]
    rets = series.pct_change().dropna()
    if len(rets) >= 21:
        recent_vol = rets.iloc[-21:].std() * np.sqrt(252)
        if recent_vol > 0:
            exposure = min(target_vol / recent_vol, max_exposure)
        else:
            exposure = max_exposure
    else:
        exposure = max_exposure

    weights = {best: exposure}
    remainder = 1.0 - exposure
    if remainder > 0.05:
        # Put remainder in SHY
        if "SHY" in prices.columns:
            weights["SHY"] = remainder
    return weights


# =============================================================================
# ELITE 8: HYBRID ENSEMBLE
# Combine signals from multiple sub-strategies. More robust.
# =============================================================================

def hybrid_ensemble(prices: pd.DataFrame, date: pd.Timestamp) -> dict:
    """Ensemble of 4 strategies voting on regime + asset selection."""
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Collect votes for risk-on
    risk_votes = 0
    total_votes = 0

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None

    if spy is not None and len(spy) > 252:
        # Vote 1: Price > 200 SMA
        if spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]:
            risk_votes += 1
        total_votes += 1

        # Vote 2: 50 > 200 SMA (golden cross)
        if spy.rolling(50).mean().iloc[-1] > spy.rolling(200).mean().iloc[-1]:
            risk_votes += 1
        total_votes += 1

        # Vote 3: 6-month return > 0
        if spy.iloc[-1] / spy.iloc[-126] - 1 > 0:
            risk_votes += 1
        total_votes += 1

        # Vote 4: 3-month drawdown not severe
        recent_high = spy.iloc[-63:].max()
        dd = (spy.iloc[-1] - recent_high) / recent_high
        if dd > -0.10:
            risk_votes += 1
        total_votes += 1

        # Vote 5: Canary (EEM momentum)
        if "EEM" in prices.columns:
            eem = prices["EEM"].iloc[:idx + 1]
            if _weighted_mom(eem) > 0:
                risk_votes += 1
            total_votes += 1

    if total_votes == 0:
        return None

    risk_fraction = risk_votes / total_votes

    if risk_fraction >= 0.6:
        # Aggressive: best growth ETF
        best, _ = _best_by_momentum(prices, ["SOXX", "QQQ", "XLK", "VGT"], idx, 42)
        if best:
            return {best: risk_fraction, "GLD": 1.0 - risk_fraction} if "GLD" in prices.columns else {best: 1.0}
    elif risk_fraction >= 0.4:
        # Mixed
        best_g, _ = _best_by_momentum(prices, ["SOXX", "QQQ", "XLK"], idx, 42)
        best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
        weights = {}
        if best_g:
            weights[best_g] = 0.4
        if best_d:
            weights[best_d] = 0.6
        return weights if weights else None
    else:
        # Defensive
        best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
        return {best_d: 1.0} if best_d else None


# =============================================================================
# ELITE 9: ABSOLUTE + RELATIVE MOMENTUM ON GROWTH
# Absolute: only invest if growth > cash (SHY). Relative: pick best growth.
# =============================================================================

def abs_rel_growth_momentum(prices: pd.DataFrame, date: pd.Timestamp,
                              growth: list = None, lookback: int = 126,
                              cash_ticker: str = "SHY") -> dict:
    """Classic absolute + relative momentum applied to growth universe."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK", "VGT", "IGV"]

    idx = prices.index.get_loc(date)
    if idx < max(lookback, 252):
        return None

    # Compute momentum for all assets including cash proxy
    mom = {}
    for t in growth + [cash_ticker]:
        if t in prices.columns:
            s = prices[t].iloc[:idx + 1]
            if len(s) > lookback:
                mom[t] = s.iloc[-1] / s.iloc[-lookback] - 1

    cash_mom = mom.get(cash_ticker, 0)

    # Find best growth asset
    growth_mom = {t: m for t, m in mom.items() if t in growth}
    if not growth_mom:
        return None

    best = max(growth_mom, key=growth_mom.get)
    best_mom = growth_mom[best]

    # Absolute momentum: best growth must beat cash
    if best_mom > cash_mom:
        return {best: 1.0}
    else:
        # Go to defensive
        best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
        return {best_d: 1.0} if best_d else {cash_ticker: 1.0}


# =============================================================================
# ELITE 10: SOXX BREAKOUT TREND
# Hold SOXX when making new 3-month highs (breakout signal).
# =============================================================================

def soxx_breakout(prices: pd.DataFrame, date: pd.Timestamp,
                   ticker: str = "SOXX", lookback: int = 63) -> dict:
    """Hold SOXX when price is within 5% of N-day high (breakout)."""
    if ticker not in prices.columns:
        return None

    idx = prices.index.get_loc(date)
    if idx < max(lookback, 252):
        return None

    series = prices[ticker].iloc[:idx + 1]
    recent_high = series.iloc[-lookback:].max()
    current = series.iloc[-1]

    # Within 5% of recent high = breakout/uptrend
    near_high = current > recent_high * 0.95

    # Also check broader regime
    spy_ok = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        if len(spy) > 200:
            spy_ok = spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]

    if near_high and spy_ok:
        return {ticker: 1.0}

    best_d, _ = _best_by_momentum(prices, ["GLD", "SHY", "IEF"], idx, 63)
    return {best_d: 1.0} if best_d else None


# =============================================================================
# ELITE 11: MAXIMUM GROWTH COMPOSITE
# Ultimate concentration: pick single best from SOXX, QQQ, XLK.
# Triple confirmation: SMA + momentum + drawdown check.
# Use GLD/SHY as defensive. No TLT.
# =============================================================================

def max_growth_composite(prices: pd.DataFrame, date: pd.Timestamp,
                          growth: list = None, sma_period: int = 150,
                          dd_limit: float = -0.10) -> dict:
    """Maximum growth concentration with triple-confirmed regime filter."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    if "SPY" not in prices.columns:
        return None

    spy = prices["SPY"].iloc[:idx + 1]

    # Triple confirmation
    above_sma = spy.iloc[-1] > spy.rolling(sma_period).mean().iloc[-1]
    positive_mom = spy.iloc[-1] / spy.iloc[-126] - 1 > 0 if len(spy) > 126 else False
    recent_high = spy.iloc[-42:].max()
    dd = (spy.iloc[-1] - recent_high) / recent_high
    no_crash = dd > dd_limit

    if above_sma and positive_mom and no_crash:
        # Best growth by composite score
        available = [g for g in growth if g in prices.columns]
        scores = {}
        for t in available:
            s = prices[t].iloc[:idx + 1]
            if len(s) > 252:
                r1m = s.iloc[-1] / s.iloc[-21] - 1
                r3m = s.iloc[-1] / s.iloc[-63] - 1
                r6m = s.iloc[-1] / s.iloc[-126] - 1
                scores[t] = 0.4 * r1m + 0.35 * r3m + 0.25 * r6m

        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return {best: 1.0}

    # Defensive: best of GLD and SHY
    best_d, _ = _best_by_momentum(prices, ["GLD", "SHY"], idx, 63)
    return {best_d: 1.0} if best_d else None


# =============================================================================
# ELITE 12: ULTIMATE STRATEGY - Combines everything learned
# Fast regime, best growth, gold/cash defensive, drawdown protection
# =============================================================================

def ultimate_strategy(prices: pd.DataFrame, date: pd.Timestamp) -> dict:
    """Ultimate strategy: all learnings combined."""
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    spy = prices["SPY"].iloc[:idx + 1] if "SPY" in prices.columns else None
    if spy is None or len(spy) < 252:
        return None

    # Regime score (0-5)
    score = 0

    # 1. Price > 150 SMA
    if spy.iloc[-1] > spy.rolling(150).mean().iloc[-1]:
        score += 1
    # 2. 50 SMA > 150 SMA
    if spy.rolling(50).mean().iloc[-1] > spy.rolling(150).mean().iloc[-1]:
        score += 1
    # 3. 3-month return positive
    if spy.iloc[-1] / spy.iloc[-63] - 1 > 0:
        score += 1
    # 4. Not in drawdown (> -8% from 42-day high)
    recent_high = spy.iloc[-42:].max()
    if (spy.iloc[-1] - recent_high) / recent_high > -0.08:
        score += 1
    # 5. EEM canary positive
    if "EEM" in prices.columns:
        eem = prices["EEM"].iloc[:idx + 1]
        if len(eem) > 63 and eem.iloc[-1] / eem.iloc[-63] - 1 > 0:
            score += 1

    growth = ["SOXX", "QQQ", "XLK", "VGT"]
    defensive = ["GLD", "SHY"]

    if score >= 4:
        # Strong bullish: 100% best growth
        best, _ = _best_by_momentum(prices, growth, idx, 42)
        return {best: 1.0} if best else None
    elif score >= 3:
        # Moderate: 80% growth, 20% defensive
        best_g, _ = _best_by_momentum(prices, growth, idx, 42)
        best_d, _ = _best_by_momentum(prices, defensive, idx, 63)
        w = {}
        if best_g:
            w[best_g] = 0.8
        if best_d:
            w[best_d] = 0.2
        return w if w else None
    elif score >= 2:
        # Cautious: 40% growth, 60% defensive
        best_g, _ = _best_by_momentum(prices, growth, idx, 42)
        best_d, _ = _best_by_momentum(prices, defensive, idx, 63)
        w = {}
        if best_g:
            w[best_g] = 0.4
        if best_d:
            w[best_d] = 0.6
        return w if w else None
    else:
        # Full defensive
        best_d, _ = _best_by_momentum(prices, defensive, idx, 63)
        return {best_d: 1.0} if best_d else None


# =============================================================================
# REGISTRY
# =============================================================================

ELITE_REGISTRY = {
    "soxx_gold_hedge": {
        "fn": soxx_gold_hedge,
        "tickers": ["SOXX", "QQQ", "GLD", "SHY", "SPY"],
    },
    "multi_signal_soxx": {
        "fn": multi_signal_soxx,
        "tickers": ["SOXX", "QQQ", "XLK", "GLD", "SHY", "TLT", "IEF", "SPY"],
    },
    "soxx_trend_ddstop": {
        "fn": soxx_trend_ddstop,
        "tickers": ["SOXX", "QQQ", "GLD", "SHY", "IEF", "SPY"],
    },
    "canary_growth_gold": {
        "fn": canary_growth_gold,
        "tickers": ["SOXX", "QQQ", "XLK", "EEM", "AGG", "GLD", "SHY", "IEF", "TLT"],
    },
    "aggressive_rotation": {
        "fn": aggressive_rotation,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLY", "XLI", "GLD", "SHY", "IEF", "SPY"],
    },
    "compound_momentum": {
        "fn": compound_momentum,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "GLD", "SHY", "IEF", "SPY"],
    },
    "vol_adjusted_growth": {
        "fn": vol_adjusted_growth,
        "tickers": ["SOXX", "QQQ", "XLK", "GLD", "SHY", "IEF", "SPY"],
    },
    "hybrid_ensemble": {
        "fn": hybrid_ensemble,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "EEM", "GLD", "SHY", "IEF", "SPY"],
    },
    "abs_rel_growth_mom": {
        "fn": abs_rel_growth_momentum,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "IGV", "GLD", "SHY", "IEF"],
    },
    "soxx_breakout": {
        "fn": soxx_breakout,
        "tickers": ["SOXX", "GLD", "SHY", "IEF", "SPY"],
    },
    "max_growth_composite": {
        "fn": max_growth_composite,
        "tickers": ["SOXX", "QQQ", "XLK", "GLD", "SHY", "SPY"],
    },
    "ultimate_strategy": {
        "fn": ultimate_strategy,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "EEM", "GLD", "SHY", "SPY"],
    },
}
