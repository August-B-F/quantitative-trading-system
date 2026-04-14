# TEST 5 — Rebuild from scratch

Start from canonical baseline and add layers one at a time.
Add order: Test 1 Sharpe-loss magnitude (biggest first), skipping
already-rejected layers (L2, L7, L10).
After each addition, check if the layer still helps on top of the
accumulating stack.

| Step | Layer added | CAGR | Sharpe | MaxDD | Keep? |
|------|-------------|------|--------|-------|-------|
| 0 | (baseline) | 23.61% | 1.498 | -12.94% | -- |
| +L1 | L1 | 23.96% | 1.577 | -12.84% | KEEP |
| +L4 | L4 | 25.64% | 1.687 | -12.84% | KEEP |
| +L6 | L6 | 26.42% | 1.759 | -12.84% | KEEP |
| +L5 | L5 | 27.62% | 1.870 | -12.84% | KEEP |
| +L3 | L3 | 28.17% | 1.894 | -12.84% | KEEP |
| +L9 | L9 | 29.80% | 1.925 | -12.84% | KEEP |
| +L8 | L8 | 29.91% | 1.927 | -12.84% | DROP |

## Final robust stack: ['L1', 'L3', 'L4', 'L5', 'L6', 'L9']
Stats: CAGR 29.80%, Sharpe 1.925, MaxDD -12.84%

- Canonical baseline: 23.61% / 1.498 / -12.94%
- Robust stack:       29.80% / 1.925 / -12.84%
- Full P59 stack:     30.73% / 1.883 / -12.66%
