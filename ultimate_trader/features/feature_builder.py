"""Build aligned per-symbol feature matrices and label vectors for training and inference."""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.preprocessing import RobustScaler

from ultimate_trader.features.technicals import compute_all_technicals
from ultimate_trader.features.sentiment import build_sentiment_features
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)


def build_labels(
    close: pd.Series,
    horizon: int = 3,
    r_hi: float = 0.03,
    r_lo: float = 0.005,
) -> pd.Series:
    """
    5-class labels based on forward return over `horizon` days.
        4 = strong_buy   (ret > +r_hi)
        3 = buy          (+r_lo < ret <= +r_hi)
        2 = hold         (-r_lo <= ret <= +r_lo)
        1 = sell         (-r_hi <= ret < -r_lo)
        0 = strong_sell  (ret < -r_hi)
    """
    future_ret = close.shift(-horizon) / close - 1
    labels = pd.cut(
        future_ret,
        bins=[-np.inf, -r_hi, -r_lo, r_lo, r_hi, np.inf],
        labels=[0, 1, 2, 3, 4]
    ).astype("Int64")
    return labels.rename("label")


def build_symbol_features(
    symbol: str,
    bars: pd.DataFrame,
    benchmark_bars: Optional[pd.DataFrame],
    macro_data: Optional[Dict[str, pd.DataFrame]],
    news_raw_dir: str,
    scalers_dir: str,
    price_window: int = 40,
    sentiment_window: int = 20,
    macro_window: int = 20,
    horizon: int = 3,
    r_hi: float = 0.03,
    r_lo: float = 0.005,
    fit_scalers: bool = True,
) -> Tuple[dict, pd.Series]:
    """
    Build feature windows and labels for a single symbol.

    Returns:
        features_dict: dict with keys:
            'price_seq'     : (T, price_window, n_price_feats)
            'sentiment_seq' : (T, sentiment_window, n_sent_feats)
            'macro_seq'     : (T, macro_window, n_macro_feats)
            'company_id'    : int (symbol index for embedding)
        labels: pd.Series of int labels aligned to dates
    """
    scaler_path = Path(scalers_dir)
    scaler_path.mkdir(parents=True, exist_ok=True)

    benchmark_returns = benchmark_bars["close"].pct_change() if benchmark_bars is not None else None
    tech = compute_all_technicals(bars, benchmark_returns)

    # scale technicals — fit per symbol once during training, then reload
    tech_scaler_file = scaler_path / f"{symbol}_tech.pkl"
    tech_numeric = tech.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).fillna(0)
    if fit_scalers:
        tech_scaler = RobustScaler()
        tech_scaled = pd.DataFrame(
            tech_scaler.fit_transform(tech_numeric),
            columns=tech_numeric.columns, index=tech_numeric.index
        )
        joblib.dump(tech_scaler, tech_scaler_file)
    else:
        tech_scaler = joblib.load(tech_scaler_file)
        tech_scaled = pd.DataFrame(
            tech_scaler.transform(tech_numeric),
            columns=tech_numeric.columns, index=tech_numeric.index
        )

    # sentiment features
    sent_df = build_sentiment_features(symbol, news_raw_dir)
    sent_cols = ["sentiment_score", "sentiment_pos", "sentiment_neg",
                 "article_count_z", "sentiment_3d_momentum",
                 "sentiment_5d_momentum", "sentiment_volatility"]
    if not sent_df.empty:
        sent_df = sent_df.reindex(tech_scaled.index, method="ffill").fillna(0)
        sent_df = sent_df[[c for c in sent_cols if c in sent_df.columns]]
    else:
        sent_df = pd.DataFrame(0.0, index=tech_scaled.index, columns=sent_cols)

    sent_scaler_file = scaler_path / f"{symbol}_sent.pkl"
    if fit_scalers:
        sent_scaler = RobustScaler()
        sent_arr = sent_scaler.fit_transform(sent_df)
        joblib.dump(sent_scaler, sent_scaler_file)
    else:
        sent_scaler = joblib.load(sent_scaler_file)
        sent_arr = sent_scaler.transform(sent_df)
    sent_scaled = pd.DataFrame(sent_arr, columns=sent_df.columns, index=sent_df.index)

    # macro features
    macro_feats = pd.DataFrame(index=tech_scaled.index)
    if macro_data:
        macro_parts = []
        for sym, mdf in macro_data.items():
            s = mdf["close"].pct_change(20).rename(f"macro_{sym}_20d")
            macro_parts.append(s.reindex(tech_scaled.index, method="ffill").fillna(0))
        macro_feats = pd.concat(macro_parts, axis=1)

    macro_scaler_file = scaler_path / "macro.pkl"
    if not macro_feats.empty:
        if fit_scalers:
            macro_scaler = RobustScaler()
            macro_arr = macro_scaler.fit_transform(macro_feats.fillna(0))
            joblib.dump(macro_scaler, macro_scaler_file)
        else:
            macro_scaler = joblib.load(macro_scaler_file)
            macro_arr = macro_scaler.transform(macro_feats.fillna(0))
        macro_scaled = pd.DataFrame(macro_arr, columns=macro_feats.columns, index=macro_feats.index)
    else:
        macro_scaled = pd.DataFrame(0.0, index=tech_scaled.index,
                                    columns=["macro_placeholder"])

    # labels
    labels = build_labels(bars["close"], horizon, r_hi, r_lo)
    labels = labels.reindex(tech_scaled.index)

    # build sliding windows
    dates = tech_scaled.index
    price_windows, sent_windows, macro_windows = [], [], []
    valid_dates = []

    for i in range(max(price_window, sentiment_window, macro_window), len(dates)):
        p_slice = tech_scaled.iloc[i - price_window: i].values
        s_slice = sent_scaled.iloc[i - sentiment_window: i].values
        m_slice = macro_scaled.iloc[i - macro_window: i].values

        if (p_slice.shape[0] == price_window and
                s_slice.shape[0] == sentiment_window and
                m_slice.shape[0] == macro_window):
            price_windows.append(p_slice)
            sent_windows.append(s_slice)
            macro_windows.append(m_slice)
            valid_dates.append(dates[i])

    features_dict = {
        "price_seq":     np.array(price_windows, dtype=np.float32),
        "sentiment_seq": np.array(sent_windows,  dtype=np.float32),
        "macro_seq":     np.array(macro_windows,  dtype=np.float32),
    }
    labels_out = labels.loc[valid_dates]
    return features_dict, labels_out, pd.Index(valid_dates)
