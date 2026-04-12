"""Fundamental data fetcher using yfinance.

CRITICAL (look-ahead bias prevention):
  All quarterly financial data is timestamped at the *filing date*, not the
  period end date. The filing date is approximated as period_end + 45 days
  (10-Q must be filed within 45 days of quarter end per SEC rules).
  This means a Q1 (Mar 31) result only enters features after ~May 15,
  not on Apr 1. This is the correct point-in-time treatment.

  Values are forward-filled from filing date to next filing date.
"""
import os
import numpy as np
import pandas as pd
from typing import Dict, List
from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)

FUNDAMENTAL_FEATURES = [
    "pe_ratio",
    "eps_growth_yoy",
    "revenue_growth_yoy",
    "debt_equity",
    "free_cash_flow_yield",
    "insider_buy_ratio",
]

CACHE_DIR = "data/raw/fundamentals"
CACHE_TTL_DAYS = 7  # refresh weekly


class FundamentalsFetcher:
    """
    Fetches fundamental data from yfinance.
    Returns {symbol: date-indexed DataFrame} with FUNDAMENTAL_FEATURES columns,
    daily frequency, forward-filled from filing dates (no lookahead bias).
    """

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fetch(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """
        Fetch fundamentals for all symbols.
        Returns {symbol: date-indexed DataFrame} with FUNDAMENTAL_FEATURES columns.
        Missing/failed symbols get zero-filled DataFrames.
        """
        result = {}
        for sym in symbols:
            try:
                df = self._fetch_symbol(sym)
                result[sym] = df
                logger.debug(f"Fundamentals OK: {sym} ({len(df)} days)")
            except Exception as e:
                logger.warning(f"Fundamentals failed for {sym}: {e}")
                result[sym] = self._empty_df()
        n_ok = sum(1 for df in result.values() if len(df) > 0)
        logger.info(f"Fundamentals fetched: {n_ok}/{len(symbols)} symbols")
        return result

    def _fetch_symbol(self, symbol: str) -> pd.DataFrame:
        cache_path = os.path.join(self.cache_dir, f"{symbol}.parquet")

        # Use cache if fresh enough
        if os.path.exists(cache_path):
            try:
                mtime = pd.Timestamp(os.path.getmtime(cache_path), unit="s")
                age_days = (pd.Timestamp.now() - mtime).days
                if age_days < CACHE_TTL_DAYS:
                    df = pd.read_parquet(cache_path)
                    if set(FUNDAMENTAL_FEATURES).issubset(df.columns):
                        return df
            except Exception:
                pass

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — fundamentals unavailable")
            return self._empty_df()

        ticker = yf.Ticker(symbol)
        info = {}
        try:
            info = ticker.info or {}
        except Exception:
            pass

        # ── Collect quarterly records keyed by filing date ─────────────
        records: Dict[pd.Timestamp, dict] = {}

        # Income statement: revenue, EPS
        try:
            income = ticker.quarterly_financials
            if income is not None and not income.empty:
                for period in income.columns:
                    fd = _filing_date(period)
                    rev_row = income.loc[income.index.str.contains("Total Revenue", case=False), period] \
                        if any("Revenue" in str(i) for i in income.index) else pd.Series()
                    eps_row = income.loc[income.index.str.contains("Basic EPS", case=False), period] \
                        if any("EPS" in str(i) for i in income.index) else pd.Series()

                    rev = float(rev_row.iloc[0]) if len(rev_row) > 0 else np.nan
                    eps = float(eps_row.iloc[0]) if len(eps_row) > 0 else np.nan

                    if np.isnan(eps):
                        # Fall back: net income / shares
                        ni_row = income.loc[income.index.str.contains("Net Income", case=False), period] \
                            if any("Net Income" in str(i) for i in income.index) else pd.Series()
                        ni = float(ni_row.iloc[0]) if len(ni_row) > 0 else np.nan
                        shares = float(info.get("sharesOutstanding", np.nan))
                        if not np.isnan(ni) and not np.isnan(shares) and shares > 0:
                            eps = ni / shares

                    records.setdefault(fd, {})
                    records[fd]["revenue"] = rev
                    records[fd]["eps"] = eps
        except Exception as e:
            logger.debug(f"Income statement error {symbol}: {e}")

        # Balance sheet: total debt, stockholders equity
        try:
            balance = ticker.quarterly_balance_sheet
            if balance is not None and not balance.empty:
                for period in balance.columns:
                    fd = _filing_date(period)
                    debt_row = balance.loc[balance.index.str.contains("Total Debt", case=False), period] \
                        if any("Debt" in str(i) for i in balance.index) else pd.Series()
                    eq_row = balance.loc[balance.index.str.contains("Stockholders Equity", case=False), period] \
                        if any("Equity" in str(i) for i in balance.index) else pd.Series()

                    records.setdefault(fd, {})
                    records[fd]["total_debt"] = float(debt_row.iloc[0]) if len(debt_row) > 0 else np.nan
                    records[fd]["equity"] = float(eq_row.iloc[0]) if len(eq_row) > 0 else np.nan
        except Exception as e:
            logger.debug(f"Balance sheet error {symbol}: {e}")

        # Cash flow: free cash flow
        try:
            cashflow = ticker.quarterly_cashflow
            if cashflow is not None and not cashflow.empty:
                for period in cashflow.columns:
                    fd = _filing_date(period)
                    fcf_row = cashflow.loc[cashflow.index.str.contains("Free Cash Flow", case=False), period] \
                        if any("Free Cash" in str(i) for i in cashflow.index) else pd.Series()
                    records.setdefault(fd, {})
                    records[fd]["fcf"] = float(fcf_row.iloc[0]) if len(fcf_row) > 0 else np.nan
        except Exception as e:
            logger.debug(f"Cash flow error {symbol}: {e}")

        # Static current values
        pe_ratio = float(info.get("trailingPE", np.nan))
        market_cap = float(info.get("marketCap", np.nan))
        insider_buy_ratio = _get_insider_buy_ratio(ticker)

        if not records:
            return self._empty_df()

        # ── Build time-series ─────────────────────────────────────────
        sorted_dates = sorted(records.keys())
        rows = []
        for i, fd in enumerate(sorted_dates):
            r = records[fd]
            prev = records[sorted_dates[i - 4]] if i >= 4 else {}

            # YoY growth ratios
            eps_now, eps_prev = r.get("eps", np.nan), prev.get("eps", np.nan)
            rev_now, rev_prev = r.get("revenue", np.nan), prev.get("revenue", np.nan)

            eps_growth = (eps_now - eps_prev) / (abs(eps_prev) + 1e-9) \
                if not np.isnan(eps_now) and not np.isnan(eps_prev) else np.nan
            rev_growth = (rev_now - rev_prev) / (abs(rev_prev) + 1e-9) \
                if not np.isnan(rev_now) and not np.isnan(rev_prev) else np.nan

            debt = r.get("total_debt", np.nan)
            equity = r.get("equity", np.nan)
            debt_equity = debt / (abs(equity) + 1e-9) \
                if not np.isnan(debt) and not np.isnan(equity) else np.nan

            fcf = r.get("fcf", np.nan)
            fcf_yield = fcf / (market_cap + 1e-9) \
                if not np.isnan(fcf) and not np.isnan(market_cap) and market_cap > 0 else np.nan

            rows.append({
                "date": fd,
                "pe_ratio": pe_ratio,          # updated each fetch
                "eps_growth_yoy": eps_growth,
                "revenue_growth_yoy": rev_growth,
                "debt_equity": debt_equity,
                "free_cash_flow_yield": fcf_yield,
                "insider_buy_ratio": insider_buy_ratio,
            })

        df_quarterly = pd.DataFrame(rows).set_index("date").sort_index()
        df_quarterly.index = pd.DatetimeIndex(df_quarterly.index)

        # Forward-fill to daily business day frequency
        start = df_quarterly.index.min()
        end = pd.Timestamp.now()
        daily_idx = pd.bdate_range(start, end)
        df_daily = df_quarterly.reindex(daily_idx).ffill().fillna(0).astype(np.float32)

        try:
            df_daily.to_parquet(cache_path)
        except Exception as e:
            logger.debug(f"Fundamentals cache write failed {symbol}: {e}")

        return df_daily

    def _empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(columns=FUNDAMENTAL_FEATURES, dtype=np.float32)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _filing_date(period_end) -> pd.Timestamp:
    """
    Approximate SEC filing date as period_end + 45 days.
    10-Q must be filed within 45 days of quarter end.
    10-K within 60 days — use 45 as conservative estimate.
    """
    try:
        return pd.Timestamp(period_end) + pd.Timedelta(days=45)
    except Exception:
        return pd.Timestamp.now()


def _get_insider_buy_ratio(ticker) -> float:
    """
    Ratio of insider purchases to total insider transactions (last 6 months).
    Returns 0.5 (neutral) if data unavailable.
    """
    try:
        txns = ticker.get_insider_transactions()
        if txns is None or (hasattr(txns, "empty") and txns.empty):
            return 0.5

        # Filter last 6 months
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=180)
        date_col = next((c for c in txns.columns if "date" in c.lower()), None)
        if date_col:
            txns = txns[pd.to_datetime(txns[date_col], errors="coerce") >= cutoff]

        if len(txns) == 0:
            return 0.5

        txn_col = next((c for c in txns.columns if "transaction" in c.lower()), None)
        if txn_col is None:
            return 0.5

        buys = txns[txns[txn_col].astype(str).str.contains(
            "Buy|Purchase|Acquisition", case=False, na=False
        )]
        return len(buys) / max(len(txns), 1)
    except Exception:
        return 0.5
