"""Assembles per-symbol feature matrices and labels for model training/inference."""
import os
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from sklearn.preprocessing import RobustScaler
from ultimate_trader.features.technicals import add_technicals
from ultimate_trader.features.sentiment import build_sentiment_features
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)


def _sanitize_array(arr: np.ndarray) -> np.ndarray:
    """Replace inf/-inf with 0 and NaN with 0 in float arrays."""
    arr = np.where(np.isfinite(arr), arr, 0.0)
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

# Technical feature columns fed to model (30 original + 10 new = 40 total)
TECH_FEATURES = [
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "vol_5d", "vol_20d",
    "rsi_14", "rsi_28",
    "macd", "macd_signal", "macd_hist",
    "bb_width", "bb_pct_b",
    "atr_pct",
    "obv_change_5d",
    "volume_anomaly",
    "sma_50_200_ratio", "price_vs_sma50", "price_vs_sma200",
    "stoch_k", "stoch_d",
    "williams_r",
    "momentum_10", "momentum_20",
    "price_range_20d",
    # Earnings proximity features
    "days_to_earnings",
    "earnings_flag",
    # Inter-symbol correlation features
    "corr_spy_20d",
    "corr_sector_20d",
    # New indicators
    "vwap_dev",
    "mfi_14",
    "cmf_20",
    "elder_bull",
    "elder_bear",
    "ichi_tenkan",
    "ichi_kijun",
    "ichi_senkou_a",
    "ichi_senkou_b",
    "ichi_chikou",
    # Sector relative momentum (sector ETF return - SPY return)
    "sector_rel_momentum_5d",
    "sector_rel_momentum_20d",
]

SENTIMENT_FEATURES = [
    "avg_score", "score_std", "pos_ratio", "neg_ratio",
    "sentiment_momentum_3d", "sentiment_momentum_5d",
    "sentiment_vol_5d", "news_surge",
]

# Macro features including GDELT sentiment (14 total: 11 original + 3 GDELT)
MACRO_FEATURES = [
    "spy_return_1d", "spy_return_5d", "spy_vol_20d", "spy_trend",
    "vix_level", "vix_change_1d", "vix_regime_pct",
    "yield_proxy", "yield_change_5d",
    "oil_return_5d", "gold_return_5d",
    # GDELT market sentiment
    "gdelt_avg_tone", "gdelt_article_count", "gdelt_goldstein_scale",
]

# Fundamental features (static per symbol per day, passed to fundamentals MLP branch)
FUNDAMENTAL_FEATURES = [
    "pe_ratio",
    "eps_growth_yoy",
    "revenue_growth_yoy",
    "debt_equity",
    "free_cash_flow_yield",
    "insider_buy_ratio",
]


def _add_earnings_features(
    df: pd.DataFrame,
    earnings_dates: Optional[Dict[str, List[str]]],
    symbol: str,
) -> pd.DataFrame:
    """
    Add days_to_earnings and earnings_flag columns.
    - days_to_earnings: normalised distance to nearest upcoming earnings (0=today, 1=30+days)
    - earnings_flag: 1 if earnings within 3 days, else 0
    """
    df = df.copy()
    df["days_to_earnings"] = 1.0  # default: no upcoming earnings known
    df["earnings_flag"] = 0.0

    if not earnings_dates:
        return df

    dates_list = earnings_dates.get(symbol, [])
    if not dates_list:
        return df

    parsed = []
    for d in dates_list:
        try:
            parsed.append(pd.Timestamp(d))
        except Exception:
            pass
    if not parsed:
        return df

    for ts in df.index:
        future = [e for e in parsed if e >= ts]
        if future:
            nearest = min(future)
            delta = (nearest - ts).days
            df.at[ts, "days_to_earnings"] = min(delta / 30.0, 1.0)
            df.at[ts, "earnings_flag"] = 1.0 if delta <= 3 else 0.0
    return df


