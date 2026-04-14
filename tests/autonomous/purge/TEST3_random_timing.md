# TEST 3 — Random timing test

For each triggered layer, we compute the actual Sharpe improvement
from enabling just that layer (trans_mask held constant), and compare
against the Sharpe distribution when the same number of firings are
placed at RANDOM dates (500 iterations).

Actual firings: DD=19, FULL=43, WARM=10, TRANS=46  (n_months=190)

| Layer | Actual Δ Sharpe | Rand p50 | Rand p75 | Rand p95 | Percentile | Verdict |
|-------|------------------|----------|----------|----------|------------|---------|
| L8 DD | +0.0230 | +0.0044 | +0.0223 | +0.0432 | 76.2% | marginal — between p75 and p95 |
| L9 FULL | +0.0159 | -0.0315 | -0.0135 | +0.0097 | 97.4% | **KEEP** — timing matters (>p95) |
| L10 WARM | +0.0010 | -0.0021 | +0.0018 | +0.0066 | 68.8% | REMOVE — random dates would do at least as well |
| L5 TRANS | +0.0993 | -0.0485 | -0.0173 | +0.0346 | 100.0% | **KEEP** — timing matters (>p95) |
