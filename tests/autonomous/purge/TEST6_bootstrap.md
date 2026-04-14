# TEST 6 — Bootstrap comparison

| Strategy | CAGR | Sharpe | MaxDD |
|----------|------|--------|-------|
| Canonical | 23.61% | 1.498 | -12.94% |
| **Robust** | **29.80%** | **1.925** | **-12.84%** |
| Full P59 | 30.73% | 1.883 | -12.66% |

## Paired bootstrap (10,000 iterations, 188-month sample)

| Comparison | t-stat | P(edge>0) | Mean ann edge | 95% CI ann |
|------------|--------|-----------|---------------|------------|
| Robust vs baseline | +2.974 | 99.88% | +4.98pp/yr | [+1.79, +8.45] pp/yr |
| Full P59 vs baseline | +3.352 | 99.99% | +5.85pp/yr | [+2.53, +9.51] pp/yr |
| Robust vs Full P59 | -1.220 | 10.76% | -0.83pp/yr | [-2.18, +0.49] pp/yr |

## Interpretation

- **Robust stack has statistically significant forward edge** over baseline (95% CI lower bound +1.79pp/yr).
- Full P59 slightly beats Robust on bootstrap mean, but the gap is small.
