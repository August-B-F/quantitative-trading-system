"""
Enhanced strategies targeting 2x SPY returns with consistency.
Key insight: SOXX/QQQ/XLK returned 4-5x over 2018-2025.
Strategy: concentrate in high-growth with fast crash protection.
"""

import numpy as np
import pandas as pd


# =============================================================================
# STRATEGY E1: CONCENTRATED TECH ROTATION WITH MULTI-SIGNAL PROTECTION
# Logic: Rotate among QQQ/SOXX/XLK/VGT, crash protect with TLT/IEF.
# Uses dual trend signal: price vs SMA AND momentum sign.
# =============================================================================

def concentrated_tech_rotation(prices: pd.DataFrame, date: pd.Timestamp,
                                aggressive: list = None, defensive: list = None,
                                sma_fast: int = 50, sma_slow: int = 200,
                                mom_period: int = 126) -> dict:
    """Pick best tech/growth ETF when market trending up, best bond otherwise."""
    if aggressive is None:
        aggressive = ["SOXX", "QQQ", "XLK", "VGT", "IGV"]
    if defensive is None:
        defensive = ["TLT", "IEF", "SHY"]

    available_agg = [a for a in aggressive if a in prices.columns]
    available_def = [d for d in defensive if d in prices.columns]
    idx = prices.index.get_loc(date)
    if idx < sma_slow + 20:
        return None

    # Multi-signal regime detection on SPY
    regime_bullish = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma_f = spy.rolling(sma_fast).mean().iloc[-1]
        sma_s = spy.rolling(sma_slow).mean().iloc[-1]
        price = spy.iloc[-1]

        # Bullish: price > fast SMA AND fast SMA > slow SMA (golden cross)
        # or price > slow SMA with strong momentum
        mom_6m = spy.iloc[-1] / spy.iloc[-mom_period] - 1 if len(spy) > mom_period else 0

        regime_bullish = (price > sma_f and sma_f > sma_s) or (price > sma_s and mom_6m > 0.05)

    if regime_bullish and available_agg:
        # Pick best aggressive by composite momentum
        best = None
        best_score = -np.inf
        for t in available_agg:
            series = prices[t].iloc[:idx + 1]
            if len(series) > 252:
                r1m = series.iloc[-1] / series.iloc[-21] - 1
                r3m = series.iloc[-1] / series.iloc[-63] - 1
                r6m = series.iloc[-1] / series.iloc[-126] - 1
                # Heavier weight on recent momentum
                score = r1m * 0.5 + r3m * 0.3 + r6m * 0.2
                if score > best_score:
                    best_score = score
                    best = t
        if best:
            return {best: 1.0}

    # Defensive: pick best performing bond
    if available_def:
        best_def = None
        best_def_score = -np.inf
        for t in available_def:
            series = prices[t].iloc[:idx + 1]
            if len(series) > 63:
                score = series.iloc[-1] / series.iloc[-63] - 1
                if score > best_def_score:
                    best_def_score = score
                    best_def = t
        if best_def:
            return {best_def: 1.0}

    return None


# =============================================================================
# STRATEGY E2: SOXX/QQQ MOMENTUM SWITCH
# Logic: Simple but effective. Hold SOXX or QQQ (whichever has better momentum).
# Crash protection: if both below SMA, go to TLT.
# =============================================================================

def soxx_qqq_switch(prices: pd.DataFrame, date: pd.Timestamp,
                     sma_period: int = 150, mom_period: int = 63) -> dict:
    """Switch between SOXX and QQQ based on momentum, TLT on crash."""
    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    soxx_ok = "SOXX" in prices.columns
    qqq_ok = "QQQ" in prices.columns
    tlt_ok = "TLT" in prices.columns

    candidates = {}
    for ticker in ["SOXX", "QQQ"]:
        if ticker in prices.columns:
            series = prices[ticker].iloc[:idx + 1]
            sma = series.rolling(sma_period).mean().iloc[-1]
            mom = series.iloc[-1] / series.iloc[-mom_period] - 1 if len(series) > mom_period else 0
            above_sma = series.iloc[-1] > sma
            candidates[ticker] = {"mom": mom, "above_sma": above_sma}

    # Filter to those above SMA
    bullish = {t: v for t, v in candidates.items() if v["above_sma"]}

    if bullish:
        # Pick highest momentum
        best = max(bullish, key=lambda t: bullish[t]["mom"])
        return {best: 1.0}
    elif tlt_ok:
        return {"TLT": 1.0}
    else:
        return None


