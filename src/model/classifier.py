"""Regime classifier — walk-forward HistGB on CORE features (§2.5, §5.x).

Ports the walk-forward training loop from scripts/model/run_m26_deep.py:82-104
verbatim; the output `pred_reg` array is the 4-class argmax prediction for
t+21 trading days, used as the lookback-switch signal.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from model.preprocessing import FeaturePreprocessor
from model.walk_forward import ExpandingSplitter
from features.regime_labels import REGIME_CLASSES

log = logging.getLogger(__name__)


def build_splitter(cfg: dict) -> ExpandingSplitter:
    """Build the ExpandingSplitter from strategy.yaml config."""
    s = cfg["splitter"]
    return ExpandingSplitter(
        min_train_months=s["min_train_months"],
        val_months=s["val_months"],
        test_months=s["test_months"],
        step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"],
        embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"],
        decay_halflife_months=s["decay_halflife_months"],
    )


def build_estimator(cfg: dict) -> HistGradientBoostingClassifier:
    """Build the HistGB estimator with pinned hyperparameters."""
    c = cfg["classifier"]
    return HistGradientBoostingClassifier(
        max_iter=c["max_iter"],
        max_depth=c["max_depth"],
        learning_rate=c["learning_rate"],
        min_samples_leaf=c["min_samples_leaf"],
        l2_regularization=c["l2_regularization"],
        random_state=c["random_state"],
    )


def walk_forward_predict(
    df: pd.DataFrame,
    core_feats: list[str],
    cfg: dict,
) -> tuple[np.ndarray, pd.DatetimeIndex, list[float]]:
    """Return (pred_reg, test_dates, per_fold_accuracy).

    pred_reg is a length-NDAYS array of class indices in [0..3] or -1 where
    not predicted. Matches run_m26_deep.py:80-104.
    """
    dates = df.index
    n = len(dates)
    splitter = build_splitter(cfg)
    folds = splitter.split(dates)
    test_dates = pd.DatetimeIndex(sorted({d for f in folds for d in f["test_dates"]}))
    log.info("walk-forward: %d folds, %d test dates", len(folds), len(test_dates))

    target_col = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}

    pred_reg = np.full(n, -1, dtype=int)
    fold_accs: list[float] = []

    for fold in folds:
        tr = fold["train_dates"]
        te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]
        ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, core_feats]
        yte_raw = df.loc[te, target_col]
        mtr = ytr_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50:
            continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = build_estimator(cfg)
        try:
            clf.fit(Xtr_z, ytr, sample_weight=sw)
        except Exception as e:
            log.error("fold fit failed (%s); skipping", e)
            continue
        proba = clf.predict_proba(Xte_z)
        # expand to 4 columns even if some class absent from the train fold
        full = np.zeros((len(Xte_z), 4))
        for j, cls in enumerate(clf.classes_):
            full[:, int(cls)] = proba[:, j]
        pr = np.argmax(full, axis=1)
        te_pos = dates.get_indexer(te)
        pred_reg[te_pos] = pr
        yte_m = yte_raw.map(cls_to_idx)
        if yte_m.notna().any():
            yv = yte_m.dropna().astype(int).to_numpy()
            fold_accs.append(float((pr[: len(yv)] == yv[: len(pr)]).mean()))

    if fold_accs:
        log.info("WF 4-class accuracy: %.3f (n=%d folds)", float(np.mean(fold_accs)), len(fold_accs))
    return pred_reg, test_dates, fold_accs


def classifier_fallback(n: int) -> np.ndarray:
    """63d-always fallback: return all-(-1) so downstream treats use_trans=False."""
    return np.full(n, -1, dtype=int)


def predict_at(
    df: pd.DataFrame,
    core_feats: list[str],
    cfg: dict,
    as_of: pd.Timestamp,
) -> int:
    """Fit a fresh classifier on all labels available before `as_of` and predict that date.

    The WF splitter only emits predictions on its discrete test dates
    (`sample_every_n_days=5`), so live rebalance dates that fall between
    test points will have no WF prediction. This function trains one
    model on all labeled data older than `as_of - (target_horizon +
    embargo) trading days` and returns the predicted regime class for
    the live row. Returns -1 only if the fit can't be performed.
    """
    s = cfg["splitter"]
    horizon = int(s.get("target_horizon", 21))
    embargo = int(s.get("embargo_days", 5))
    target_col = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}

    as_of = pd.Timestamp(as_of)
    if as_of not in df.index:
        log.warning("predict_at: %s not in panel index", as_of.date())
        return -1

    pos = df.index.get_loc(as_of)
    cutoff_pos = pos - (horizon + embargo)
    if cutoff_pos <= 50:
        log.warning("predict_at: not enough history before %s", as_of.date())
        return -1
    train_dates = df.index[:cutoff_pos + 1]

    Xtr = df.loc[train_dates, core_feats]
    ytr_raw = df.loc[train_dates, target_col]
    mtr = ytr_raw.notna()
    Xtr, ytr_raw = Xtr[mtr], ytr_raw[mtr]
    if len(Xtr) < 200:
        log.warning("predict_at: only %d labeled rows", len(Xtr))
        return -1

    ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
    pp = FeaturePreprocessor()
    Xtr_z = pp.fit_transform(Xtr).to_numpy()
    Xte_z = pp.transform(df.loc[[as_of], core_feats]).to_numpy()

    clf = build_estimator(cfg)
    try:
        clf.fit(Xtr_z, ytr)
    except Exception as e:
        log.error("predict_at fit failed: %s", e)
        return -1

    proba = clf.predict_proba(Xte_z)[0]
    full = np.zeros(4)
    for j, cls in enumerate(clf.classes_):
        full[int(cls)] = proba[j]
    pred = int(np.argmax(full))
    log.info("predict_at %s: classes=%s probs=%s -> %d",
             as_of.date(), clf.classes_.tolist(), [f"{p:.3f}" for p in full], pred)
    return pred
