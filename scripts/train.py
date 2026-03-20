"""Walk-forward model training.

Training strategy:
  - Splits history into N folds. Each fold:
      * Train on all data up to fold end
      * Validate on the next window
      * Save the checkpoint with best validation accuracy
  - Optional Optuna hyperparameter search before final training run
  - Scalers are fitted on TRAINING data of first fold only (no leakage)
  - After each fold: temperature calibration via L-BFGS
  - Final best checkpoint saved to data/models/best_model.pt

Deep Ensemble mode (--ensemble N):
    Trains N models with different random seeds and saves all checkpoints.
    At inference, EnsembleModel averages predictions for better calibration.

Class imbalance handling:
  - Focal loss down-weights the dominant 'hold' class automatically
  - WeightedRandomSampler oversamples rare buy/sell signals
  - Label smoothing=0.1 prevents overconfident predictions

Hardware: optimised for RTX 4060 Ti 16 GB (AMP + torch.compile + batch_size=512)

Usage:
    python scripts/train.py
    python scripts/train.py --hparam-search
    python scripts/train.py --folds 3 --epochs 50
    python scripts/train.py --no-news
    python scripts/train.py --ensemble 5       # deep ensemble
    python scripts/train.py --batch-size 512   # RTX 4060 Ti
    python scripts/train.py --no-fundamentals  # skip fundamentals branch
"""
import argparse
import os
import sys
import json
import shutil
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ultimate_trader.utils.config_loader import load_config
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.data_sources.alpaca_market import MarketDataFetcher
from ultimate_trader.data_sources.alpaca_news import NewsFetcher
from ultimate_trader.data_sources.alt_data import AltDataBuilder
from ultimate_trader.features.feature_builder import (
    FeatureBuilder, TECH_FEATURES, SENTIMENT_FEATURES, MACRO_FEATURES, FUNDAMENTAL_FEATURES
)
from ultimate_trader.features.regimes import RegimeDetector
from ultimate_trader.modeling.model import build_model, REGIME_TO_IDX, EnsembleModel
from ultimate_trader.modeling.losses import OrdinalReturnLoss, compute_class_weights
from ultimate_trader.modeling.metrics import sharpe_ratio, compute_val_sharpe
from ultimate_trader.modeling.calibration import TemperatureScaler
from ultimate_trader.modeling.hyperparam_search import run_search

log = get_logger("train")


# ── Dataset ───────────────────────────────────────────────────────────────────

class TradeDataset(Dataset):
    def __init__(self, samples, labels, regime_labels=None):
        self.samples = samples
        self.labels = labels
        self.regime_labels = regime_labels if regime_labels is not None else [0] * len(labels)
        # Infer fund_dim from first sample
        self._fund_dim = len(samples[0].get("fund", [])) if samples else 6

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        fund = s.get("fund", np.zeros(self._fund_dim, dtype=np.float32))
        return (
            torch.tensor(s["tech"],    dtype=torch.float32),
            torch.tensor(s["sent"],    dtype=torch.float32),
            torch.tensor(s["macro"],   dtype=torch.float32),
            torch.tensor(fund,         dtype=torch.float32),
            torch.tensor(s["sym_idx"], dtype=torch.long),
            torch.tensor(s["sec_idx"], dtype=torch.long),
            torch.tensor(self.regime_labels[idx], dtype=torch.long),
            torch.tensor(self.labels[idx], dtype=torch.long),
        )


def make_weighted_sampler(labels: list) -> WeightedRandomSampler:
    """Inverse-frequency weighting so rare buy/sell classes are sampled as often as hold."""
    counts = np.bincount(labels, minlength=5).astype(float)
    counts = np.maximum(counts, 1)
    class_weights = 1.0 / counts
    sample_weights = torch.tensor([class_weights[l] for l in labels], dtype=torch.float32)
    return WeightedRandomSampler(sample_weights, num_samples=len(sample_weights), replacement=True)