# =============================================================================
# STRATEGY E3: GROWTH MOMENTUM WITH FAST RISK-OFF
# Logic: Hold best growth ETF, but use fast 10/50 SMA crossover for quicker
# risk-off signals than the traditional 50/200.
# =============================================================================

def growth_fast_riskoff(prices: pd.DataFrame, date: pd.Timestamp,
                         growth_tickers: list = None,
                         sma_fast: int = 20, sma_slow: int = 100,
                         defensive: str = "TLT") -> dict:
    """Growth rotation with fast risk-off (20/100 SMA cross on SPY)."""
    if growth_tickers is None:
        growth_tickers = ["SOXX", "QQQ", "XLK", "VGT"]

    idx = prices.index.get_loc(date)
    if idx < max(sma_slow, 252):
        return None

    # Fast risk-off check on SPY
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        fast = spy.rolling(sma_fast).mean().iloc[-1]
        slow = spy.rolling(sma_slow).mean().iloc[-1]
        risk_on = fast > slow

    if risk_on:
        available = [t for t in growth_tickers if t in prices.columns]
        if not available:
            return None

        # Best by 3-month momentum
        best = None
        best_mom = -np.inf
        for t in available:
            series = prices[t].iloc[:idx + 1]
            if len(series) > 63:
                mom = series.iloc[-1] / series.iloc[-63] - 1
                if mom > best_mom:
                    best_mom = mom
                    best = t
        if best:
            return {best: 1.0}

    if defensive in prices.columns:
        return {defensive: 1.0}
    return None


# =============================================================================
# STRATEGY E4: AGGRESSIVE TECH ROTATION WITH VOLATILITY REGIME
# Logic: Use VIX regime to modulate between aggressive tech and defensive.
# Low VIX = aggressive tech, High VIX = bonds.
# =============================================================================

def tech_vol_regime(prices: pd.DataFrame, date: pd.Timestamp,
                     aggressive: list = None, vix_proxy: str = "VIXY",
                     vol_threshold: float = 0.02) -> dict:
    """Tech rotation modulated by volatility regime."""
    if aggressive is None:
        aggressive = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Use SPY realized vol as VIX proxy
    spy_available = "SPY" in prices.columns
    low_vol = True
    if spy_available:
        spy = prices["SPY"].iloc[:idx + 1]
        daily_ret = spy.pct_change().dropna()
        if len(daily_ret) >= 21:
            recent_vol = daily_ret.iloc[-21:].std()
            hist_vol = daily_ret.iloc[-252:].std()
            # Low vol: recent vol < 1.5x historical average
            low_vol = recent_vol < hist_vol * 1.5
            # Also check trend
            sma200 = spy.rolling(200).mean().iloc[-1]
            above_trend = spy.iloc[-1] > sma200

    if low_vol or (spy_available and above_trend):
        available = [a for a in aggressive if a in prices.columns]
        if available:
            best = None
            best_mom = -np.inf
            for t in available:
                series = prices[t].iloc[:idx + 1]
                if len(series) > 126:
                    r3m = series.iloc[-1] / series.iloc[-63] - 1
                    r6m = series.iloc[-1] / series.iloc[-126] - 1
                    mom = 0.6 * r3m + 0.4 * r6m
                    if mom > best_mom:
                        best_mom = mom
                        best = t
            if best:
                return {best: 1.0}

    # Defensive
    for d in ["TLT", "IEF", "SHY"]:
        if d in prices.columns:
            return {d: 1.0}
    return None


# =============================================================================
# STRATEGY E5: DUAL GROWTH + BOND MOMENTUM
# Logic: 70% in best growth, 30% in best bond. Shift to 100% bonds on crash.
# =============================================================================

