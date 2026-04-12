"""Splice CBOE put/call (ends 2019-10-04) with VIX-based synthetic for 2019+."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.utils import CATALOG_PATH, DATA_DIR, log_to_catalog, save_clean  # noqa: E402

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
VIX_PATH = DATA_DIR / "clean" / "prices" / "_VIX.parquet"
SPY_PATH = DATA_DIR / "clean" / "prices" / "SPY.parquet"

VARIANTS = ["total", "equity", "index"]


def build_features(include_spy: bool) -> pd.DataFrame:
    vix = pd.read_parquet(VIX_PATH)["close"].rename("vix")
    feat = pd.DataFrame({"vix": vix})
    feat["vix_chg_21d"] = vix.diff(21)
    feat["vix_ma_5d"] = vix.rolling(5).mean()
    if include_spy:
        spy = pd.read_parquet(SPY_PATH)["adj_close"].rename("spy")
        feat["spy_ret_21d"] = spy.pct_change(21)
    return feat.dropna()


def fit_ols(y: pd.Series, X: pd.DataFrame) -> tuple[np.ndarray, float]:
    Xm = np.column_stack([np.ones(len(X)), X.values])
    beta, *_ = np.linalg.lstsq(Xm, y.values, rcond=None)
    pred = Xm @ beta
    ss_res = float(((y.values - pred) ** 2).sum())
    ss_tot = float(((y.values - y.values.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return beta, r2


def predict(beta: np.ndarray, X: pd.DataFrame) -> pd.Series:
    Xm = np.column_stack([np.ones(len(X)), X.values])
    return pd.Series(Xm @ beta, index=X.index)


def splice_variant(variant: str) -> dict:
    src_path = CLEAN_DIR / f"cboe_putcall_{variant}.parquet"
    real = pd.read_parquet(src_path)
    col = real.columns[0]
    real_s = real[col].dropna()
    splice_date = real_s.index.max()  # last observed day

    # Try baseline regressors
    feat = build_features(include_spy=False)
    overlap_idx = real_s.index.intersection(feat.index)
    y = real_s.loc[overlap_idx]
    X = feat.loc[overlap_idx]
    beta, r2 = fit_ols(y, X)
    used_spy = False
    if r2 < 0.40:
        feat2 = build_features(include_spy=True)
        overlap_idx2 = real_s.index.intersection(feat2.index)
        y2 = real_s.loc[overlap_idx2]
        X2 = feat2.loc[overlap_idx2]
        beta2, r2_2 = fit_ols(y2, X2)
        if r2_2 > r2:
            feat, beta, r2 = feat2, beta2, r2_2
            used_spy = True

    # Synthesize from splice_date+1 to end of features
    future_feat = feat.loc[feat.index > splice_date]
    synth = predict(beta, future_feat)

    # Assemble
    real_df = pd.DataFrame({col: real_s, "is_proxy": False})
    synth_df = pd.DataFrame({col: synth.values, "is_proxy": True}, index=synth.index)
    spliced = pd.concat([real_df, synth_df]).sort_index()
    spliced = spliced[~spliced.index.duplicated(keep="first")]
    spliced[col] = spliced[col].astype("float64")

    out_path = CLEAN_DIR / f"cboe_putcall_{variant}_spliced.parquet"
    save_clean(
        spliced,
        out_path,
        metadata={
            "source": "cboe+vix_proxy",
            "variant": variant,
            "splice_date": str(splice_date.date()),
            "r_squared": round(r2, 4),
            "regressors": ["vix", "vix_chg_21d", "vix_ma_5d"] + (["spy_ret_21d"] if used_spy else []),
            "beta": beta.tolist(),
            "note": "Real CBOE data through splice_date; VIX-regressed synthetic after.",
        },
    )
    log_to_catalog(CATALOG_PATH, {
        "source": "cboe+proxy",
        "series_name": f"putcall_{variant}_spliced",
        "frequency": "daily",
        "date_range": f"{spliced.index.min().date()}..{spliced.index.max().date()}",
        "file_path": str(out_path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": f"splice_date={splice_date.date()} R2={r2:.3f} regressors={'+spy' if used_spy else 'vix-only'}",
    })
    return {
        "variant": variant,
        "splice_date": str(splice_date.date()),
        "r2": round(r2, 4),
        "used_spy": used_spy,
        "n_real": int(len(real_df)),
        "n_synth": int(len(synth_df)),
        "n_total": int(len(spliced)),
        "range": f"{spliced.index.min().date()}..{spliced.index.max().date()}",
    }


def main() -> None:
    for v in VARIANTS:
        r = splice_variant(v)
        print(r)


if __name__ == "__main__":
    main()
