"""Live classifier-feature builder.

On rebalance day, the classifier needs fresh CORE features for today rather
than a stale slice from `master_panel.parquet`. This module assembles a
single-row DataFrame for the latest available trading date by reading the
per-feature parquets under `data/features/{price,macro,interaction,...}/`
that the canonical builders (`engineer.main`, `macro_features.build`)
produce.

CORE column names follow `{group}__{column}` where `group` is the feature
parquet stem and `column` is the column name inside that file (see
`assemble_master_panel.load_category`). We resolve each CORE name by
scanning categories in the same order the master-panel assembler uses.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

log = logging.getLogger(__name__)

# Same scan order as assemble_master_panel.CATEGORIES so name collisions
# resolve identically (price > macro > sentiment > ... > interaction).
CATEGORIES = ["price", "macro", "sentiment", "fundamental",
              "alternative", "calendar", "interaction"]


def load_core_set(root: Path, key: str = "core") -> list[str]:
    """Read `core` (or another set) from configs/feature_sets.yaml."""
    with open(Path(root) / "configs/feature_sets.yaml") as f:
        return list(yaml.safe_load(f)[key])


def _resolve_feature(feat_name: str, root: Path) -> Optional[pd.Series]:
    """Find the parquet that supplies `feat_name = stem__col` and return its series.

    Mirrors `assemble_master_panel.load_category` naming: name is
    `f"{stem}__{col}"` when the file has multiple columns OR the column
    name differs from the stem. We try the natural split first (stem
    everywhere up to the last `__`) and fall back to the case where the
    column itself equals the stem.
    """
    feat_dir = Path(root) / "data" / "features"

    # Try every prefix length so we can find files whose stem itself contains '__'.
    parts = feat_name.split("__")
    for cut in range(len(parts) - 1, 0, -1):
        stem = "__".join(parts[:cut])
        col = "__".join(parts[cut:])
        for cat in CATEGORIES:
            p = feat_dir / cat / f"{stem}.parquet"
            if not p.exists():
                continue
            try:
                df = pd.read_parquet(p)
            except Exception as e:
                log.warning("read failed %s: %s", p, e)
                continue
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df = df[~df.index.duplicated(keep="last")]
            if col in df.columns:
                return pd.to_numeric(df[col], errors="coerce").astype("float64")

    # single-column files where name == stem
    for cat in CATEGORIES:
        p = feat_dir / cat / f"{feat_name}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            if feat_name in df.columns:
                return pd.to_numeric(df[feat_name], errors="coerce").astype("float64")
            if len(df.columns) == 1:
                return pd.to_numeric(df.iloc[:, 0], errors="coerce").astype("float64")
    return None


def compute_classifier_features(
    root: Path,
    as_of: Optional[pd.Timestamp] = None,
    feature_set: str = "core",
) -> pd.DataFrame:
    """Build a one-row feature DataFrame for the classifier.

    Parameters
    ----------
    root : repo root.
    as_of : pin output to this date. If None, uses the max date observed
        across the assembled feature columns (minus any look-ahead beyond it).
    feature_set : key into configs/feature_sets.yaml (default 'core').

    Returns
    -------
    pd.DataFrame
        Single row indexed by the chosen date, columns = the feature set,
        in declared order. Missing features come through as NaN with a
        warning.
    """
    root = Path(root)
    core = load_core_set(root, feature_set)

    series_map: dict[str, pd.Series] = {}
    missing: list[str] = []
    for name in core:
        s = _resolve_feature(name, root)
        if s is None or s.dropna().empty:
            missing.append(name)
            continue
        series_map[name] = s

    if missing:
        log.warning("live_features: %d/%d features missing: %s",
                    len(missing), len(core), missing[:5])

    if not series_map:
        raise RuntimeError("no live features could be resolved")

    panel = pd.DataFrame(series_map).sort_index()
    if as_of is None:
        # Use the latest date where ALL features have a value (after ffill
        # within the panel's existing index — feature builders already
        # encode the publication-lag policy).
        valid = panel.dropna()
        if valid.empty:
            valid = panel.ffill().dropna()
        if valid.empty:
            raise RuntimeError("no row where all CORE features are populated")
        as_of = valid.index.max()
    else:
        as_of = pd.Timestamp(as_of)
        if as_of not in panel.index:
            panel = panel.reindex(panel.index.union([as_of])).ffill()

    row = panel.loc[[as_of]]
    # Re-order to the declared CORE order, NaN-filling any missing.
    return row.reindex(columns=core)