def dual_growth_bond(prices: pd.DataFrame, date: pd.Timestamp,
                      growth: list = None, bonds: list = None,
                      growth_pct: float = 0.7) -> dict:
    """70/30 growth/bond with crash protection."""
    if growth is None:
        growth = ["SOXX", "QQQ", "XLK", "VGT"]
    if bonds is None:
        bonds = ["TLT", "IEF", "AGG"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Market regime
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma200 = spy.rolling(200).mean().iloc[-1]
        risk_on = spy.iloc[-1] > sma200

    # Best growth ETF
    avail_g = [g for g in growth if g in prices.columns]
    avail_b = [b for b in bonds if b in prices.columns]

    best_growth = None
    best_g_mom = -np.inf
    for t in avail_g:
        series = prices[t].iloc[:idx + 1]
        if len(series) > 126:
            mom = series.iloc[-1] / series.iloc[-63] - 1
            if mom > best_g_mom:
                best_g_mom = mom
                best_growth = t

    best_bond = None
    best_b_mom = -np.inf
    for t in avail_b:
        series = prices[t].iloc[:idx + 1]
        if len(series) > 63:
            mom = series.iloc[-1] / series.iloc[-63] - 1
            if mom > best_b_mom:
                best_b_mom = mom
                best_bond = t

    if risk_on and best_growth and best_bond:
        return {best_growth: growth_pct, best_bond: 1.0 - growth_pct}
    elif best_bond:
        return {best_bond: 1.0}
    elif best_growth:
        return {best_growth: 0.5}
    return None


# =============================================================================
# STRATEGY E6: PURE SOXX TREND
# Simplest possible: hold SOXX above 200 SMA, TLT below. SOXX did 468% total.
# =============================================================================

def pure_soxx_trend(prices: pd.DataFrame, date: pd.Timestamp,
                     ticker: str = "SOXX", defensive: str = "TLT",
                     sma_period: int = 200) -> dict:
    """Simple trend: SOXX above SMA = hold, below = bonds."""
    if ticker not in prices.columns:
        return None

    idx = prices.index.get_loc(date)
    if idx < sma_period + 20:
        return None

    series = prices[ticker].iloc[:idx + 1]
    sma = series.rolling(sma_period).mean().iloc[-1]

    if series.iloc[-1] > sma:
        return {ticker: 1.0}
    elif defensive in prices.columns:
        return {defensive: 1.0}
    return None


# =============================================================================
# STRATEGY E7: ENSEMBLE - MULTI-STRATEGY VOTING
# Logic: Run multiple simple strategies, go with majority vote.
# Reduces whipsaws, increases consistency.
# =============================================================================

def ensemble_voting(prices: pd.DataFrame, date: pd.Timestamp) -> dict:
    """Ensemble: majority vote across multiple signals."""
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    votes_risk_on = 0
    votes_total = 0

    # Signal 1: SPY above 200 SMA
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        if len(spy) > 200:
            sma200 = spy.rolling(200).mean().iloc[-1]
            if spy.iloc[-1] > sma200:
                votes_risk_on += 1
            votes_total += 1

    # Signal 2: SPY 50 SMA > 200 SMA (golden cross)
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        if len(spy) > 200:
            sma50 = spy.rolling(50).mean().iloc[-1]
            sma200 = spy.rolling(200).mean().iloc[-1]
            if sma50 > sma200:
                votes_risk_on += 1
            votes_total += 1

    # Signal 3: SPY 12-month return positive
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        if len(spy) > 252:
            ret_12m = spy.iloc[-1] / spy.iloc[-252] - 1
            if ret_12m > 0:
                votes_risk_on += 1
            votes_total += 1

    # Signal 4: Breadth - majority of growth ETFs above their 200 SMA
    growth = ["QQQ", "XLK", "SOXX", "VGT"]
    above_count = 0
    total_count = 0
    for g in growth:
        if g in prices.columns:
            series = prices[g].iloc[:idx + 1]
            if len(series) > 200:
                sma = series.rolling(200).mean().iloc[-1]
                if series.iloc[-1] > sma:
                    above_count += 1
                total_count += 1
    if total_count > 0:
        if above_count > total_count / 2:
            votes_risk_on += 1
        votes_total += 1

    # Signal 5: Low recent volatility
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        rets = spy.pct_change().dropna()
        if len(rets) > 63:
            recent_vol = rets.iloc[-21:].std() * np.sqrt(252)
            if recent_vol < 0.25:  # Annualized vol below 25%
                votes_risk_on += 1
            votes_total += 1

    if votes_total == 0:
        return None

    risk_on_pct = votes_risk_on / votes_total

    if risk_on_pct >= 0.6:  # 3/5 or more signals bullish
        # Pick best growth ETF
        available = [g for g in ["SOXX", "QQQ", "XLK", "VGT"] if g in prices.columns]
        if available:
            best = None
            best_mom = -np.inf
            for t in available:
                series = prices[t].iloc[:idx + 1]
                if len(series) > 63:
                    mom = series.iloc[-1] / series.iloc[-63] - 1
                    if mom > best_mom:
                        best_mom = mom
                        best = t
            if best:
                return {best: 1.0}
    else:
        # Defensive
        for d in ["TLT", "IEF", "SHY"]:
            if d in prices.columns:
                return {d: 1.0}

    return None


# =============================================================================
# STRATEGY E8: SOXX/QQQ ACCELERATION SWITCH
# Logic: Use momentum acceleration (2nd derivative) for faster switching.
# =============================================================================

def accel_tech_switch(prices: pd.DataFrame, date: pd.Timestamp,
                       tickers: list = None, defensive: str = "TLT") -> dict:
    """Pick tech ETF with best momentum acceleration, bail on deceleration."""
    if tickers is None:
        tickers = ["SOXX", "QQQ", "XLK"]

    idx = prices.index.get_loc(date)
    if idx < 252 + 21:
        return None

    candidates = {}
    for t in tickers:
        if t not in prices.columns:
            continue
        series = prices[t].iloc[:idx + 1]
        if len(series) < 273:
            continue

        # 6-month momentum now vs 1 month ago
        mom_now = series.iloc[-1] / series.iloc[-126] - 1
        mom_prev = series.iloc[-22] / series.iloc[-147] - 1
        accel = mom_now - mom_prev

        # Also check trend
        sma200 = series.rolling(200).mean().iloc[-1]
        above_trend = series.iloc[-1] > sma200

        candidates[t] = {
            "momentum": mom_now,
            "acceleration": accel,
            "above_trend": above_trend,
            "composite": mom_now + 0.5 * accel
        }

    # Filter to those with positive momentum AND above trend
    bullish = {t: v for t, v in candidates.items() if v["momentum"] > 0 and v["above_trend"]}

    if bullish:
        best = max(bullish, key=lambda t: bullish[t]["composite"])
        return {best: 1.0}

    # Check if any has positive momentum (even if below trend)
    positive = {t: v for t, v in candidates.items() if v["momentum"] > 0}
    if positive:
        best = max(positive, key=lambda t: positive[t]["composite"])
        return {best: 0.5, defensive: 0.5} if defensive in prices.columns else {best: 1.0}

    if defensive in prices.columns:
        return {defensive: 1.0}
    return None


# =============================================================================
# STRATEGY E9: MULTI-TIMEFRAME GROWTH
# Logic: Use multiple timeframe confirmations for entering/exiting growth.
# All 3 timeframes bullish = 100% growth. Mixed = partial. All bearish = bonds.
# =============================================================================

def multi_timeframe_growth(prices: pd.DataFrame, date: pd.Timestamp) -> dict:
    """Multi-timeframe growth: 3 timeframes must agree for full allocation."""
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    if "SPY" not in prices.columns:
        return None

    spy = prices["SPY"].iloc[:idx + 1]

    # Short-term: 20/50 SMA cross
    short_bull = spy.rolling(20).mean().iloc[-1] > spy.rolling(50).mean().iloc[-1] if len(spy) > 50 else False
    # Medium-term: 50/200 SMA cross
    med_bull = spy.rolling(50).mean().iloc[-1] > spy.rolling(200).mean().iloc[-1] if len(spy) > 200 else False
    # Long-term: price > 200 SMA AND 12-month return positive
    long_bull = (spy.iloc[-1] > spy.rolling(200).mean().iloc[-1] and
                 spy.iloc[-1] / spy.iloc[-252] - 1 > 0) if len(spy) > 252 else False

    bullish_count = sum([short_bull, med_bull, long_bull])

    # Select best growth ETF
    growth = ["SOXX", "QQQ", "XLK", "VGT"]
    available = [g for g in growth if g in prices.columns]

    best_growth = None
    best_mom = -np.inf
    for t in available:
        series = prices[t].iloc[:idx + 1]
        if len(series) > 63:
            mom = series.iloc[-1] / series.iloc[-63] - 1
            if mom > best_mom:
                best_mom = mom
                best_growth = t

    best_bond = None
    for b in ["TLT", "IEF", "SHY"]:
        if b in prices.columns:
            best_bond = b
            break

    if bullish_count == 3 and best_growth:
        return {best_growth: 1.0}
    elif bullish_count == 2 and best_growth and best_bond:
        return {best_growth: 0.75, best_bond: 0.25}
    elif bullish_count == 1 and best_growth and best_bond:
        return {best_growth: 0.3, best_bond: 0.7}
    elif best_bond:
        return {best_bond: 1.0}
    return None


# =============================================================================
# STRATEGY E10: ADAPTIVE CONCENTRATION
# Logic: Concentrate fully in single best performer when regime is favorable.
# Use strict crash detection (weekly drawdown check) for fast exit.
# =============================================================================

def adaptive_concentration(prices: pd.DataFrame, date: pd.Timestamp,
                            universe: list = None) -> dict:
    """Adaptive concentration: all-in on best when safe, bonds when not."""
    if universe is None:
        universe = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "SPY"]

    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    # Regime: SPY > 200 SMA AND 10-day return not severely negative
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma200 = spy.rolling(200).mean().iloc[-1]
        ret_10d = spy.iloc[-1] / spy.iloc[-10] - 1 if len(spy) > 10 else 0

        risk_on = spy.iloc[-1] > sma200 and ret_10d > -0.07  # Not in crash

    if risk_on:
        available = [u for u in universe if u in prices.columns]
        if not available:
            return None

        # Best by weighted momentum
        best = None
        best_score = -np.inf
        for t in available:
            series = prices[t].iloc[:idx + 1]
            if len(series) > 252:
                r1m = series.iloc[-1] / series.iloc[-21] - 1
                r3m = series.iloc[-1] / series.iloc[-63] - 1
                r6m = series.iloc[-1] / series.iloc[-126] - 1
                r12m = series.iloc[-22] / series.iloc[-252] - 1  # skip recent month
                score = r1m * 0.3 + r3m * 0.3 + r6m * 0.25 + r12m * 0.15
                if score > best_score:
                    best_score = score
                    best = t

        if best and best_score > 0:
            return {best: 1.0}

    # Defensive
    for d in ["TLT", "IEF", "SHY"]:
        if d in prices.columns:
            return {d: 1.0}
    return None


