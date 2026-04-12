"""Feature preprocessing with optional weighted z-score normalization."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


class FeaturePreprocessor:
    def __init__(self, clip_sigma: float = 5.0):
        self.clip_sigma = clip_sigma
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.median_: Optional[np.ndarray] = None
        self.columns_: Optional[list] = None

    def fit_transform(
        self,
        X_train: pd.DataFrame,
        sample_weights: Optional[np.ndarray] = None,
    ) -> pd.DataFrame:
        self.columns_ = list(X_train.columns)
        X = X_train.to_numpy(dtype=float)
        # Median impute (computed on train only)
        self.median_ = np.nanmedian(X, axis=0)
        X = np.where(np.isnan(X), self.median_, X)

        if sample_weights is not None:
            w = np.asarray(sample_weights, dtype=float)
            w = w / max(w.sum(), 1e-12)
            mean = np.average(X, weights=w, axis=0)
            var = np.average((X - mean) ** 2, weights=w, axis=0)
            std = np.sqrt(var)
        else:
            mean = X.mean(axis=0)
            std = X.std(axis=0)

        std = np.where(std < 1e-8, 1.0, std)
        self.mean_ = mean
        self.std_ = std

        Z = (X - mean) / std
        if self.clip_sigma:
            Z = np.clip(Z, -self.clip_sigma, self.clip_sigma)
        return pd.DataFrame(Z, index=X_train.index, columns=self.columns_)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        assert self.mean_ is not None, "Preprocessor not fit"
        X = X[self.columns_]
        arr = X.to_numpy(dtype=float)
        arr = np.where(np.isnan(arr), self.median_, arr)
        Z = (arr - self.mean_) / self.std_
        if self.clip_sigma:
            Z = np.clip(Z, -self.clip_sigma, self.clip_sigma)
        return pd.DataFrame(Z, index=X.index, columns=self.columns_)
