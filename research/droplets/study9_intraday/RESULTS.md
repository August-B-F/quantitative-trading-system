# Study 9 RESULTS — measured intraday execution costs (Alpaca SIP)

Date: 2026-07-02. Hypothesis registered before any fetch (HYPOTHESIS.md).
Scripts: probe_api.py (feed capabilities), fetch_bars.py (rerunnable
fetcher: minute bars + sampled NBBO), analyze.py (all numbers below).
Raw outputs: measurements.csv, nbbo_spread_summary.csv, probe_results.json,
data/*.parquet.

## 0. What the feed actually is (probe, 2026-07-02)

The "free plan = IEX only" assumption was WRONG for our keys (ALPACA_S1):
- **SIP (consolidated) historical data is served**: 1-min bars back to
  **2016-01-04**, historical NBBO quotes back to 2016, recency limited only
  by the 15-minute delay. IEX 1-min bars start 2020-07-27 (~2-3% of volume)
  — we did not need them.
- Fields per bar: o,h,l,c,v,n,vw. Rate limit 200 req/min. Page cap 10k rows.
- `adjustment=split` matches our parquet convention (split-adjusted,
  dividend-unadjusted) exactly; `raw` is 3x off for SOXX and 2x for XLE
  pre-2024 (both split in 2024-2025). Verified per symbol on 4 dates,
  ratios 0.999-1.001.
- Multi-symbol quotes endpoint gotcha: `limit` is filled by the
  alphabetically first symbol; per-symbol requests required.

Sample: 2,638 trading days per symbol (2016-01-04..2026-07-01), ~98-100%
minute-slot coverage. NBBO sampled on 63 days (every other month, 10th
trading day) at 7 instants.

## (a) Effective open execution — market-at-open vs official auction open

Signed VWAP(09:30-09:34) vs official open (bps), 2,637-2,638 days/symbol:

| symbol | mean signed | mean abs | med abs | p90 abs | min-0 VWAP med abs |
|--------|------------:|---------:|--------:|--------:|-------------------:|
| SOXX | +0.36 | 16.16 | 12.29 | 34.77 | 4.3 |
| QQQ  | +0.49 |  7.88 |  5.87 | 17.41 | 2.0 |
| XLE  | -0.57 | 19.86 | 14.89 | 42.63 | 6.6 |
| GLD  | -0.23 |  3.81 |  2.66 |  8.22 | 0.8 |
| SHY  | -0.07 |  0.48 |  0.26 |  1.06 | 0.1 |
| SPY  | +0.43 |  5.38 |  3.73 | 11.40 | 1.5 |

- **Mean signed slippage is ~zero everywhere (±0.6 bps)** — the first
  5 minutes are a random walk around the auction print, not a systematic
  cost. The abs numbers are volatility, not money lost in expectation.
- Pre-registered materiality bars (10 bps liquid / 20 bps SOXX-XLE mean
  abs): **not breached** (XLE 19.9 is within 20 by a hair). The backtest's
  official-open fill assumption is NOT materially optimistic for a prompt
  market order: trades in minute 0 average within 0.1-6.6 bps (median) of
  the auction print.

**Delay-N-minutes decision.** The pre-registered range-proxy rule fires
"delay ~5 min" (proxy drops 12.5 bps for SOXX vs +0.8 bps drift). But the
NBBO supplement — the direct measurement — shows the range proxy conflates
volatility with spread: real quoted spread at 09:30:15 is only 8.5 bps
(SOXX), 2.3 (XLE), <0.9 (SPY/QQQ/GLD), i.e. the true half-spread saving
from waiting to 09:35 is ~1.2 bps on SOXX, ~0.3 on XLE, ~0 elsewhere,
while the measured signed drift over those 5 minutes is +0.8..+1.0 bps
against buys on the momentum legs. Net measured edge of delaying ≈ 0,
plus ~12-35 bps (med-abs, symbol-dependent) of pure tracking error vs the
backtested open price.
**Verdict: STAY IMMEDIATE.** Both readings are reported per rule 8; the
proxy rule fired but its premise (proxy = spread) is directly contradicted
by the quoted-spread measurement. The superior upgrade is `opg` auction
orders (exact backtest fidelity, zero spread) — already a recorded lead.

## (b) Spread, open vs afternoon — when is trading cheaper

Median of daily mean 1-min (h-l)/c, bps; and median quoted NBBO spread:

| symbol | range proxy 09:30-34 | range proxy 15:45-54 | pm cheaper % days | NBBO 09:30:15 | NBBO 09:35 | NBBO 15:45-55 |
|--------|---------------------:|---------------------:|------------------:|--------------:|-----------:|--------------:|
| SOXX | 20.9 | 6.1 | 99% | 8.51 | 6.05 | 1.98-2.57 |
| QQQ  | 12.0 | 5.6 | 96% | 0.62 | 0.59 | 0.48-0.55 |
| XLE  | 24.2 | 6.7 | 100% | 2.26 | 1.59 | 1.46 |
| GLD  |  5.9 | 2.1 | 97% | 0.84 | 0.83 | 0.62-0.63 |
| SHY  |  0.8 | 0.9 | 47% | 1.20 | 1.19 | 1.19-1.20 |
| SPY  |  7.2 | 4.7 | 87% | 0.39 | 0.33 | 0.33-0.36 |

- The afternoon (15:45-15:55) is cheaper on ALL rotation risk legs, both
  by proxy (-22% to -72%) and by quoted spread (SOXX 4x tighter). The
  pre-registered ">=25% cheaper on all 6" criterion fails only on SHY,
  whose spread is a flat ~1.2 bps in both windows (it cannot be 25%
  cheaper than itself); the economic direction is unambiguous on 5/6.
- **Verdict: afternoon IS the cheaper window** — supporting evidence for
  the `cls` lead. Note the absolute numbers: quoted spreads on these ETFs
  are 0.3-8.5 bps, i.e. half-spread cost 0.2-4.3 bps/side. Our 10 bps/side
  assumption already covers spread+slippage generously for every leg
  except possibly SOXX at the open, where it is still adequate.

## (c) Close drift — feasibility of the 15:45-signal + `cls` order lead

Official close vs 15:44-bar close (bps):

| symbol | mean (all) | med abs (all) | p90 abs (all) | med abs (decision days, n≈490) |
|--------|-----------:|--------------:|--------------:|-------------------------------:|
| SOXX | +0.29 | 15.04 | 50.28 | 14.47 |
| QQQ  | +0.07 | 10.70 | 34.08 | 11.35 |
| XLE  | -0.59 | 12.85 | 38.34 | 12.45 |
| GLD  | -0.18 |  4.53 | 13.56 |  4.84 |
| SHY  | +0.03 |  1.17 |  2.44 |  1.18 |
| SPY  | -0.17 |  9.28 | 31.02 | 10.41 |

Last-10-min VWAP vs official close (working the close manually instead of
the auction): med abs 6.5 (SOXX), 4.3 (QQQ), 5.6 (XLE), 2.1 (GLD),
0.7 (SHY), 4.0 (SPY) bps — the closing auction is the cheapest fill.

**Rank-flip test** (blend_126_252 top-3 recomputed with the 15:44 close
substituted for the final print; XLK/VGT/IGV proxied by official closes →
flips slightly UNDERcounted; 2,628 days):
- top-3 set differs on **7.7%** of all days; on **6.8%** of the 502
  month-end +0/+5/+10/+15 decision days.
- SPY/SMA200 **gate flips on 0.49%** of days — the gate is essentially
  immune to 15-minute staleness.

**Pre-registered verdict:** flip rate 6.8% <= 10% bar — PASS. Median
|drift| <= 15 bps on rotation legs: PASS on decision days (max 14.5), and
on the strict all-days reading SOXX sits exactly at the boundary (15.04 vs
15.00 — reported, not reinterpreted). **The data SUPPORTS the `cls` lead**:
prices move a median ~10-15 bps in the final 16 minutes, only ~1 decision
in 15 would see a different top-3, and the gate almost never flips. The
full shadow study (live 15:40 signal vs official-close signal, whole-share
`cls` constraints) that DROPLET_LEDGER already requires remains the next
gate before any spec.

## Cost-model calibration (the folklore replaced)

- Measured all-in cost of "market order at open" vs backtest open:
  ~0.5-5 bps/side expected (half-spread + ~zero drift) for SPY/QQQ/GLD/SHY,
  ~4-8 bps/side for SOXX/XLE at the open. **10 bps/side is a fair-to-
  conservative primary assumption; 20 bps/side is clearly conservative.**
- No evidence to add an execution-delay penalty; no evidence the open
  assumption flatters the backtest beyond the noise documented above.

## Files
- HYPOTHESIS.md (pre-registered), probe_api.py, probe_results.json
- fetch_bars.py (rerunnable; bars + --quotes), data/*.parquet (6 symbols
  x 2,638 days windows 09:30-09:39 & 15:40-15:59; 2,638-row NBBO sample)
- analyze.py, measurements.csv, nbbo_spread_summary.csv, trials.csv