# =============================================================================
# STRATEGY E11: CANARY + GROWTH
# Logic: Use EEM and AGG as canary (PAA-style), but invest in tech/growth
# instead of broad market when canary signals clear.
# =============================================================================

def canary_growth(prices: pd.DataFrame, date: pd.Timestamp) -> dict:
    """Canary-based crash protection with growth concentration."""
    idx = prices.index.get_loc(date)
    if idx < 252:
        return None

    def weighted_momentum(series):
        r1 = series.iloc[-1] / series.iloc[-21] - 1 if len(series) > 21 else 0
        r3 = series.iloc[-1] / series.iloc[-63] - 1 if len(series) > 63 else 0
        r6 = series.iloc[-1] / series.iloc[-126] - 1 if len(series) > 126 else 0
        r12 = series.iloc[-1] / series.iloc[-252] - 1 if len(series) > 252 else 0
        return 12 * r1 + 4 * r3 + 2 * r6 + r12

    # Canary: EEM and AGG
    canary_bad = 0
    canary_total = 0
    for c in ["EEM", "AGG"]:
        if c in prices.columns:
            series = prices[c].iloc[:idx + 1]
            if weighted_momentum(series) < 0:
                canary_bad += 1
            canary_total += 1

    bond_frac = canary_bad / max(canary_total, 1)

    growth_frac = 1.0 - bond_frac

    if growth_frac > 0:
        # Pick best growth ETF
        growth = ["SOXX", "QQQ", "XLK", "VGT"]
        available = [g for g in growth if g in prices.columns]
        best = None
        best_mom = -np.inf
        for t in available:
            series = prices[t].iloc[:idx + 1]
            mom = weighted_momentum(series)
            if mom > best_mom:
                best_mom = mom
                best = t

        weights = {}
        if best:
            weights[best] = growth_frac

        if bond_frac > 0:
            # Best defensive
            for d in ["IEF", "TLT", "SHY"]:
                if d in prices.columns:
                    weights[d] = bond_frac
                    break
        return weights if weights else None
    else:
        for d in ["IEF", "TLT", "SHY"]:
            if d in prices.columns:
                return {d: 1.0}
    return None