# ── Args ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config",            default="config")
    p.add_argument("--folds",             type=int,   default=None)
    p.add_argument("--epochs",            type=int,   default=None)
    p.add_argument("--batch-size",        type=int,   default=None,
                   help="Default 512 for RTX 4060 Ti 16GB")
    p.add_argument("--lr",                type=float, default=None)
    p.add_argument("--hparam-search",     action="store_true")
    p.add_argument("--no-news",           action="store_true")
    p.add_argument("--no-fundamentals",   action="store_true",
                   help="Skip fundamentals branch (faster, no yfinance calls)")
    p.add_argument("--no-gdelt",          action="store_true",
                   help="Skip GDELT news sentiment (faster)")
    p.add_argument("--device",            default=None)
    p.add_argument("--ensemble",          type=int,   default=1,
                   help="Number of ensemble members (1 = single model)")
    p.add_argument("--compile",           action="store_true", default=True,
                   help="Use torch.compile for ~20%% speedup (PyTorch 2.x)")
    p.add_argument("--no-compile",        dest="compile", action="store_false")
    return p.parse_args()


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_data(cfg, args):
    market = MarketDataFetcher(cfg)
    all_symbols = (
        list(cfg.universe.symbols)
        + [cfg.universe.benchmark]
        + list(cfg.universe.sector_etfs)
        + list(cfg.universe.macro_tickers)
        + [cfg.universe.vix_ticker]
    )
    all_symbols = list(dict.fromkeys(s for s in all_symbols if s))
    bars = market.fetch(all_symbols)

    alt = AltDataBuilder(cfg)

    # GDELT market sentiment (optional)
    gdelt_df = None
    if not getattr(args, "no_gdelt", False):
        try:
            from ultimate_trader.data_sources.gdelt_news import GDELTFetcher
            gdelt = GDELTFetcher()
            start_date = getattr(cfg.data, "start_date", "2018-01-01")
            gdelt_df = gdelt.fetch_market_sentiment(start=start_date)
            if not gdelt_df.empty:
                log.info(f"GDELT data loaded: {len(gdelt_df)} days")
            else:
                log.info("GDELT data empty — macro features will have zero GDELT columns")
        except Exception as e:
            log.warning(f"GDELT fetch failed (non-fatal): {e}")

    macro_df = alt.build_macro_features(bars, gdelt_df=gdelt_df)

    earnings_dates = alt.get_earnings_dates(list(cfg.universe.symbols))

    if args.no_news or not cfg.news.enabled:
        sentiment = {}
    else:
        news = NewsFetcher(cfg)
        sentiment = news.fetch_and_score(list(cfg.universe.symbols))

    # Fundamentals (optional)
    fundamentals = None
    if not args.no_fundamentals:
        try:
            from ultimate_trader.data_sources.fundamentals import FundamentalsFetcher
            ff = FundamentalsFetcher()
            fundamentals = ff.fetch(list(cfg.universe.symbols))
            n_ok = sum(1 for df in fundamentals.values() if len(df) > 0)
            log.info(f"Fundamentals loaded: {n_ok}/{len(cfg.universe.symbols)} symbols")
        except Exception as e:
            log.warning(f"Fundamentals fetch failed (non-fatal): {e}")
            fundamentals = None

    return bars, macro_df, sentiment, earnings_dates, fundamentals


def build_symbol_maps(cfg):
    symbols = list(cfg.universe.symbols)
    symbol_to_idx = {s: i + 1 for i, s in enumerate(symbols)}
    sector_map = {
        "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "INTC", "QCOM", "TXN", "ACN", "INTU", "NOW", "CSCO"],
        "XLF": ["JPM", "BAC", "GS", "V", "MA", "SPGI"],
        "XLV": ["UNH", "LLY", "JNJ", "ABT", "MRK", "ABBV", "TMO", "DHR", "AMGN"],
        "XLE": ["XOM", "CVX"],
        "XLP": ["WMT", "KO", "PG", "COST", "PEP", "PM"],
        "XLY": ["AMZN", "TSLA", "MCD", "NKE", "HD"],
        "XLC": ["META", "GOOGL", "NFLX"],
        "XLI": ["RTX", "UPS", "LIN", "NEE"],
    }
    symbol_to_sector = {}
    for sec_idx, (etf, syms) in enumerate(sector_map.items(), start=1):
        for s in syms:
            symbol_to_sector[s] = sec_idx
    return symbol_to_idx, symbol_to_sector


