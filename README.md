# quantitative-trading-system

This is a stock trading system I built, plus the machinery to test it honestly, plus the record of everything I tried that did not work. The short version is that it does not beat the market. After a few hundred runs over eight years of data the best honest result was a Sharpe of about 0.96, which is roughly what you would get from luck given how many things I tried. This project is in progress, and it is more about measuring properly than about making money.

The strategy itself is simple. It rotates once a month between eight ETFs, ranked by how they have been doing lately, and moves to cash when the market drops below its 200 day average. There is one machine learning part, a small model that decides whether to rank on the last 21 days or the last 63, and that is all it does. It does not pick the stocks or size the trades.

The part I actually care about is the backtester. It is easy to fool yourself with a backtest, so this one decides at the close and buys at the next open, carries dividends and splits, and runs the benchmark through the exact same code. It does walk forward testing with a gap between the training and the test data so the future cannot leak in, and it reports a deflated Sharpe that docks the score for how many strategies were tried. There are 132 tests guarding the things that quietly break a backtest, like look ahead and ledger math.

What it found, more than any single number, is that adding more features and models gives less and less back, and that public information does not give you an edge because the market has already priced it in. That is a boring result, but it is the true one, and getting to it honestly was the point.

Charts and the full write up are in results and docs.
