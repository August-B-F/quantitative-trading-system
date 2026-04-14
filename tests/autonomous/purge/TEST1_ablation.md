# TEST 1 — Leave-one-out layer ablation

Full P59 stack: CAGR 30.73% / Sharpe 1.88 / MaxDD -12.66%

| Removed | CAGR | Sharpe | MaxDD | Δ CAGR | Δ Sharpe | Verdict |
|---------|------|--------|-------|--------|----------|---------|
| None | 30.73% | 1.88 | -12.66% | +0.00 | +0.000 | full stack |
| L1 | 29.08% | 1.72 | -19.28% | -1.64 | -0.159 | **KEEP** (load-bearing) |
| L2 | 30.69% | 1.94 | -12.84% | -0.03 | +0.054 | **REMOVE** (improves without it) |
| L3 | 30.12% | 1.86 | -12.66% | -0.61 | -0.025 | UNCERTAIN |
| L4 | 28.79% | 1.74 | -12.66% | -1.93 | -0.143 | **KEEP** (load-bearing) |
| L5 | 29.81% | 1.80 | -12.66% | -0.92 | -0.082 | **KEEP** (load-bearing) |
| L6 | 29.41% | 1.77 | -12.66% | -1.32 | -0.114 | **KEEP** (load-bearing) |
| L7 | 30.11% | 1.87 | -12.66% | -0.62 | -0.009 | REMOVE (dead weight) |
| L8 | 30.22% | 1.87 | -12.66% | -0.51 | -0.018 | REMOVE (dead weight) |
| L9 | 29.76% | 1.87 | -12.66% | -0.97 | -0.015 | REMOVE (dead weight) |
| L10 | 30.51% | 1.88 | -12.66% | -0.21 | -0.002 | REMOVE (dead weight) |