def assign_regime_labels(samples: list, regime_detector, bars: dict) -> list:
    """
    Assign a regime index (int) to each training sample based on the sample's date.
    BUG FIX: samples now store "date" key — use it for correct regime lookup.
    Falls back to 0 (unknown) if regime cannot be determined.
    """
    spy_bars = bars.get("SPY")
    if spy_bars is None or regime_detector is None:
        return [0] * len(samples)

    try:
        regime_series = regime_detector.predict(spy_bars)  # pd.Series: date -> regime str
        regime_map = {
            pd.Timestamp(k): REGIME_TO_IDX.get(v, 0)
            for k, v in regime_series.items()
        }
    except Exception as e:
        log.warning(f"Regime prediction failed: {e}")
        return [0] * len(samples)

    labels = []
    for sample in samples:
        date = sample.get("date")
        if date is not None:
            # Try exact match, then nearest business day
            regime_idx = regime_map.get(pd.Timestamp(date))
            if regime_idx is None:
                # asof lookup: find the most recent regime at or before this date
                try:
                    idx = regime_series.index.asof(pd.Timestamp(date))
                    if idx is not pd.NaT:
                        regime_idx = REGIME_TO_IDX.get(regime_series.loc[idx], 0)
                    else:
                        regime_idx = 0
                except Exception:
                    regime_idx = 0
            labels.append(regime_idx)
        else:
            labels.append(0)

    n_nonzero = sum(1 for x in labels if x != 0)
    log.info(f"Regime labels: {n_nonzero}/{len(labels)} samples have non-unknown regime")
    return labels


# ── Training loops ────────────────────────────────────────────────────────────

def train_epoch(model, loader, optimizer, criterion, device, amp_scaler=None):
    model.train()
    total_loss, correct, n = 0.0, 0, 0
    for tech, sent, macro, fund, sym_idx, sec_idx, regime_idx, labels in loader:
        tech, sent, macro, fund = tech.to(device), sent.to(device), macro.to(device), fund.to(device)
        sym_idx, sec_idx = sym_idx.to(device), sec_idx.to(device)
        regime_idx = regime_idx.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        if amp_scaler is not None:
            with torch.autocast(device_type="cuda"):
                logits = model(tech, sent, macro, fund, sym_idx, sec_idx, regime_idx)
                loss = criterion(logits, labels)
            amp_scaler.scale(loss).backward()
            amp_scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            amp_scaler.step(optimizer)
            amp_scaler.update()
        else:
            logits = model(tech, sent, macro, fund, sym_idx, sec_idx, regime_idx)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        total_loss += loss.item() * len(labels)
        correct += (logits.argmax(1) == labels).sum().item()
        n += len(labels)
    return total_loss / max(n, 1), correct / max(n, 1)


