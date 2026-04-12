"""
Standalone backtesting engine for systematic strategy research.
Supports portfolio-level strategies with rebalancing, transaction costs, and comprehensive metrics.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import json
import os
from datetime import datetime


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000
    transaction_cost_bps: float = 5  # 5 bps round-trip
    slippage_bps: float = 5  # 5 bps slippage
    rebalance_frequency: str = "monthly"  # monthly, weekly, daily
    start_date: str = "2018-01-01"
    end_date: str = "2025-12-31"
    benchmark: str = "SPY"


@dataclass
class BacktestResult:
    strategy_name: str
    config: dict
    equity_curve: pd.Series = None
    benchmark_curve: pd.Series = None
    weights_history: pd.DataFrame = None
    trades: List[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def compute_metrics(self):
        """Compute comprehensive performance metrics."""
        eq = self.equity_curve
        bm = self.benchmark_curve

        if eq is None or len(eq) < 2:
            return

        # Returns
        returns = eq.pct_change().dropna()
        bm_returns = bm.pct_change().dropna() if bm is not None else None

        # Annual returns by year
        annual_returns = {}
        annual_bm_returns = {}
        for year in range(eq.index[0].year, eq.index[-1].year + 1):
            yr_eq = eq[eq.index.year == year]
            if len(yr_eq) >= 2:
                annual_returns[year] = (yr_eq.iloc[-1] / yr_eq.iloc[0]) - 1
            if bm is not None:
                yr_bm = bm[bm.index.year == year]
                if len(yr_bm) >= 2:
                    annual_bm_returns[year] = (yr_bm.iloc[-1] / yr_bm.iloc[0]) - 1

        # Total return
        total_return = (eq.iloc[-1] / eq.iloc[0]) - 1
        bm_total_return = (bm.iloc[-1] / bm.iloc[0]) - 1 if bm is not None else None

        # CAGR
        years = (eq.index[-1] - eq.index[0]).days / 365.25
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
        bm_cagr = (bm.iloc[-1] / bm.iloc[0]) ** (1 / years) - 1 if bm is not None and years > 0 else 0

        # Sharpe ratio (annualized, assuming 252 trading days)
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        # Sortino ratio
        downside = returns[returns < 0]
        sortino = returns.mean() / downside.std() * np.sqrt(252) if len(downside) > 0 and downside.std() > 0 else 0

        # Max drawdown
        cummax = eq.cummax()
        drawdown = (eq - cummax) / cummax
        max_dd = drawdown.min()

        # Calmar ratio
        calmar = cagr / abs(max_dd) if max_dd != 0 else 0

        # Year-to-year variance of returns
        if len(annual_returns) > 1:
            annual_vals = list(annual_returns.values())
            return_variance = np.std(annual_vals)
        else:
            return_variance = 0

        # Negative years count
        negative_years = sum(1 for r in annual_returns.values() if r < 0)

        # Consistency score: penalize high variance, reward positive years
        # Lower is better for variance, higher is better for positive years
        positive_year_ratio = 1 - (negative_years / max(len(annual_returns), 1))

        # Excess return vs benchmark per year
        annual_excess = {}
        for y in annual_returns:
            if y in annual_bm_returns:
                annual_excess[y] = annual_returns[y] - annual_bm_returns[y]

        # Win rate vs benchmark
        if annual_excess:
            beat_benchmark_years = sum(1 for e in annual_excess.values() if e > 0)
            beat_rate = beat_benchmark_years / len(annual_excess)
        else:
            beat_rate = 0

        self.metrics = {
            "total_return": round(total_return * 100, 2),
            "benchmark_total_return": round(bm_total_return * 100, 2) if bm_total_return is not None else None,
            "cagr": round(cagr * 100, 2),
            "benchmark_cagr": round(bm_cagr * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 3),
            "annual_returns": {str(k): round(v * 100, 2) for k, v in annual_returns.items()},
            "annual_benchmark_returns": {str(k): round(v * 100, 2) for k, v in annual_bm_returns.items()},
            "annual_excess_returns": {str(k): round(v * 100, 2) for k, v in annual_excess.items()},
            "return_std_across_years": round(return_variance * 100, 2),
            "negative_years": negative_years,
            "positive_year_ratio": round(positive_year_ratio * 100, 1),
            "beat_benchmark_rate": round(beat_rate * 100, 1),
            "cumulative_vs_benchmark": round((total_return / bm_total_return) if bm_total_return and bm_total_return > 0 else 0, 2),
            "years_tested": len(annual_returns),
        }
        return self.metrics

    def save(self, output_dir: str):
        """Save results to files."""
        os.makedirs(output_dir, exist_ok=True)
        safe_name = self.strategy_name.replace(" ", "_").replace("/", "_").lower()

        if self.equity_curve is not None:
            self.equity_curve.to_csv(os.path.join(output_dir, f"{safe_name}_equity.csv"))
        if self.benchmark_curve is not None:
            self.benchmark_curve.to_csv(os.path.join(output_dir, f"{safe_name}_benchmark.csv"))
        if self.weights_history is not None:
            self.weights_history.to_csv(os.path.join(output_dir, f"{safe_name}_weights.csv"))

        with open(os.path.join(output_dir, f"{safe_name}_metrics.json"), "w") as f:
            json.dump({"strategy": self.strategy_name, "config": self.config, "metrics": self.metrics}, f, indent=2)

        return os.path.join(output_dir, f"{safe_name}_metrics.json")


class BacktestEngine:
    """Core backtesting engine for portfolio allocation strategies."""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._price_cache = {}

    def fetch_prices(self, tickers: List[str], start: str = None, end: str = None) -> pd.DataFrame:
        """Fetch adjusted close prices for a list of tickers."""
        import yfinance as yf
        import time as _time

        start = start or self.config.start_date
        end = end or self.config.end_date

        # Need extra history for lookback calculations
        from dateutil.relativedelta import relativedelta
        fetch_start = (pd.Timestamp(start) - relativedelta(months=18)).strftime("%Y-%m-%d")

        cache_key = (tuple(sorted(tickers)), fetch_start, end)
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        # Check for cached parquet file
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "strategy_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"prices_{fetch_start}_{end}_{len(tickers)}.parquet")

        if os.path.exists(cache_file):
            print(f"  Loading cached prices from {cache_file}")
            prices = pd.read_parquet(cache_file)
            self._price_cache[cache_key] = prices
            return prices

        print(f"  Fetching prices for {len(tickers)} tickers from {fetch_start} to {end}...")

        # Batch downloads to avoid rate limiting
        batch_size = 8
        all_frames = []
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            print(f"    Batch {i // batch_size + 1}: {batch}")
            retries = 3
            for attempt in range(retries):
                try:
                    data = yf.download(batch, start=fetch_start, end=end, auto_adjust=True, progress=False)
                    if isinstance(data.columns, pd.MultiIndex):
                        batch_prices = data["Close"]
                    else:
                        batch_prices = data[["Close"]]
                        batch_prices.columns = batch
                    all_frames.append(batch_prices)
                    break
                except Exception as e:
                    print(f"    Retry {attempt + 1}/{retries}: {e}")
                    _time.sleep(2 ** (attempt + 1))
            _time.sleep(1.5)  # Rate limiting pause between batches

        if not all_frames:
            return pd.DataFrame()

        prices = pd.concat(all_frames, axis=1)
        prices = prices.ffill().dropna(how="all")

        # Cache to parquet
        try:
            prices.to_parquet(cache_file)
            print(f"  Cached prices to {cache_file}")
        except Exception:
            pass

        self._price_cache[cache_key] = prices
        return prices

    def get_rebalance_dates(self, prices: pd.DataFrame, start: str = None) -> List[pd.Timestamp]:
        """Get rebalance dates based on frequency."""
        start = pd.Timestamp(start or self.config.start_date)
        dates = prices.index[prices.index >= start]

        if self.config.rebalance_frequency == "daily":
            return list(dates)
        elif self.config.rebalance_frequency == "weekly":
            # Last trading day of each week
            weekly = dates.to_series().groupby(dates.to_period("W")).last()
            return list(weekly.values)
        elif self.config.rebalance_frequency == "monthly":
            # Last trading day of each month
            monthly = dates.to_series().groupby(dates.to_period("M")).last()
            return list(monthly.values)
        elif self.config.rebalance_frequency == "quarterly":
            quarterly = dates.to_series().groupby(dates.to_period("Q")).last()
            return list(quarterly.values)
        else:
            raise ValueError(f"Unknown frequency: {self.config.rebalance_frequency}")

    def run(self, strategy_fn: Callable, prices: pd.DataFrame,
            strategy_name: str = "Strategy", strategy_config: dict = None) -> BacktestResult:
        """
        Run a backtest.

        strategy_fn(prices_up_to_date, current_date, **kwargs) -> dict of {ticker: weight}
        Weights should sum to <= 1.0 (remainder is cash).
        """
        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)

        # Filter prices to valid range
        all_dates = prices.index[(prices.index >= start) & (prices.index <= end)]
        if len(all_dates) == 0:
            print(f"  WARNING: No data in range {start} to {end}")
            return BacktestResult(strategy_name=strategy_name, config=strategy_config or {})

        rebalance_dates = set(self.get_rebalance_dates(prices, start=self.config.start_date))

        # Track portfolio
        capital = self.config.initial_capital
        holdings = {}  # ticker -> shares
        equity_curve = {}
        weights_history = {}
        current_weights = {}

        tc_rate = (self.config.transaction_cost_bps + self.config.slippage_bps) / 10000

        # Get benchmark
        benchmark_prices = None
        if self.config.benchmark in prices.columns:
            benchmark_prices = prices[self.config.benchmark]

        for date in all_dates:
            # Current portfolio value
            port_value = capital
            for ticker, shares in holdings.items():
                if ticker in prices.columns and not pd.isna(prices.loc[date, ticker]):
                    port_value += shares * prices.loc[date, ticker]

            equity_curve[date] = port_value

            # Rebalance if needed
            if date in rebalance_dates:
                # Get target weights from strategy
                prices_available = prices[prices.index <= date]
                try:
                    target_weights = strategy_fn(prices_available, date)
                except Exception as e:
                    # Strategy can't compute yet (not enough history)
                    continue

                if target_weights is None:
                    continue

                # Calculate current weights
                current_vals = {}
                for ticker, shares in holdings.items():
                    if ticker in prices.columns and not pd.isna(prices.loc[date, ticker]):
                        current_vals[ticker] = shares * prices.loc[date, ticker]

                # Sell everything first (simplified rebalance)
                total_proceeds = capital
                for ticker, shares in holdings.items():
                    if ticker in prices.columns and not pd.isna(prices.loc[date, ticker]):
                        sale_value = shares * prices.loc[date, ticker]
                        total_proceeds += sale_value * (1 - tc_rate)

                # Buy new positions
                # Account for transaction costs in allocation: investable = proceeds / (1 + tc)
                holdings = {}
                capital = total_proceeds
                total_weight = sum(w for w in target_weights.values() if w > 0)
                if total_weight > 0:
                    investable = total_proceeds / (1 + tc_rate)  # Max we can invest after costs
                    for ticker, weight in target_weights.items():
                        if weight > 0 and ticker in prices.columns and not pd.isna(prices.loc[date, ticker]):
                            alloc = investable * weight
                            cost = alloc * (1 + tc_rate)
                            shares = alloc / prices.loc[date, ticker]
                            holdings[ticker] = shares
                            capital -= cost

                current_weights = target_weights
                weights_history[date] = target_weights

        # Build equity series
        eq_series = pd.Series(equity_curve).sort_index()

        # Build benchmark equity
        bm_series = None
        if benchmark_prices is not None:
            bm_start = benchmark_prices.loc[benchmark_prices.index >= start]
            if len(bm_start) > 0:
                bm_series = bm_start / bm_start.iloc[0] * self.config.initial_capital

        # Build weights dataframe
        weights_df = pd.DataFrame(weights_history).T if weights_history else None

        result = BacktestResult(
            strategy_name=strategy_name,
            config=strategy_config or {},
            equity_curve=eq_series,
            benchmark_curve=bm_series,
            weights_history=weights_df,
        )
        result.compute_metrics()
        return result


def fetch_fred_data(series_ids: Dict[str, str], start: str = "2016-01-01", end: str = "2025-12-31") -> pd.DataFrame:
    """Fetch data from FRED using pandas_datareader or direct CSV download."""
    frames = {}
    for name, series_id in series_ids.items():
        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}&coed={end}"
            df = pd.read_csv(url, parse_dates=["DATE"], index_col="DATE")
            df.columns = [name]
            # FRED uses '.' for missing values
            df = df.replace(".", np.nan).astype(float)
            frames[name] = df[name]
        except Exception as e:
            print(f"  Warning: Could not fetch FRED series {series_id}: {e}")
    if frames:
        return pd.DataFrame(frames).ffill()
    return pd.DataFrame()


def compute_momentum(prices: pd.Series, lookback: int = 252, skip: int = 21) -> pd.Series:
    """Compute momentum with recent month skip (standard academic approach)."""
    if skip > 0:
        return prices.shift(skip) / prices.shift(lookback) - 1
    return prices / prices.shift(lookback) - 1


def compute_volatility(returns: pd.Series, window: int = 63) -> pd.Series:
    """Compute rolling annualized volatility."""
    return returns.rolling(window).std() * np.sqrt(252)


def compute_sma(prices: pd.Series, window: int = 200) -> pd.Series:
    """Simple moving average."""
    return prices.rolling(window).mean()


def compute_ema(prices: pd.Series, span: int = 50) -> pd.Series:
    """Exponential moving average."""
    return prices.ewm(span=span).mean()


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
