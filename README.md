# quantitative-trading-system

An ETF momentum strategy and the machinery to measure it honestly. Plus the full record of everything that got tried and did not beat the market. In progress.

The short version. After a few hundred runs across eight years of data, the best honest result is a net Sharpe of 0.96, which sits just under what you would expect from luck alone given how many strategies were tried. This is not a money printer. It is a backtester you can trust and the discipline to report that number straight.

## What it does

A monthly rotation over eight ETFs, ranked by trailing return, holding the top few, with a trend gate that goes to cash when the market is below its 200 day average. There is one learned piece, a gradient boosted classifier, and all it does is flip the ranking window between 21 and 63 days. It does not pick the stocks or size the trades.

## Why it is careful

Two backtest engines and only the honest one counts. A daily NAV ledger that decides at the close and fills at the next open, carries dividends and splits, and runs the benchmarks through the same path. The faster proxy engine is for screening, and its rosier numbers are flagged as such everywhere they appear.

Walk forward with purge and embargo, so the 21 day target can never leak across a fold boundary. Deflated Sharpe on every Sharpe, to dock it for how many things were tried. And 132 tests guarding the things that break a backtest quietly, look ahead, ledger math, determinism, freshness.

## What it found

More features and models give less and less back, and past a point they just overfit the recent half. The regime classifier is right 60 to 66 percent of the time, under the 91 percent you get by assuming tomorrow looks like today. Public information does not carry an edge, the market has already priced it in.

Result charts and the full postmortem are in results/ and docs/.

## Status

In progress. Runs a daily pipeline. The whole thing is an argument for measuring honestly.
