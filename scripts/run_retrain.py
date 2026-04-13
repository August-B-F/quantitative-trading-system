"""Classifier retrain entry point — scaffold.

Production cadence: quarterly (§5.5). This stub runs the walk-forward
harness and prints WF accuracy. A live version would save the joblib to
data/models/regime_classifier_vYYYYqQ.joblib and update the symlink.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data.pipeline import load_config, load_panel  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402


def main() -> int:
    """Entry point."""
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(bundle.df, core)
    _, _, accs = walk_forward_predict(bundle.df, core_present, cfg)
    if accs:
        print(f"WF 4-class accuracy: {sum(accs)/len(accs):.3f}  folds={len(accs)}")
    else:
        print("no folds produced predictions — check data range / min_train_months")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