def _add_correlation_features(
    df: pd.DataFrame,
    symbol: str,
    bars: Dict[str, pd.DataFrame],
    symbol_to_sector_etf: Optional[Dict[str, str]] = None,
    window: int = 20,
) -> pd.DataFrame:
    """Add rolling correlation vs SPY and vs the symbol's sector ETF."""
    df = df.copy()
    sym_ret = df["close"].pct_change() if "close" in df.columns else None

    spy = bars.get("SPY")
    if spy is not None and sym_ret is not None:
        spy_ret = spy["close"].pct_change().reindex(df.index)
        df["corr_spy_20d"] = sym_ret.rolling(window).corr(spy_ret).fillna(0.0)
    else:
        df["corr_spy_20d"] = 0.0

    sector_etf = (symbol_to_sector_etf or {}).get(symbol)
    if sector_etf and sector_etf in bars and sym_ret is not None:
        sec_ret = bars[sector_etf]["close"].pct_change().reindex(df.index)
        df["corr_sector_20d"] = sym_ret.rolling(window).corr(sec_ret).fillna(0.0)
    else:
        df["corr_sector_20d"] = df.get("corr_spy_20d", pd.Series(0.0, index=df.index))

    # Sector relative momentum: sector ETF return vs SPY (rotation factor)
    for w in [5, 20]:
        col = f"sector_rel_momentum_{w}d"
        if sector_etf and sector_etf in bars and spy is not None:
            sec_ret_w = bars[sector_etf]["close"].reindex(df.index).ffill().pct_change(w)
            spy_ret_w = spy["close"].reindex(df.index).ffill().pct_change(w)
            df[col] = (sec_ret_w - spy_ret_w).fillna(0.0)
        else:
            df[col] = 0.0

    return df


SECTOR_ETF_MAP = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AVGO": "XLK",
    "ORCL": "XLK", "CRM": "XLK", "ADBE": "XLK", "AMD": "XLK",
    "INTC": "XLK", "QCOM": "XLK", "TXN": "XLK", "ACN": "XLK",
    "INTU": "XLK", "NOW": "XLK", "CSCO": "XLK",
    "JPM": "XLF", "BAC": "XLF", "GS": "XLF", "V": "XLF", "MA": "XLF", "SPGI": "XLF",
    "UNH": "XLV", "LLY": "XLV", "JNJ": "XLV", "ABT": "XLV", "MRK": "XLV",
    "ABBV": "XLV", "TMO": "XLV", "DHR": "XLV", "AMGN": "XLV",
    "XOM": "XLE", "CVX": "XLE",
    "WMT": "XLP", "KO": "XLP", "PG": "XLP", "COST": "XLP", "PEP": "XLP", "PM": "XLP",
    "AMZN": "XLY", "TSLA": "XLY", "MCD": "XLY", "NKE": "XLY", "HD": "XLY",
    "META": "XLC", "GOOGL": "XLC", "NFLX": "XLC",
    "RTX": "XLI", "UPS": "XLI", "LIN": "XLI", "NEE": "XLI",
}


