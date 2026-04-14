# TEST 2 — Forward walk holdout per layer

Full stack per-half Sharpe: A (2010-17) 2.278, B (2018-26) 1.750

`dA = full_A_sharpe - variant_A_sharpe` — positive means the layer helps Period A.

| Layer | A Sharpe (no-L) | B Sharpe (no-L) | dA | dB | Both positive? | Verdict |
|-------|-----------------|-----------------|----|----|----------------|---------|
| L1 | 2.300 | 1.518 | -0.022 | +0.232 | no | REMOVE — only helps B (2018-2026) |
| L2 | 2.255 | 1.831 | +0.022 | -0.081 | no | REMOVE — only helps A (2010-2017) |
| L3 | 2.278 | 1.707 | +0.000 | +0.043 | no | REMOVE — only helps B (2018-2026) |
| L4 | 2.160 | 1.650 | +0.117 | +0.100 | yes | **KEEP** — helps both |
| L5 | 2.002 | 1.751 | +0.276 | -0.000 | no | REMOVE — only helps A (2010-2017) |
| L6 | 1.908 | 1.780 | +0.370 | -0.030 | no | REMOVE — only helps A (2010-2017) |
| L7 | 2.276 | 1.731 | +0.002 | +0.020 | yes | **KEEP** — helps both |
| L8 | 2.264 | 1.725 | +0.014 | +0.025 | yes | **KEEP** — helps both |
| L9 | 2.220 | 1.752 | +0.058 | -0.002 | no | REMOVE — only helps A (2010-2017) |
| L10 | 2.269 | 1.748 | +0.008 | +0.003 | yes | **KEEP** — helps both |