# =============================================================================
# STRATEGY E12: OPTIMIZED SOXX-QQQ-TLT ROTATION
# Fine-tuned parameters for this specific asset trio.
# =============================================================================

def optimized_soxx_qqq_tlt(prices: pd.DataFrame, date: pd.Timestamp,
                            sma_period: int = 150, mom_weight_short: float = 0.6,
                            mom_weight_long: float = 0.4) -> dict:
    """Optimized SOXX/QQQ/TLT rotation with tuned parameters."""
    idx = prices.index.get_loc(date)
    if idx < max(sma_period, 252):
        return None

    # Check regime
    risk_on = True
    if "SPY" in prices.columns:
        spy = prices["SPY"].iloc[:idx + 1]
        sma = spy.rolling(sma_period).mean().iloc[-1]
        risk_on = spy.iloc[-1] > sma

    if risk_on:
        candidates = {}
        for t in ["SOXX", "QQQ"]:
            if t in prices.columns:
                series = prices[t].iloc[:idx + 1]
                if len(series) > 252:
                    r3m = series.iloc[-1] / series.iloc[-63] - 1
                    r12m = series.iloc[-22] / series.iloc[-252] - 1
                    score = mom_weight_short * r3m + mom_weight_long * r12m
                    candidates[t] = score

        if candidates:
            best = max(candidates, key=candidates.get)
            return {best: 1.0}

    if "TLT" in prices.columns:
        return {"TLT": 1.0}
    return None


