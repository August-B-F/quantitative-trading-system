# FINAL RECOMMENDATION
Generated: 2026-04-11 19:44:58

## Methodology

Strategies scored on composite metric weighting:
- Consistency (positive years, low year-to-year variance): 50% weight
- Risk-adjusted returns (Sharpe ratio): 20% weight
- Outperformance vs S&P 500: 15% weight
- Drawdown protection: 15% weight

Total strategies evaluated: 316

## Top 5 Recommendations

### #1: FN_abs_mom_optimized (Score: 11.16)

**Performance:**
- CAGR: 22.99% (SPY: 14.23%)
- Total Return: 422.56% (SPY: 189.62%)
- Sharpe Ratio: 0.962
- Max Drawdown: -28.39%
- Cumulative vs SPY: 2.23x

**Consistency:**
- Negative Years: 0
- Return Std Across Years: 10.36%
- Beat Benchmark Rate: 75.0%

**Annual Returns:**
  2018:     7.6% (SPY:    -5.2%) +
  2019:    11.6% (SPY:    31.1%)  
  2020:    32.0% (SPY:    17.2%) +
  2021:    39.0% (SPY:    30.5%) +
  2022:    17.4% (SPY:   -18.6%) +
  2023:    23.5% (SPY:    26.7%)  
  2024:    32.1% (SPY:    25.6%) +
  2025:    29.8% (SPY:    18.9%) +

**Configuration:** {}

### #2: FN_absmom_lb63_n5 (Score: 11.16)

**Performance:**
- CAGR: 22.99% (SPY: 14.23%)
- Total Return: 422.56% (SPY: 189.62%)
- Sharpe Ratio: 0.962
- Max Drawdown: -28.39%
- Cumulative vs SPY: 2.23x

**Consistency:**
- Negative Years: 0
- Return Std Across Years: 10.36%
- Beat Benchmark Rate: 75.0%

**Annual Returns:**
  2018:     7.6% (SPY:    -5.2%) +
  2019:    11.6% (SPY:    31.1%)  
  2020:    32.0% (SPY:    17.2%) +
  2021:    39.0% (SPY:    30.5%) +
  2022:    17.4% (SPY:   -18.6%) +
  2023:    23.5% (SPY:    26.7%)  
  2024:    32.1% (SPY:    25.6%) +
  2025:    29.8% (SPY:    18.9%) +

**Configuration:** {"growth": ["SOXX", "QQQ", "XLK", "VGT", "IGV"], "lookback": 63}

### #3: FN_abs_mom_growth_energy (Score: 10.12)

**Performance:**
- CAGR: 22.67% (SPY: 14.23%)
- Total Return: 411.8% (SPY: 189.62%)
- Sharpe Ratio: 0.935
- Max Drawdown: -27.67%
- Cumulative vs SPY: 2.17x

**Consistency:**
- Negative Years: 1
- Return Std Across Years: 18.38%
- Beat Benchmark Rate: 62.5%

**Annual Returns:**
  2018:     8.1% (SPY:    -5.2%) +
  2019:    22.6% (SPY:    31.1%)  
  2020:    32.0% (SPY:    17.2%) +
  2021:    25.9% (SPY:    30.5%)  
  2022:   -11.6% (SPY:   -18.6%) +
  2023:    25.7% (SPY:    26.7%)  
  2024:    53.2% (SPY:    25.6%) +
  2025:    40.0% (SPY:    18.9%) +

**Configuration:** {}

### #4: FN_absmom_lb63_n3 (Score: 8.74)

**Performance:**
- CAGR: 17.59% (SPY: 14.23%)
- Total Return: 265.08% (SPY: 189.62%)
- Sharpe Ratio: 0.776
- Max Drawdown: -29.82%
- Cumulative vs SPY: 1.4x

**Consistency:**
- Negative Years: 1
- Return Std Across Years: 12.02%
- Beat Benchmark Rate: 37.5%

**Annual Returns:**
  2018:    -9.0% (SPY:    -5.2%)  
  2019:    20.2% (SPY:    31.1%)  
  2020:    29.3% (SPY:    17.2%) +
  2021:    23.5% (SPY:    30.5%)  
  2022:    17.4% (SPY:   -18.6%) +
  2023:    24.3% (SPY:    26.7%)  
  2024:    13.2% (SPY:    25.6%)  
  2025:    32.5% (SPY:    18.9%) +

**Configuration:** {"growth": ["SOXX", "QQQ", "XLK"], "lookback": 63}

### #5: FN_absmom_lb63_n2 (Score: 8.55)

**Performance:**
- CAGR: 17.15% (SPY: 14.23%)
- Total Return: 254.19% (SPY: 189.62%)
- Sharpe Ratio: 0.756
- Max Drawdown: -30.45%
- Cumulative vs SPY: 1.34x

**Consistency:**
- Negative Years: 1
- Return Std Across Years: 12.26%
- Beat Benchmark Rate: 37.5%

**Annual Returns:**
  2018:    -9.6% (SPY:    -5.2%)  
  2019:    20.2% (SPY:    31.1%)  
  2020:    31.0% (SPY:    17.2%) +
  2021:    22.4% (SPY:    30.5%)  
  2022:    17.4% (SPY:   -18.6%) +
  2023:    21.5% (SPY:    26.7%)  
  2024:    12.6% (SPY:    25.6%)  
  2025:    32.5% (SPY:    18.9%) +

**Configuration:** {"growth": ["SOXX", "QQQ"], "lookback": 63}

## Data Sources
- **Price Data**: Yahoo Finance (via yfinance) - adjusted close prices
- **Asset Universe**: US equity ETFs (SPY, QQQ, sector ETFs), international (EFA, EEM),
  bonds (TLT, IEF, AGG, SHY, BIL), commodities (GLD, DBC), REITs (VNQ),
  factor ETFs (QUAL, MTUM, VUG, VLUE, USMV)
- **Benchmark**: S&P 500 (SPY)

## Replication Steps
1. Install dependencies: `pip install yfinance pandas numpy`
2. Run: `cd strategies && python run_all_backtests.py`
3. Results will be in `/results/` directory

## Caveats
- Transaction costs modeled at 10bps round-trip (5bps costs + 5bps slippage)
- No leverage used in any strategy
- All data is adjusted for splits and dividends
- Monthly rebalancing unless otherwise noted
- Survivorship bias: ETFs that exist today may not have existed at backtest start
- Past performance does not guarantee future results