class FeatureBuilder:
    """
    Builds windowed feature arrays and labels for model training/inference.

    Scaler fit/transform separation:
      - fit_scalers() is called ONCE on training-fold data
      - All subsequent calls use transform() only
      - Scalers are saved to disk and reloaded at inference

    Branches:
      - tech: 40 technical indicators, windowed (price_window)
      - sent: 8 sentiment features, windowed (sentiment_window)
      - macro: 14 macro features (incl. GDELT), windowed (macro_window)
      - fund: 6 fundamental features, static (not windowed)
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.price_window = cfg.model.price_window
        self.sentiment_window = cfg.model.sentiment_window
        self.macro_window = cfg.model.macro_window
        self.horizon = cfg.targets.horizon_days
        self.r_hi = cfg.targets.r_hi
        self.r_lo = cfg.targets.r_lo
        self.scalers_dir = cfg.paths.scalers_dir
        os.makedirs(self.scalers_dir, exist_ok=True)

        self.tech_scaler = RobustScaler()
        self.sent_scaler = RobustScaler()
        self.macro_scaler = RobustScaler()
        self.fund_scaler = RobustScaler()
        self._fitted = False

    def fit_scalers(self, all_tech: np.ndarray, all_sent: np.ndarray,
                    all_macro: np.ndarray, all_fund: Optional[np.ndarray] = None):
        """Fit scalers on TRAINING data only. Call once, then save."""
        self.tech_scaler.fit(all_tech.reshape(-1, all_tech.shape[-1]))
        self.sent_scaler.fit(all_sent.reshape(-1, all_sent.shape[-1]))
        if all_macro.shape[-1] > 0:
            self.macro_scaler.fit(all_macro.reshape(-1, all_macro.shape[-1]))
        if all_fund is not None and all_fund.shape[-1] > 0:
            self.fund_scaler.fit(all_fund.reshape(-1, all_fund.shape[-1]))
        self._fitted = True
        self._save_scalers()
        logger.info("Feature scalers fitted and saved")

    def _save_scalers(self):
        for name, scaler in [("tech", self.tech_scaler),
                              ("sent", self.sent_scaler),
                              ("macro", self.macro_scaler),
                              ("fund", self.fund_scaler)]:
            with open(os.path.join(self.scalers_dir, f"{name}_scaler.pkl"), "wb") as f:
                pickle.dump(scaler, f)

    def load_scalers(self):
        for name, attr in [("tech", "tech_scaler"),
                            ("sent", "sent_scaler"),
                            ("macro", "macro_scaler"),
                            ("fund", "fund_scaler")]:
            path = os.path.join(self.scalers_dir, f"{name}_scaler.pkl")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    setattr(self, attr, pickle.load(f))
        self._fitted = True
        logger.info("Feature scalers loaded from disk")

    def build_features(
        self,
        bars: Dict[str, pd.DataFrame],
        sentiment: Dict[str, pd.DataFrame],
        macro_df: pd.DataFrame,
        symbols: List[str],
        symbol_to_idx: Dict[str, int],
        symbol_to_sector: Dict[str, int],
        earnings_dates: Optional[Dict[str, List[str]]] = None,
        fundamentals: Optional[Dict[str, pd.DataFrame]] = None,
        fit: bool = False,
    ) -> Tuple[dict, Optional[dict]]:
        tech_pool, sent_pool, macro_pool, fund_pool = [], [], [], []
        raw = {}

        for symbol in symbols:
            if symbol not in bars:
                continue

            df = bars[symbol].copy()
            df = add_technicals(df)
            df = _add_earnings_features(df, earnings_dates, symbol)
            df = _add_correlation_features(df, symbol, bars, SECTOR_ETF_MAP)

            macro_aligned = macro_df.reindex(df.index).ffill().fillna(0)
            sent_df = sentiment.get(symbol, pd.DataFrame()).reindex(df.index).fillna(0)
            sent_cols = [c for c in SENTIMENT_FEATURES if c in sent_df.columns]
            sent_arr = sent_df[sent_cols].values if sent_cols else np.zeros((len(df), len(SENTIMENT_FEATURES)))

            tech_arr = _sanitize_array(df[[c for c in TECH_FEATURES if c in df.columns]].values.astype(np.float32))
            macro_arr = _sanitize_array(macro_aligned[[c for c in MACRO_FEATURES if c in macro_aligned.columns]].values.astype(np.float32))

            # Fundamentals (daily, aligned to bar dates)
            fund_arr = _align_fundamentals(fundamentals, symbol, df.index)

            raw[symbol] = {
                "tech": tech_arr, "sent": sent_arr, "macro": macro_arr, "fund": fund_arr,
                "index": df.index, "close": df["close"].values,
                "sym_idx": symbol_to_idx.get(symbol, 0),
                "sec_idx": symbol_to_sector.get(symbol, 0),
            }
            tech_pool.append(tech_arr)
            sent_pool.append(sent_arr)
            macro_pool.append(macro_arr)
            fund_pool.append(fund_arr)

        if fit and tech_pool:
            self.fit_scalers(
                np.concatenate(tech_pool),
                np.concatenate(sent_pool),
                np.concatenate(macro_pool),
                np.concatenate(fund_pool) if fund_pool else None,
            )

        features, labels = {}, {}
        for symbol, data in raw.items():
            tech_s = self.tech_scaler.transform(data["tech"]) if self._fitted else data["tech"]
            sent_s = self.sent_scaler.transform(data["sent"]) if self._fitted else data["sent"]
            macro_s = self.macro_scaler.transform(data["macro"]) if self._fitted and data["macro"].shape[-1] > 0 else data["macro"]
            fund_s = self.fund_scaler.transform(data["fund"]) if self._fitted and data["fund"].shape[-1] > 0 else data["fund"]

            features[symbol] = {
                "tech":    tech_s[-self.price_window:],
                "sent":    sent_s[-self.sentiment_window:],
                "macro":   macro_s[-self.macro_window:],
                "fund":    fund_s[-1] if len(fund_s) > 0 else np.zeros(len(FUNDAMENTAL_FEATURES), dtype=np.float32),
                "sym_idx": data["sym_idx"],
                "sec_idx": data["sec_idx"],
            }
            close = data["close"]
            if len(close) > self.horizon:
                future_ret = (close[-1] / close[-(self.horizon + 1)] - 1)
                # Use last available vol for volatility-normalized label
                close_s_inf = pd.Series(close)
                ret_s_inf   = close_s_inf.pct_change()
                cv = float(ret_s_inf.rolling(20).std().iloc[-1])
                lv = float(ret_s_inf.rolling(252).std().iloc[-1])
                cv = cv if not np.isnan(cv) else None
                lv = lv if not np.isnan(lv) else None
                labels[symbol] = self._label(future_ret, current_vol=cv, long_term_vol=lv)

        return features, labels

    def _label(self, ret: float,
               current_vol: float = None, long_term_vol: float = None) -> int:
        """
        5-class label: 0=strong_sell … 4=strong_buy.
        Thresholds scale with realised volatility so labels remain consistent
        across high-vol (VIX 40) and low-vol (VIX 12) regimes.
        scale = clip(vol_20d / vol_252d, 0.5, 3.0)
        """
        if current_vol and long_term_vol and long_term_vol > 1e-9:
            scale = float(np.clip(current_vol / long_term_vol, 0.5, 3.0))
            r_hi = self.r_hi * scale
            r_lo = self.r_lo * scale
        else:
            r_hi, r_lo = self.r_hi, self.r_lo

        if ret > r_hi:       return 4
        elif ret > r_lo:     return 3
        elif ret >= -r_lo:   return 2
        elif ret >= -r_hi:   return 1
        else:                return 0

    def build_training_samples(
        self,
        bars: Dict[str, pd.DataFrame],
        sentiment: Dict[str, pd.DataFrame],
        macro_df: pd.DataFrame,
        symbols: List[str],
        symbol_to_idx: Dict[str, int],
        symbol_to_sector: Dict[str, int],
        date_range: pd.DatetimeIndex,
        fit_scalers: bool = False,
        earnings_dates: Optional[Dict[str, List[str]]] = None,
        fundamentals: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Tuple[List, List[int]]:
        """
        Builds (feature_dict, label) samples over all symbols x all dates.

        Each sample dict includes:
          tech, sent, macro, fund, sym_idx, sec_idx, date, regime_idx (default 0)

        Scaler safety:
          fit_scalers=True  -> fit ONLY on this date_range (training fold)
          fit_scalers=False -> transform only (validation / inference)
        """
        samples, label_list = [], []
        tech_pool, sent_pool, macro_pool, fund_pool = [], [], [], []
        raw_data = {}

        for symbol in symbols:
            if symbol not in bars:
                continue
            df = bars[symbol].copy()
            df = add_technicals(df)
            df = _add_earnings_features(df, earnings_dates, symbol)
            df = _add_correlation_features(df, symbol, bars, SECTOR_ETF_MAP)

            macro_aligned = macro_df.reindex(df.index).ffill().fillna(0)
            sent_df = sentiment.get(symbol, pd.DataFrame()).reindex(df.index).fillna(0)
            sent_cols = [c for c in SENTIMENT_FEATURES if c in sent_df.columns]

            tech_arr = _sanitize_array(df[[c for c in TECH_FEATURES if c in df.columns]].values.astype(np.float32))
            sent_arr = _sanitize_array(sent_df[sent_cols].values if sent_cols
                        else np.zeros((len(df), len(SENTIMENT_FEATURES)), dtype=np.float32))
            macro_arr = _sanitize_array(macro_aligned[[c for c in MACRO_FEATURES
                                        if c in macro_aligned.columns]].values.astype(np.float32))
            fund_arr = _align_fundamentals(fundamentals, symbol, df.index)

            date_mask = pd.Series(df.index).isin(date_range).values
            raw_data[symbol] = {
                "tech": tech_arr, "sent": sent_arr, "macro": macro_arr, "fund": fund_arr,
                "dates": df.index, "close": df["close"].values,
                "sym_idx": symbol_to_idx.get(symbol, 0),
                "sec_idx": symbol_to_sector.get(symbol, 0),
                "date_mask": date_mask,
            }

            if fit_scalers:
                tech_pool.append(tech_arr[date_mask])
                sent_pool.append(sent_arr[date_mask])
                macro_pool.append(macro_arr[date_mask])
                if len(fund_arr) > 0:
                    fund_pool.append(fund_arr[date_mask])

        if fit_scalers and tech_pool:
            self.fit_scalers(
                np.concatenate([t for t in tech_pool if len(t) > 0]),
                np.concatenate([s for s in sent_pool if len(s) > 0]),
                np.concatenate([m for m in macro_pool if len(m) > 0]),
                np.concatenate([f for f in fund_pool if len(f) > 0]) if fund_pool else None,
            )

        for symbol, data in raw_data.items():
            dates = data["dates"]
            close = data["close"]

            tech_s = self.tech_scaler.transform(data["tech"]) if self._fitted else data["tech"]
            sent_s = self.sent_scaler.transform(data["sent"]) if self._fitted else data["sent"]
            macro_s = self.macro_scaler.transform(data["macro"]) if self._fitted else data["macro"]
            fund_data = data["fund"]
            fund_s = (self.fund_scaler.transform(fund_data)
                      if self._fitted and fund_data.shape[-1] > 0 else fund_data)

            # Pre-compute rolling vol series for volatility-normalized labels
            close_s = pd.Series(close, index=dates)
            ret_s   = close_s.pct_change()
            vol_20  = ret_s.rolling(20).std()
            vol_252 = ret_s.rolling(252).std()

            for i, date in enumerate(dates):
                if date not in date_range:
                    continue
                if i < max(self.price_window, self.sentiment_window, self.macro_window):
                    continue
                if i + self.horizon >= len(close):
                    continue

                future_ret = close[i + self.horizon] / close[i] - 1
                cv = float(vol_20.iloc[i]) if not np.isnan(vol_20.iloc[i]) else None
                lv = float(vol_252.iloc[i]) if not np.isnan(vol_252.iloc[i]) else None
                label = self._label(future_ret, current_vol=cv, long_term_vol=lv)

                # Fundamentals: single row at index i (static for this date)
                if len(fund_s) > i:
                    fund_vec = fund_s[i].astype(np.float32)
                else:
                    fund_vec = np.zeros(len(FUNDAMENTAL_FEATURES), dtype=np.float32)

                sample = {
                    "tech":    tech_s[i - self.price_window:i].astype(np.float32),
                    "sent":    sent_s[i - self.sentiment_window:i].astype(np.float32),
                    "macro":   macro_s[i - self.macro_window:i].astype(np.float32),
                    "fund":    fund_vec,
                    "sym_idx": data["sym_idx"],
                    "sec_idx": data["sec_idx"],
                    "date":    date,        # FIX: stored for regime label lookup in train.py
                    "regime_idx": 0,        # Default; overwritten by assign_regime_labels
                }
                samples.append(sample)
                label_list.append(label)

        logger.info(f"Built {len(samples)} training samples")
        return samples, label_list


def _align_fundamentals(
    fundamentals: Optional[Dict[str, pd.DataFrame]],
    symbol: str,
    index: pd.DatetimeIndex,
) -> np.ndarray:
    """
    Align fundamentals DataFrame to the bar's date index.
    Returns (len(index), len(FUNDAMENTAL_FEATURES)) float32 array of zeros if unavailable.
    """
    n = len(index)
    n_feat = len(FUNDAMENTAL_FEATURES)
    empty = np.zeros((n, n_feat), dtype=np.float32)

    if fundamentals is None:
        return empty

    fund_df = fundamentals.get(symbol)
    if fund_df is None or (hasattr(fund_df, "empty") and fund_df.empty):
        return empty

    try:
        cols = [c for c in FUNDAMENTAL_FEATURES if c in fund_df.columns]
        if not cols:
            return empty
        aligned = _sanitize_array(fund_df[cols].reindex(index).ffill().fillna(0).values.astype(np.float32))
        # Pad if some features are missing
        if aligned.shape[1] < n_feat:
            pad = np.zeros((n, n_feat - aligned.shape[1]), dtype=np.float32)
            aligned = np.concatenate([aligned, pad], axis=1)
        return aligned[:, :n_feat]
    except Exception:
        return empty