# =============================================================================
# STRATEGY REGISTRY
# =============================================================================

ENHANCED_REGISTRY = {
    "concentrated_tech": {
        "fn": concentrated_tech_rotation,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "IGV", "TLT", "IEF", "SHY", "SPY"],
        "description": "Concentrated tech rotation with multi-signal crash protection",
    },
    "soxx_qqq_switch": {
        "fn": soxx_qqq_switch,
        "tickers": ["SOXX", "QQQ", "TLT", "SPY"],
        "description": "SOXX/QQQ momentum switch with trend filter",
    },
    "growth_fast_riskoff": {
        "fn": growth_fast_riskoff,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "TLT", "SPY"],
        "description": "Growth rotation with fast 20/100 SMA risk-off",
    },
    "tech_vol_regime": {
        "fn": tech_vol_regime,
        "tickers": ["SOXX", "QQQ", "XLK", "TLT", "IEF", "SHY", "SPY"],
        "description": "Tech rotation modulated by volatility regime",
    },
    "dual_growth_bond": {
        "fn": dual_growth_bond,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "TLT", "IEF", "AGG", "SPY"],
        "description": "70/30 growth/bond with crash protection",
    },
    "pure_soxx_trend": {
        "fn": pure_soxx_trend,
        "tickers": ["SOXX", "TLT"],
        "description": "Pure SOXX trend following: above 200 SMA = hold, below = TLT",
    },
    "ensemble_voting": {
        "fn": ensemble_voting,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "TLT", "IEF", "SHY", "SPY"],
        "description": "Ensemble: 5-signal voting for regime detection + growth rotation",
    },
    "accel_tech_switch": {
        "fn": accel_tech_switch,
        "tickers": ["SOXX", "QQQ", "XLK", "TLT", "SPY"],
        "description": "Tech switch using momentum acceleration (2nd derivative)",
    },
    "multi_tf_growth": {
        "fn": multi_timeframe_growth,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "TLT", "IEF", "SHY", "SPY"],
        "description": "Multi-timeframe growth: 3 timeframes must agree for full allocation",
    },
    "adaptive_concentration": {
        "fn": adaptive_concentration,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "IGV", "SPY", "TLT", "IEF", "SHY"],
        "description": "Adaptive concentration: all-in on best when safe, bonds when not",
    },
    "canary_growth": {
        "fn": canary_growth,
        "tickers": ["SOXX", "QQQ", "XLK", "VGT", "EEM", "AGG", "IEF", "TLT", "SHY"],
        "description": "Canary crash protection + growth concentration (PAA-style)",
    },
    "optimized_soxx_qqq_tlt": {
        "fn": optimized_soxx_qqq_tlt,
        "tickers": ["SOXX", "QQQ", "TLT", "SPY"],
        "description": "Optimized SOXX/QQQ/TLT rotation with tuned parameters",
    },
}
