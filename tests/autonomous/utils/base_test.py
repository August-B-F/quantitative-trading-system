"""Cached backtest harness. Loads panel + walk-forward predictions ONCE per process,
then runs many config overrides quickly.

Usage:
    from utils.base_test import run, run_many, CHAMPION
    stats = run({"top_k": 4})
"""
from __future__ import annotations

import copy
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data.pipeline import load_config, load_panel  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402

CHAMPION = {"cagr": 0.2361, "sharpe": 1.50, "max_dd": -0.1294}

_CACHE_DIR = ROOT / "tests" / "autonomous" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_PRED_CACHE = _CACHE_DIR / "pred_reg.pkl"

_STATE = {}


def _load():
    if "cfg" in _STATE:
        return
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    if _PRED_CACHE.exists():
        with open(_PRED_CACHE, "rb") as f:
            pred_reg, test_dates = pickle.load(f)
    else:
        core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
        core_present = select_core_features(bundle.df, core)
        pred_reg, test_dates, _ = walk_forward_predict(bundle.df, core_present, cfg)
        with open(_PRED_CACHE, "wb") as f:
            pickle.dump((pred_reg, test_dates), f)
    _STATE.update({"cfg": cfg, "bundle": bundle, "pred_reg": pred_reg, "test_dates": test_dates})


def run(overrides=None, pred_reg_override=None):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"])
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    pred_reg = pred_reg_override if pred_reg_override is not None else _STATE["pred_reg"]
    engine = PortfolioEngine(_STATE["bundle"], pred_reg, cfg)
    res = run_backtest(engine, _STATE["test_dates"], cfg)
    return res.stats


def run_many(experiments):
    """experiments: list of (name, overrides) tuples. Returns list of (name, stats)."""
    out = []
    for name, ov in experiments:
        try:
            s = run(ov)
            out.append((name, s))
        except Exception as e:
            out.append((name, {"error": str(e)}))
    return out


def fmt(stats):
    if "error" in stats:
        return f"ERROR: {stats['error']}"
    return f"CAGR={stats['cagr']*100:6.2f}%  Sharpe={stats['sharpe']:.2f}  MaxDD={stats['max_dd']*100:6.2f}%"


def haircut_verdict(stats):
    """Apply 50% haircut on CAGR improvement vs champion. Returns (passes, hcut_cagr)."""
    if "error" in stats:
        return False, None
    bench = CHAMPION["cagr"]
    delta = stats["cagr"] - bench
    if delta <= 0:
        return False, stats["cagr"]
    hcut = bench + delta * 0.5
    passes = (hcut > bench) and (stats["sharpe"] >= CHAMPION["sharpe"] - 0.02)
    return passes, hcut
