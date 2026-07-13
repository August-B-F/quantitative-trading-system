# quantitative-trading-system

A regime-conditional ETF momentum rotation strategy, its measurement
infrastructure, and the audit trail of everything that was tried and did not
work. The headline result of the research is a negative one: after roughly 650
trials across eight years of history, the best honestly-measured net Sharpe is
0.962, which sits *below* the multiple-testing luck envelope for the number of
strategies tested. The durable value here is the rigor of the measurement and
the discipline of reporting that number honestly, not a claim of edge.

This README describes what the system does, how it is measured, what the
research found, and — explicitly — what it is not.

## What the strategy is

A monthly-rebalanced rotation over a fixed 8-ETF universe (`SOXX, QQQ, XLK,
VGT, IGV, XLE, GLD, SHY`, with `SHY` as the short-Treasury cash proxy). ETFs
are ranked cross-sectionally by trailing total return over the active lookback.
The portfolio holds a 50/50 blend of the single best ETF and an
inverse-volatility-weighted basket of the top three. Two overlays modify this:

- an **SMA200 trend gate** parks the top-1 leg in cash when SPY is more than 4%
  below its 200-day moving average (`src/strategy/sma_gate.py`);
- a **FOMC deferral** rule pushes out any rebalance that would land in the days
  immediately after an FOMC meeting (`src/strategy/rebalance.py`).

Everything above is deterministic and rules-based. There is exactly one
learned component, and its authority is deliberately narrow.

## The model, and what it is allowed to do

The production model is a scikit-learn `HistGradientBoostingClassifier`
(`src/model/classifier.py`, configured in `configs/strategy.yaml`). It predicts
a 4-class growth/inflation quadrant 21 trading days forward. Its **only** output
into the strategy is a binary lookback toggle: switch the momentum ranking
window between 63 and 21 trading days. It does not select ETFs, size positions,
or gate risk. If it fails to produce a prediction, the system falls back to the
63-day lookback unconditionally (`classifier_fallback`).

