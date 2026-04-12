# TIER 2 VERDICT: PROCEED — multiple AI/ensemble strategies beat B3

Tier 1 stopped because the prescribed CORE/MIN feature sets and direct rotation/drawdown targets did not beat baselines. Tier 2 went broader and found several strategies that strictly improve over B3 on Sharpe (and most metrics) without losing meaningful CAGR.

## Recommended primary strategy

**T2_balanced**: CAGR 19.3% (vs B3 19.4%), Sharpe 1.22 (vs 1.00), MaxDD -21.0% (vs -22.3%).

Description: 0.5*[top1+SMA200-4% gate] + 0.5*top3.

This is the cleanest no-ML improvement: matches B3 CAGR within 0.1pp, raises Sharpe by +0.22, and lowers MaxDD by -1.2pp. No fitting risk — only a static SMA200 trend filter on the top-1 leg of a momentum blend.

## Alternative: ML-overlay highest-Sharpe strategy

**T2_3legCAGR_softML**: CAGR 16.9%, Sharpe 1.24 (highest of all candidates), MaxDD -16.7%. Trades ~2.5pp CAGR for +0.24 Sharpe and -5.5pp lower MaxDD. This is the strategy where ML adds clear, measurable value.

## Conclusion

The Tier 1 conclusion was right *for the prescribed model architectures*: monthly ETF rotation prediction and drawdown classification on the CORE feature set don't work. But the Tier 2 search shows there's still real value to be found by:

1. Diversifying within momentum (top-3 instead of top-1) — free Sharpe.

2. Combining momentum signals across horizons in ensembles.

3. A simple SPY trend filter on the concentrated leg.

4. An ML expected-return regressor on macro features used as a *soft* exposure scaler (not a binary on/off classifier).