@torch.no_grad()
def eval_epoch(model, loader, criterion, device):
    model.eval()
    total_loss, correct, n = 0.0, 0, 0
    for tech, sent, macro, fund, sym_idx, sec_idx, regime_idx, labels in loader:
        tech, sent, macro, fund = tech.to(device), sent.to(device), macro.to(device), fund.to(device)
        sym_idx, sec_idx = sym_idx.to(device), sec_idx.to(device)
        regime_idx = regime_idx.to(device)
        labels = labels.to(device)
        logits = model(tech, sent, macro, fund, sym_idx, sec_idx, regime_idx)
        loss = criterion(logits, labels)
        total_loss += loss.item() * len(labels)
        correct += (logits.argmax(1) == labels).sum().item()
        n += len(labels)
    return total_loss / max(n, 1), correct / max(n, 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def train_single_model(seed, fold, args, cfg, bars, macro_df, sentiment,
                       earnings_dates, fundamentals, symbol_to_idx, symbol_to_sector,
                       symbols, n_symbols, n_sectors, train_samples, train_labels,
                       val_samples, val_labels, regime_detector, device, lr):
    """Train one model with a given seed. Returns (best_val_sharpe, ckpt_path)."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    # ── Regime labels using sample["date"] (BUG FIX) ──────────────────────────
    train_regime_labels = assign_regime_labels(train_samples, regime_detector, bars)
    val_regime_labels   = assign_regime_labels(val_samples,   regime_detector, bars)

    # ── Dataloaders ────────────────────────────────────────────────────────────
    sampler = make_weighted_sampler(train_labels)
    train_ds = TradeDataset(train_samples, train_labels, train_regime_labels)
    val_ds   = TradeDataset(val_samples,   val_labels,   val_regime_labels)

    batch_size = args.batch_size or cfg.training.get("batch_size", 512)
    # Windows: num_workers > 0 can cause spawn issues; use 2 with spawn safeguard
    n_workers = 0 if sys.platform == "win32" else 4
    train_loader = DataLoader(train_ds, batch_size=batch_size, sampler=sampler,
                              num_workers=n_workers, pin_memory=(device.type == "cuda"),
                              persistent_workers=(n_workers > 0))
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                              num_workers=n_workers, pin_memory=(device.type == "cuda"),
                              persistent_workers=(n_workers > 0))

    tech_dim  = train_samples[0]["tech"].shape[-1]
    sent_dim  = train_samples[0]["sent"].shape[-1]
    macro_dim = train_samples[0]["macro"].shape[-1]
    fund_dim  = len(train_samples[0].get("fund", [0] * len(FUNDAMENTAL_FEATURES)))

    model = build_model(cfg, n_symbols, n_sectors,
                        tech_dim, sent_dim, macro_dim, fund_dim).to(device)

    # torch.compile: ~20-30% speedup on RTX 4060 Ti with PyTorch 2.x
    if args.compile and device.type == "cuda" and hasattr(torch, "compile"):
        try:
            model = torch.compile(model)
            log.info("torch.compile enabled")
        except Exception as e:
            log.warning(f"torch.compile failed (non-fatal): {e}")

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=lr,
        weight_decay=cfg.training.get("weight_decay", 1e-4),
    )
    epochs = args.epochs or cfg.training.get("epochs", 50)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=lr * 0.01,
    )

    class_weights = compute_class_weights(train_labels).to(device)
    # OrdinalReturnLoss: FocalLoss (70%) + differentiable ordinal penalty (30%)
    # Penalises directional reversals far more than adjacent-class misclassifications
    criterion = OrdinalReturnLoss(focal_weight=0.7, ordinal_weight=0.3,
                                  gamma=2.0, weight=class_weights)

    use_amp = (device.type == "cuda")
    amp_scaler = torch.amp.GradScaler() if use_amp else None

    best_val_sharpe = -999.0
    patience_count = 0
    patience = cfg.training.get("early_stopping_patience", 8)
    ckpt_path = os.path.join(cfg.paths.models_dir, f"fold_{fold+1}_seed{seed}.pt")

    for epoch in range(1, epochs + 1):
        tr_loss, tr_acc = train_epoch(model, train_loader, optimizer, criterion, device, amp_scaler)
        val_loss, val_acc = eval_epoch(model, val_loader, criterion, device)
        scheduler.step()

        # Sharpe-based checkpoint selection: optimise for trading profitability
        raw_m = model._orig_mod if hasattr(model, "_orig_mod") else model
        val_sharpe = compute_val_sharpe(raw_m, val_loader, device, val_samples)

        log.info(f"Fold {fold+1} Seed {seed} Ep {epoch:03d} | "
                 f"tr={tr_loss:.4f}/{tr_acc:.3f} val={val_loss:.4f}/{val_acc:.3f} "
                 f"val_sharpe={val_sharpe:.3f}")

        if val_sharpe > best_val_sharpe:
            best_val_sharpe = val_sharpe
            patience_count = 0
            # Get underlying model if compiled
            save_model = model._orig_mod if hasattr(model, "_orig_mod") else model
            torch.save({
                "epoch": epoch, "fold": fold + 1, "seed": seed,
                "model_state": save_model.state_dict(),
                "val_acc": val_acc,
                "val_sharpe": val_sharpe,
                "tech_dim": tech_dim, "sent_dim": sent_dim,
                "macro_dim": macro_dim, "fund_dim": fund_dim,
                "n_symbols": n_symbols, "n_sectors": n_sectors,
                "symbol_to_idx": symbol_to_idx,
                "symbol_to_sector": symbol_to_sector,
            }, ckpt_path)
        else:
            patience_count += 1
            if patience_count >= patience:
                log.info(f"Early stopping at epoch {epoch}")
                break

    # ── Temperature calibration ────────────────────────────────────────────────
    log.info("Running temperature calibration...")
    # Reload best checkpoint for calibration
    raw_model = build_model(cfg, n_symbols, n_sectors,
                            tech_dim, sent_dim, macro_dim, fund_dim).to(device)
    ckpt = torch.load(ckpt_path, map_location=device)
    raw_model.load_state_dict(ckpt["model_state"])

    calib = TemperatureScaler()
    optimal_temp = calib.fit(raw_model, val_loader, device)
    log.info(f"Fold {fold+1} Seed {seed}: optimal temperature = {optimal_temp:.4f}")

    # Save temperature alongside the checkpoint
    temp_path = ckpt_path.replace(".pt", "_temperature.pt")
    calib.save(raw_model, temp_path)

    # Update checkpoint with calibrated temperature
    ckpt["temperature"] = optimal_temp
    torch.save(ckpt, ckpt_path)

    return best_val_sharpe, ckpt_path


def main():
    args = parse_args()
    cfg = load_config(args.config)
    tcfg = cfg.training

    device_str = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_str)
    log.info(f"Using device: {device}")
    if device.type == "cuda":
        log.info(f"GPU: {torch.cuda.get_device_name(0)}")
        log.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    os.makedirs(cfg.paths.models_dir, exist_ok=True)
    os.makedirs(cfg.paths.scalers_dir, exist_ok=True)
    os.makedirs(cfg.paths.processed_dir, exist_ok=True)

    log.info("Loading market data...")
    bars, macro_df, sentiment, earnings_dates, fundamentals = load_all_data(cfg, args)

    symbol_to_idx, symbol_to_sector = build_symbol_maps(cfg)
    symbols = [s for s in cfg.universe.symbols if s in bars]
    n_symbols = len(symbol_to_idx)
    n_sectors = max(symbol_to_sector.values(), default=1)

    spy_bars = bars.get("SPY")
    regime_detector = RegimeDetector(n_components=4)
    if spy_bars is not None:
        regime_detector.fit(spy_bars)
        regime_path = os.path.join(cfg.paths.models_dir, "regime_detector.pkl")
        regime_detector.save(regime_path)
        log.info(f"4-state regime detector saved to {regime_path}")

    fb = FeatureBuilder(cfg)

    n_folds    = args.folds or tcfg.get("n_folds", 4)
    lr         = args.lr or tcfg.get("learning_rate", tcfg.get("lr", 3e-4))
    val_window = tcfg.get("val_window_days", 120)
    n_ensemble = args.ensemble

    all_dates = spy_bars.index if spy_bars is not None else next(iter(bars.values())).index
    fold_size = len(all_dates) // (n_folds + 1)

    best_global_val_sharpe = -999.0
    best_model_path = os.path.join(cfg.paths.models_dir, "best_model.pt")
    ensemble_ckpts = []

    for fold in range(n_folds):
        train_end_idx = fold_size * (fold + 1)
        val_end_idx   = min(train_end_idx + val_window, len(all_dates))
        train_dates   = all_dates[:train_end_idx]
        val_dates     = all_dates[train_end_idx:val_end_idx]

        if len(train_dates) < cfg.data.min_history_days or len(val_dates) < 20:
            log.info(f"Fold {fold+1}: not enough data, skipping")
            continue

        log.info(f"Fold {fold+1}/{n_folds}: train {train_dates[0].date()}--{train_dates[-1].date()}, "
                 f"val {val_dates[0].date()}--{val_dates[-1].date()}")

        train_samples, train_labels = fb.build_training_samples(
            bars, sentiment, macro_df, symbols, symbol_to_idx, symbol_to_sector,
            date_range=train_dates, fit_scalers=(fold == 0),
            earnings_dates=earnings_dates, fundamentals=fundamentals,
        )
        val_samples, val_labels = fb.build_training_samples(
            bars, sentiment, macro_df, symbols, symbol_to_idx, symbol_to_sector,
            date_range=val_dates, fit_scalers=False,
            earnings_dates=earnings_dates, fundamentals=fundamentals,
        )

        if not train_samples or not val_samples:
            log.warning(f"Fold {fold+1}: empty samples, skipping")
            continue

        log.info(f"Fold {fold+1}: {len(train_samples)} train, {len(val_samples)} val samples")
        label_dist = np.bincount(train_labels, minlength=5)
        log.info(f"Label distribution: {label_dist} (0=s.sell 1=sell 2=hold 3=buy 4=s.buy)")

        # ── Optuna hparam search (fold 0 only) ─────────────────────────────────
        if args.hparam_search and fold == 0:
            log.info("Running Optuna hyperparameter search...")
            tech_dim  = train_samples[0]["tech"].shape[-1]
            sent_dim  = train_samples[0]["sent"].shape[-1]
            macro_dim = train_samples[0]["macro"].shape[-1]
            fund_dim  = len(train_samples[0].get("fund", [0] * len(FUNDAMENTAL_FEATURES)))

            def objective(trial, params):
                trial_model = build_model(
                    cfg, n_symbols, n_sectors, tech_dim, sent_dim, macro_dim, fund_dim
                ).to(device)
                opt = torch.optim.AdamW(trial_model.parameters(),
                                         lr=params.get("lr", lr),
                                         weight_decay=params.get("weight_decay", 1e-4))
                crit = OrdinalReturnLoss(focal_weight=0.7, ordinal_weight=0.3, gamma=2.0)
                search_sampler = make_weighted_sampler(train_labels)
                search_ds = TradeDataset(train_samples, train_labels)
                search_loader = DataLoader(search_ds, batch_size=256, sampler=search_sampler)
                for _ in range(8):
                    train_epoch(trial_model, search_loader, opt, crit, device)
                # Evaluate on val Sharpe (fixes metric: "sharpe" config being ignored)
                val_loader_search = DataLoader(
                    TradeDataset(val_samples, val_labels), batch_size=256)
                val_sharpe = compute_val_sharpe(trial_model, val_loader_search, device, val_samples)
                return val_sharpe

            search_space = {"lr": [1e-4, 1e-2], "weight_decay": [1e-5, 1e-2]}
            best_params = run_search(objective, search_space,
                                      n_trials=tcfg.get("n_trials", 40),
                                      output_dir=cfg.paths.models_dir)
            if best_params:
                lr = best_params.get("lr", lr)
                log.info(f"Best lr from Optuna: {lr}")

        # ── Train ensemble members ──────────────────────────────────────────────
        fold_best_sharpe = -999.0
        fold_best_ckpt = None

        for seed in range(n_ensemble):
            log.info(f"Training ensemble member {seed+1}/{n_ensemble} (seed={seed})")
            val_sharpe, ckpt_path = train_single_model(
                seed=seed, fold=fold, args=args, cfg=cfg,
                bars=bars, macro_df=macro_df, sentiment=sentiment,
                earnings_dates=earnings_dates, fundamentals=fundamentals,
                symbol_to_idx=symbol_to_idx, symbol_to_sector=symbol_to_sector,
                symbols=symbols, n_symbols=n_symbols, n_sectors=n_sectors,
                train_samples=train_samples, train_labels=train_labels,
                val_samples=val_samples, val_labels=val_labels,
                regime_detector=regime_detector, device=device, lr=lr,
            )
            log.info(f"  -> seed {seed} val_sharpe: {val_sharpe:.4f}")

            if val_sharpe > fold_best_sharpe:
                fold_best_sharpe = val_sharpe
                fold_best_ckpt = ckpt_path

            ensemble_ckpts.append(ckpt_path)

        log.info(f"Fold {fold+1} best val_sharpe: {fold_best_sharpe:.4f}")

        if fold_best_sharpe > best_global_val_sharpe:
            best_global_val_sharpe = fold_best_sharpe
            shutil.copy2(fold_best_ckpt, best_model_path)
            # Also copy temperature file
            temp_src = fold_best_ckpt.replace(".pt", "_temperature.pt")
            if os.path.exists(temp_src):
                shutil.copy2(temp_src, best_model_path.replace(".pt", "_temperature.pt"))
            log.info(f"New best model: fold {fold+1}, val_sharpe={fold_best_sharpe:.4f}")

    # Save ensemble manifest
    if n_ensemble > 1:
        manifest_path = os.path.join(cfg.paths.models_dir, "ensemble_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump({"members": ensemble_ckpts, "n": n_ensemble}, f, indent=2)
        log.info(f"Ensemble manifest saved to {manifest_path}")

    log.info(f"Training complete. Best val_sharpe: {best_global_val_sharpe:.4f}")
    log.info(f"Best model: {best_model_path}")


if __name__ == "__main__":
    main()