This is a gradient-boosted tree over tabular macro/price features, not a deep
sequence model. An earlier iteration built an LSTM/Transformer/FinBERT stack;
that code has been retired to `archive/old_codebase/` and is not part of the
production or research path. The decision to replace it with a HistGB toggle
was itself a finding: the added model capacity did not survive honest
out-of-sample measurement (see [Empirical findings](#empirical-findings)).

## Architecture

### Data pipeline

`src/data/` ingests from 33 fetchers (`src/data/fetchers/`) spanning prices,
FRED macro series, CFTC/COT positioning, AAII/NAAIM sentiment surveys, CBOE
put/call, FINRA short volume, margin debt, semiconductor billings, and news
sentiment. Each source is written to `data/clean/`, then assembled into feature
panels under `data/features/`.

Publication lag is handled explicitly at the feature layer, not left to chance:
weekly surveys are shifted +1 trading day, COT +4 days (Tuesday position date
publishes Friday), margin debt and CAPE +30 days, S&P buyback yield +60 days,
semiconductor sales +45 days (`data/FEATURE_CATALOG.md`,
`src/features/sentiment_features.py`). Every feature is reindexed onto the NYSE
trading calendar. Sources that could not be obtained cleanly are recorded in
`data/FAILED_SOURCES.md` with an orphan check confirming no feature silently
references a failed source. The catalog is candid about the compromises that
remain (e.g. margin-debt-per-SPY-price is a relative proxy, not a true
percentage of market cap; put/call native coverage ends in 2019 and post-2019
folds fall back to VIX-derived sentiment).

### Two backtest engines — and which one counts

There are two engines, and conflating them is the single most common way to
report a fake number, so the distinction is enforced:

- **`src/backtest/ledger.py` — the daily NAV-ledger backtester.** This is the
  canonical, quotable engine. A decision known at the close of day *d* fills at
  the next trading day's open. Fills use dividend/split-consistent prices
  (`adj_open = open * adj_close / close`); the fill-day return is spliced
  correctly (pre-trade holdings earn prev-close→open, post-trade holdings earn
  open→close). Positions **drift** between rebalances with each ticker's
  adjusted return rather than being phantom-rebalanced daily. Transaction cost
  is `cost_bps × traded notional`, deducted from NAV on the fill day. Benchmarks
  (buy-and-hold SPY, monthly-rebalanced 60/40) run *through the same engine at
  the same cost*, so comparisons are apples-to-apples. Sharpe is computed on
  daily NAV returns.
- **`src/backtest/engine.py` — the fwd21 proxy.** A screening tool that
  approximates each month's return by the forward-21-day return of the executed
  position, gross of transaction cost. It is fast and useful for sweeps, but its
  output is *never* quotable as performance. The Sharpe ≈ 1.5–1.9 figures that
  appear in older stress and champion reports (`results/STRESS_TEST_REPORT.md`,
  `tests/autonomous/purge/VERDICT.md`) come from this proxy. They are gross,
  overlapping-return approximations and are not comparable to the net,
  daily-ledger 0.962.

This rule is codified in `CONSTITUTION.md` rule 5: numbers come only from the
daily-ledger engine.

### Walk-forward with purge and embargo

`src/model/walk_forward.py` provides `OverlappingSplitter` and
`ExpandingSplitter`. Both emit overlapping daily training samples with
**purging and embargo** (`_purge_and_embargo`): any training sample whose
forward-return window `[t, t+H]` (plus an embargo of several trading days) could
overlap the start of the validation or test window is dropped. This is the
López de Prado construction, and it is what prevents the 21-day forward target
from leaking backward across a fold boundary. The expanding splitter
additionally applies exponential-decay sample weights to older observations.

### Position sizing and execution

Sizing is in `src/strategy/position_sizing.py` (50% top-1, 50% inverse-vol
top-3). Execution targets Alpaca paper trading (`src/execution/`), one account
per strategy variant, with positions reconciled against the broker. All
strategy parameters live in `configs/strategy.yaml`; nothing that affects a
backtest number is hard-coded.

## The test suite

The formal pytest suite is **132 test functions across 24 modules** in
`tests/` (`tests/test_*.py`). This is separate from the ~120 exploratory
experiment scripts under `tests/autonomous/`, which are the research corpus, not
unit tests. The 132 tests exist because a backtest you cannot trust is worse
than none, and because this repository has already been burned once by a
plumbing failure that no test caught (see [Governance](#governance-read-this-first)).

What they guard, concretely:

- **Ledger correctness** (`test_ledger.py`): a SPY-replication canary (the
  engine must reproduce buy-and-hold SPY), hand-computed drift, cost-sanity on
  alternating schedules, schedule validation (negative weights, weights summing
  above 1, unknown tickers all raise), partial-weight remainder routed to cash,
  no-NaN / weights-sum-to-one invariants, and **determinism**.
- **Look-ahead and freshness** (`test_live_freshness.py`,
  `test_health_freshness.py`): the live path must reach genuinely fresh dates,
  must never trade a stale tail, and the freshness gate must fire when the panel,
  feature layer, and wall clock disagree. NaN feature tails must alert rather
  than silently produce a position.
- **Multiple-testing math** (`test_deflated_sharpe.py`): that deflation
  actually bites as trial count rises, that DSR collapses to PSR at a single
  trial, that DSR sits at 0.5 exactly at the analytic expected-max Sharpe, and
  that the CLI reproduces this against the seeded ledger.
- **Worked examples** (`test_worked_example.py`): specific historical
  rebalances (2019-01, 2020-03 month-ends) reproduced end-to-end.
- **Walk-forward regression** (`test_backtest_canary.py`), classifier, momentum
  ranking, tranche wiring, executor, risk monitoring, config loading, and data
  failover.

## Empirical findings

These are the results the research actually supports. They are documented in
`docs/POSTMORTEM_2026H1.md`, `research/MECHANISM_ANALYSIS.md`, and
`tests/autonomous/purge/VERDICT.md`, and they are not flattering.

**1. Added complexity shows diminishing, then negative, returns.** The most
layered champion (P59) stacked 10 overlays. The ablation study
(`tests/autonomous/purge/`) found that of its +7.12 percentage points of CAGR
over the canonical strategy, +6.19pp (87%) was load-bearing and +0.93pp (13%)
came from four overlays (a 62/38 split, an FOMC-window tightening, a drawdown
trigger, a warm boost) that *did not improve Sharpe and hurt the
out-of-sample second half* — classic overfitting that survived only because it
raised full-sample CAGR. Stripping them made the strategy strictly better on a
risk-adjusted basis. The mechanism analysis reaches the same conclusion from
the other direction: the appropriate response to the strategy's weak years is
**not** to optimize the lookback window (which overfits the mechanism), because
any fix that helps one regime demonstrably harms another.

**2. Public market information does not confer a durable edge here.** This is
the semi-strong-efficiency result, stated plainly:

- The regime classifier's walk-forward accuracy is 60–66%, **below the 91% of
  the naive "same regime as today" baseline** — a model that beats nothing.
- Macro features carry roughly 25–35 days of publication-lag look-ahead when not
  meticulously aligned, which inflates any classifier-conditioned backtest and
  accounts for much of the apparent edge in careless configurations.
- The most defensible surviving candidate is, on honest inspection, a *gated
  tech-concentration book*: its risk-on holdings average ~78% in a correlated
  5-fund tech block, and applying the same chassis to ex-ante universes adds ≈0
  Sharpe over its own SMA200 gate (`EVALUATION.md`). The gate supplies the
  drawdown control; the universe supplies the return. It is not a momentum edge.
- Single-date month-end backtests on this sample carry +0.15–0.18 Sharpe
  (~200–260 bps/yr) of pure rebalance-*date* luck (`results/DROPLET_LEDGER.md`).

The honest forward expectation for the best candidate is a net Sharpe of roughly
0.6–0.8 with a -30% max-drawdown budget — judged against that, not against 1.0.

## Deflated Sharpe and the multiple-testing correction

`scripts/research/deflated_sharpe.py` implements the Probabilistic and Deflated
Sharpe Ratios of Bailey & López de Prado (2014). The Deflated Sharpe is the
probability that an observed Sharpe reflects skill rather than being the best of
*N* noise draws; it compares the observed Sharpe against the *expected maximum*
Sharpe that *N* zero-skill trials would produce by luck alone, given the
cross-trial variance of Sharpes.

Applied honestly to this repository's own trial ledger
(`results/TRIAL_LEDGER.csv`, ~650+ trials censused):

- Best net Sharpe (daily-ledger engine): **0.962** (`FN_abs_mom_optimized`,
  `results/MASTER_SUMMARY.md`).
- Expected-max Sharpe under luck at N≈316 trials: **≈0.97** — the observed
  result is *at or below* the luck envelope, and higher under wider dispersion
  assumptions.
- Deflated Sharpe: **0.46** at N=316, **0.26** against the full ledger. Both are
  far below the 0.95 threshold the project sets for taking a result seriously.

`CONSTITUTION.md` rule 3 requires that every reported Sharpe ship with its
Deflated Sharpe. The 0.962 is reported here with its DSR precisely because the
DSR is the part that matters: the strategy does not clear the selection-bias
hurdle. Nothing in this repository has.

## Governance (read this first)

The 2026 H1 paper race was declared **void** (`docs/POSTMORTEM_2026H1.md`).
For 2.5 months the live system re-traded a signal frozen at 2026-04-10 — the
master feature panel stopped rebuilding, the health check watched the wrong data
layer, and the system reported zero alerts the entire time. One account posted
+37.7% and another -8.4%; the spread measured which frozen April portfolio
drifted luckiest, not strategy skill. The post-mortem documents every root cause
to file and line.

The governance layer written in response binds all subsequent work:

- **[CONSTITUTION.md](CONSTITUTION.md)** — 10 rules: hypothesis committed before
  backtest, a hard budget of 3 specs per quarter, every trial appended to the
  ledger, Deflated Sharpe beside every Sharpe, beat the named naive baseline net
  of cost, ledger-engine numbers only, negative results kept, criteria never
  rewritten after seeing results, universe fixed by ex-ante rule, and — rule 10 —
  a system that cannot prove its signal is fresh must refuse to trade.
- **[EVALUATION.md](EVALUATION.md)** — the relaunch race protocol: control arms,
  DSR/SPA entry gates, drawdown tripwires, and a promotion/kill table that is
  explicit that a 12-month Sharpe race cannot resolve a 0.20 edge (it judges
  *implementability*, not alpha).
- **[docs/RELAUNCH_RUNBOOK.md](docs/RELAUNCH_RUNBOOK.md)** — operator steps to
  reset accounts and relaunch.

The full strategy spec is [MASTER_ARCHITECTURE.md](MASTER_ARCHITECTURE.md).
Where it disagrees with code, the code is authoritative.

## What this is, and what it is not

**It is** a carefully instrumented research pipeline: a leakage-aware feature
layer, a daily NAV ledger that live trading can converge to, walk-forward
splits with purge and embargo, a full trial census, a multiple-testing
correction applied to the project's own results, and a governance regime born
from a documented failure. The engineering is the deliverable.

**It is not** a profitable strategy, and it is not presented as one:

- No result in the repository clears the Deflated Sharpe threshold. The best net
  Sharpe (0.962) is below the luck envelope for the number of trials run.
- The classifier does not beat naive regime persistence.
- The strongest candidate's return comes from concentrated exposure to a
  correlated tech block plus a trend gate, not from an information edge over an
  efficient market.
- There is no held-out, out-of-sample track record of live skill. The one paper
  race that ran was voided by a data-freshness bug.
- The fwd21-proxy Sharpe figures (1.5–1.9) that appear in older reports are
  gross, overlapping-return approximations and must not be read as performance.

The intellectually honest summary is that public, liquid ETF markets priced in
the information these signals encode, and the search for edge returned a
negative result. The project's worth is in how rigorously that negative result
was established.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with FRED and Alpaca paper keys (see `configs/accounts.yaml`).
Without a FRED key the macro fetcher falls through to the public fredgraph.csv
endpoint.

## Usage

```bash
python3 scripts/run_rebalance.py                 # dry run, all strategies
python3 scripts/run_rebalance.py --status        # broker status of all accounts
python3 scripts/run_rebalance.py --strategy 1 --execute
python3 scripts/run_health_check.py              # freshness/drift checks; exit 1 on alert
python3 scripts/run_backtest.py                  # daily-ledger backtest
python3 scripts/research/deflated_sharpe.py --sharpe 0.962 --T 96 --ledger results/TRIAL_LEDGER.csv
```

## Disclaimer

Educational and research use. Paper trading only. Nothing here is investment
advice, and the documented findings are a reason not to trade it with real
capital, not an invitation to.
