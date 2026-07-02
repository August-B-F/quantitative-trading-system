"""Classifier retrain entry point.

Production cadence: quarterly (§5.5). Runs the walk-forward harness over the
live-extended panel, persists ``(pred_reg, test_dates, dates)`` to
``tests/autonomous/cache/pred_reg.pkl`` — the exact format
``scripts/run_rebalance.py::_load_pred_cache`` reads — and logs the
walk-forward accuracy next to the persistence baseline
(predict regime[t+21] = regime[t], i.e. "the regime never changes").

Sends a WARNING alert if the classifier underperforms persistence.
Exits non-zero on any exception.
"""
from __future__ import annotations

import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data.pipeline import load_config, load_panel  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from features.regime_labels import REGIME_CLASSES, current_regime  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402
from risk.notify import send_alert  # noqa: E402

CACHE_PATH = ROOT / "tests" / "autonomous" / "cache" / "pred_reg.pkl"

log = logging.getLogger("retrain")


def persistence_baseline_accuracy(
    bundle, pred_reg: np.ndarray, test_dates: pd.DatetimeIndex, cfg: dict
) -> tuple[float | None, float | None]:
    """Return (classifier_acc, persistence_acc) on the labeled test dates.

    Persistence predicts the t+21 regime label equals the current regime at t.
    Both accuracies are computed on the same dates: those test dates where the
    classifier emitted a prediction AND the realized label exists.
    """
    target_col = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    y = bundle.df[target_col].map(cls_to_idx)
    pos = bundle.dates.get_indexer(pd.DatetimeIndex(test_dates))
    pos = pos[pos >= 0]
    if len(pos) == 0:
        return None, None
    cur = current_regime(bundle.df).index
    yv = y.iloc[pos].to_numpy(dtype=float)
    pred = pred_reg[pos]
    mask = (pred >= 0) & np.isfinite(yv)
    if not mask.any():
        return None, None
    yv_i = yv[mask].astype(int)
    clf_acc = float((pred[mask] == yv_i).mean())
    persist_acc = float((cur[pos][mask] == yv_i).mean())
    return clf_acc, persist_acc


def main() -> int:
    """Entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        cfg = load_config(ROOT)
        bundle = load_panel(ROOT, cfg, live_extend=True)
        core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
        core_present = select_core_features(bundle.df, core)
        pred_reg, test_dates, accs = walk_forward_predict(bundle.df, core_present, cfg)

        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "wb") as f:
            # 3-tuple WITH the panel dates so the rebalance loader can align
            # predictions by DATE — a positional cache goes stale the moment
            # live_extend grows the panel index (daily).
            pickle.dump((pred_reg, test_dates, bundle.dates), f)
        log.info("saved pred_reg cache: %s (%d panel rows, %d test dates, "
                 "as_of %s)", CACHE_PATH, len(pred_reg), len(test_dates),
                 bundle.dates.max().date())

        if accs:
            print(f"WF 4-class accuracy (per-fold mean): {sum(accs)/len(accs):.3f}  "
                  f"folds={len(accs)}")
        else:
            print("no folds produced predictions — check data range / min_train_months")

        clf_acc, persist_acc = persistence_baseline_accuracy(
            bundle, pred_reg, pd.DatetimeIndex(test_dates), cfg
        )
        if clf_acc is None or persist_acc is None:
            log.warning("could not compute persistence baseline (no labeled test dates)")
        else:
            print(f"classifier accuracy:  {clf_acc:.3f}")
            print(f"persistence baseline: {persist_acc:.3f}  "
                  f"(predict regime[t+21] = regime[t])")
            if clf_acc < persist_acc:
                send_alert(
                    f"regime classifier accuracy {clf_acc:.3f} is below the "
                    f"persistence baseline {persist_acc:.3f} — investigate before "
                    f"trusting transition signals",
                    "WARNING",
                )
    except Exception:
        log.exception("retrain failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
