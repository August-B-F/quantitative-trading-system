# OPTIMIZATION REPORT — E-R1 Mods M01..M27

Walk-forward regime classifier accuracy: **0.665**

Haircut rule: improvement (after 50% reduction) must exceed +0.5pp CAGR or +0.03 Sharpe, with MaxDD not >2pp worse.

## Individual modification results

| Mod  | Description | CAGR | Sharpe | MaxDD | Δ CAGR | Δ Sharpe | Δ MaxDD | Pass haircut |
|---|---|---|---|---|---|---|---|---|
| E-R1 | Control: 63d/21d, 50% top1 + 50% top3, SMA200 gate | 21.2% | 1.34 | -21.0% | -- | -- | -- | -- |
| M01 | 63d/42d | 18.6% | 1.19 | -21.0% | -2.60pp | -0.15 | -0.00pp | fail |
| M02 | 126d/21d | 19.4% | 1.18 | -29.2% | -1.75pp | -0.16 | -8.16pp | fail |
| M03 | 126d/42d | 16.9% | 1.04 | -31.4% | -4.31pp | -0.29 | -10.36pp | fail |
| M04 | 63d/10d | 20.0% | 1.25 | -21.0% | -1.20pp | -0.09 | +0.00pp | fail |
| M05 | avg(63,126)stable / 21d trans | 20.3% | 1.23 | -21.5% | -0.82pp | -0.11 | -0.47pp | fail |
| M06 | avg(21,63,126)/avg(10,21) | 19.6% | 1.20 | -21.0% | -1.54pp | -0.14 | +0.03pp | fail |
| M07 | 100% top3 EW | 18.3% | 1.24 | -21.1% | -2.89pp | -0.10 | -0.09pp | fail |
| M08 | 40% top1 / 60% top3 | 20.6% | 1.34 | -20.8% | -0.54pp | +0.00 | +0.23pp | fail |
| M09 | 60% top1 / 40% top3 | 21.7% | 1.32 | -21.3% | +0.52pp | -0.01 | -0.24pp | fail |
| M10 | 50% top1 / 50% top2 | 20.5% | 1.24 | -21.5% | -0.66pp | -0.10 | -0.51pp | fail |
| M11 | top3 inverse-vol weighted | 22.4% | 1.40 | -19.4% | +1.24pp | +0.06 | +1.59pp | PASS |
| M12 | top3 momentum-score weighted | 21.1% | 1.23 | -19.1% | -0.10pp | -0.11 | +1.92pp | fail |
| M13 | 50/50 top1/top4 | 20.8% | 1.34 | -19.8% | -0.40pp | +0.01 | +1.25pp | fail |
| M14 | +TLT (9 ETF) | 18.6% | 1.23 | -20.8% | -2.58pp | -0.11 | +0.26pp | fail |
| M15 | +DBC (9 ETF) | 18.5% | 1.17 | -25.9% | -2.63pp | -0.16 | -4.88pp | fail |
| M16 | +TLT+DBC (10 ETF) | 16.4% | 1.08 | -25.9% | -4.77pp | -0.25 | -4.88pp | fail |
| M17 | Drop XLK/VGT/IGV; +XLF/XLI/XLV | 19.1% | 1.24 | -24.4% | -2.04pp | -0.09 | -3.41pp | fail |
| M18 | M17 + TLT + DBC (10 ETF) | 14.0% | 0.96 | -28.8% | -7.16pp | -0.38 | -7.80pp | fail |
| M19 | E-R1 + soft EV gate (HistGB on macro) | 14.1% | 1.19 | -13.5% | -7.06pp | -0.14 | +7.50pp | fail |
| M20 | E-R1 + HY-IG z>1.5 → 60% | 20.9% | 1.37 | -21.0% | -0.25pp | +0.03 | +0.00pp | fail |
| M21 | E-R1 + VIX>30 → 50% | 19.8% | 1.29 | -21.0% | -1.41pp | -0.04 | +0.00pp | fail |
| M22 | E-R1 + YC inverted 63d → 70% | 20.5% | 1.33 | -21.0% | -0.67pp | -0.01 | +0.00pp | fail |
| M23 | E-R1 + signal disagreement → 70% | 20.2% | 1.32 | -21.0% | -0.96pp | -0.02 | +0.00pp | fail |
| M24 | Weekly check, 3pp threshold | 10.4% | 0.67 | -29.6% | -10.74pp | -0.66 | -8.61pp | fail |
| M25 | Weekly check, 5pp threshold | 10.4% | 0.67 | -29.6% | -10.74pp | -0.66 | -8.61pp | fail |
| M26 | Defer FOMC week 5d | 21.1% | 1.32 | -14.8% | -0.04pp | -0.02 | +6.24pp | fail |
| M27 | Defer quad witching 5d | 20.5% | 1.30 | -21.0% | -0.68pp | -0.04 | +0.00pp | fail |

## Best per block (haircut-passing)

- **B1**: no modification passed haircut
- **B2**: M11 — CAGR 22.4%, Sharpe 1.40, MaxDD -19.4%
- **B3**: no modification passed haircut
- **B4**: no modification passed haircut
- **B5**: no modification passed haircut

## Incremental combination

| Step | Added | CAGR | Sharpe | MaxDD | Action |
|---|---|---|---|---|---|
| Step1 | E-R1 base | 21.2% | 1.34 | -21.0% | start |
| B1_skip | (none) | -- | -- | -- | skipped |
| B2_+M11 | M11 | 22.4% | 1.40 | -19.4% | KEEP |
| B3_skip | (none) | -- | -- | -- | skipped |
| B4_skip | (none) | -- | -- | -- | skipped |
| B5_skip | (none) | -- | -- | -- | skipped |

## Final optimized strategy

- CAGR: **22.4%**
- Sharpe: **1.40**
- MaxDD: **-19.4%**
- ΔCAGR vs E-R1: +1.24pp
- ΔSharpe vs E-R1: +0.06