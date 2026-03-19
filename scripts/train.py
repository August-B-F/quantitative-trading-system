"""Walk-forward model training.

Training strategy:
  - Splits history into N folds. Each fold:
      * Train on all data up to fold end
      * Validate on the next window
      * Save the checkpoint with best validation Sharpe
  - Optional Optuna hyperparameter search before final training run
  - Scalers are fitted on training data of first fold and reused
  - Final best checkpoint saved to data/models/best_model.pt

Usage:
    python scripts/train.py                         # train with config defaults
    python scripts/train.py --hparam-search         # run Optuna search first
    python scripts/train.py --folds 3 --epochs 50   # override folds/epochs
    python scripts/train.py --no-news               # skip FinBERT (faster iteration)
"""
import argparse
import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ultimate_trader.utils.config_loader import load_config
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.data_sources.alpaca_market import MarketDataFetcher
from ultimate_trader.data_sources.alpaca_news import NewsFetcher
from ultimate_trader.data_sources.alt_data import AltDataBuilder
from ultimate_trader.features.feature_builder import FeatureBuilder, TECH_FEATURES, SENTIMENT_FEATURES, MACRO_FEATURES
from ultimate_trader.features.regimes import RegimeDetector
from ultimate_trader.modeling.model import build_model
from ultimate_trader.modeling.losses import get_loss_fn
from ultimate_trader.modeling.metrics import sharpe_ratio
from ultimate_trader.modeling.hyperparam_search import run_search

log = get_logger("train")


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class TradeDataset(Dataset):
    def __init__(self, samples, labels):
        self.samples = samples
        self.labels = labels

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        return (
            torch.tensor(s["tech"], dtype=torch.float32),
            torch.tensor(s["sent"], dtype=torch.float32),
            torch.tensor(s["macro"], dtype=torch.float32),
            torch.tensor(s["sym_idx"], dtype=torch.long),
            torch.tensor(s["sec_idx"], dtype=torch.long),
            torch.tensor(self.labels[idx], dtype=torch.long),
        )


# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config")
    p.add_argument("--folds", type=int, default=None, help="Number of walk-forward folds")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--hparam-search", action="store_true", help="Run Optuna search before training")
    p.add_argument("--no-news", action="store_true", help="Use zero sentiment (skip FinBERT)")
    p.add_argument("--device", default=None, help="cuda / cpu (auto-detected if omitted)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Load data helpers
# ---------------------------------------------------------------------------
def load_all_data(cfg, no_news=False):
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
    macro_df = alt.build_macro_features(bars)

    if no_news or not cfg.news.enabled:
        sentiment = {}
    else:
        news = NewsFetcher(cfg)
        sentiment = news.fetch_and_score(list(cfg.universe.symbols))

    return bars, macro_df, sentiment


def build_symbol_maps(cfg):
    symbols = list(cfg.universe.symbols)
    symbol_to_idx = {s: i + 1 for i, s in enumerate(symbols)}  # 0 = padding

    # Sector grouping (rough - by known sector ETF dominance)
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


# ---------------------------------------------------------------------------
# Train one epoch
# ---------------------------------------------------------------------------
def train_epoch(model, loader, optimizer, criterion, device, scaler=None):
    model.train()
    total_loss = 0.0
    correct = 0
    n = 0
    for tech, sent, macro, sym_idx, sec_idx, labels in loader:
        tech, sent, macro = tech.to(device), sent.to(device), macro.to(device)
        sym_idx, sec_idx = sym_idx.to(device), sec_idx.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        if scaler is not None:
            with torch.autocast(device_type="cuda"):
                logits = model(tech, sent, macro, sym_idx, sec_idx)
                loss = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(tech, sent, macro, sym_idx, sec_idx)
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
    total_loss = 0.0
    correct = 0
    n = 0
    for tech, sent, macro, sym_idx, sec_idx, labels in loader:
        tech, sent, macro = tech.to(device), sent.to(device), macro.to(device)
        sym_idx, sec_idx = sym_idx.to(device), sec_idx.to(device)
        labels = labels.to(device)
        logits = model(tech, sent, macro, sym_idx, sec_idx)
        loss = criterion(logits, labels)
        total_loss += loss.item() * len(labels)
        correct += (logits.argmax(1) == labels).sum().item()
        n += len(labels)
    return total_loss / max(n, 1), correct / max(n, 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    cfg = load_config(args.config)
    tcfg = cfg.training
    mcfg = cfg.model

    device_str = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_str)
    log.info(f"Using device: {device}")

    os.makedirs(cfg.paths.models_dir, exist_ok=True)
    os.makedirs(cfg.paths.scalers_dir, exist_ok=True)
    os.makedirs(cfg.paths.processed_dir, exist_ok=True)

    # ---- Load data ----
    log.info("Loading market data...")
    bars, macro_df, sentiment = load_all_data(cfg, no_news=args.no_news)
    symbol_to_idx, symbol_to_sector = build_symbol_maps(cfg)
    symbols = [s for s in cfg.universe.symbols if s in bars]
    n_symbols = len(symbol_to_idx)
    n_sectors = max(symbol_to_sector.values(), default=1)

    # ---- Fit regime detector on SPY ----
    spy_bars = bars.get("SPY")
    regime_detector = RegimeDetector()
    if spy_bars is not None:
        regime_detector.fit(spy_bars)
        regime_path = os.path.join(cfg.paths.models_dir, "regime_detector.pkl")
        regime_detector.save(regime_path)
        log.info(f"Regime detector saved to {regime_path}")

    # ---- Feature builder ----
    fb = FeatureBuilder(cfg)

    # ---- Walk-forward folds ----
    n_folds = args.folds or tcfg.get("n_folds", 4)
    epochs = args.epochs or tcfg.get("epochs", 30)
    batch_size = args.batch_size or tcfg.get("batch_size", 256)
    lr = args.lr or tcfg.get("learning_rate", 1e-3)
    val_window = tcfg.get("val_window_days", 120)

    # Build full date index from SPY
    if spy_bars is not None:
        all_dates = spy_bars.index
    else:
        first_sym = next(iter(bars.values()))
        all_dates = first_sym.index

    fold_size = len(all_dates) // (n_folds + 1)
    best_global_val_acc = -1.0
    best_model_path = os.path.join(cfg.paths.models_dir, "best_model.pt")

    for fold in range(n_folds):
        train_end_idx = fold_size * (fold + 1)
        val_end_idx = min(train_end_idx + val_window, len(all_dates))
        train_dates = all_dates[:train_end_idx]
        val_dates = all_dates[train_end_idx:val_end_idx]

        if len(train_dates) < cfg.data.min_history_days or len(val_dates) < 20:
            log.info(f"Fold {fold+1}: not enough data, skipping")
            continue

        log.info(f"Fold {fold+1}/{n_folds}: train {train_dates[0].date()}--{train_dates[-1].date()}, "
                 f"val {val_dates[0].date()}--{val_dates[-1].date()}")

        # Build samples
        train_samples, train_labels = fb.build_training_samples(
            bars, sentiment, macro_df, symbols,
            symbol_to_idx, symbol_to_sector,
            date_range=train_dates,
            fit_scalers=(fold == 0),  # only fit scalers on first fold
        )
        val_samples, val_labels = fb.build_training_samples(
            bars, sentiment, macro_df, symbols,
            symbol_to_idx, symbol_to_sector,
            date_range=val_dates,
            fit_scalers=False,
        )

        if not train_samples or not val_samples:
            log.warning(f"Fold {fold+1}: empty samples, skipping")
            continue

        log.info(f"Fold {fold+1}: {len(train_samples)} train, {len(val_samples)} val samples")

        train_loader = DataLoader(TradeDataset(train_samples, train_labels),
                                  batch_size=batch_size, shuffle=True,
                                  num_workers=2, pin_memory=True)
        val_loader = DataLoader(TradeDataset(val_samples, val_labels),
                                batch_size=batch_size, shuffle=False,
                                num_workers=2, pin_memory=True)

        # Infer feature dims from first sample
        tech_dim = train_samples[0]["tech"].shape[-1]
        sent_dim = train_samples[0]["sent"].shape[-1]
        macro_dim = train_samples[0]["macro"].shape[-1]

        # ---- Optuna search (only on fold 0 if requested) ----
        if args.hparam_search and fold == 0:
            log.info("Running Optuna hyperparameter search...")

            def objective(trial, params):
                trial_model = build_model(
                    cfg, n_symbols, n_sectors, tech_dim, sent_dim, macro_dim
                ).to(device)
                opt = torch.optim.AdamW(trial_model.parameters(),
                                        lr=params.get("lr", lr),
                                        weight_decay=params.get("weight_decay", 1e-4))
                crit = nn.CrossEntropyLoss()
                for ep in range(10):  # short search epochs
                    train_epoch(trial_model, train_loader, opt, crit, device)
                _, val_acc = eval_epoch(trial_model, val_loader, crit, device)
                return val_acc

            search_space = getattr(tcfg, "hyperparam_search", {}).get("search_space", {
                "lr": [1e-4, 1e-2],
                "weight_decay": [1e-5, 1e-2],
            })
            best_params = run_search(objective, search_space,
                                     n_trials=tcfg.get("n_trials", 40),
                                     output_dir=cfg.paths.models_dir)
            if best_params:
                lr = best_params.get("lr", lr)
                log.info(f"Using best lr from Optuna: {lr}")

        # ---- Build and train model ----
        model = build_model(cfg, n_symbols, n_sectors,
                            tech_dim, sent_dim, macro_dim).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr,
                                      weight_decay=tcfg.get("weight_decay", 1e-4))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=epochs, eta_min=lr * 0.01
        )
        criterion = nn.CrossEntropyLoss(label_smoothing=tcfg.get("label_smoothing", 0.1))
        use_amp = (device.type == "cuda")
        scaler = torch.amp.GradScaler() if use_amp else None

        best_val_acc = -1.0
        patience_count = 0
        patience = tcfg.get("early_stopping_patience", 8)
        fold_ckpt = os.path.join(cfg.paths.models_dir, f"fold_{fold+1}.pt")

        for epoch in range(1, epochs + 1):
            tr_loss, tr_acc = train_epoch(model, train_loader, optimizer, criterion,
                                          device, scaler)
            val_loss, val_acc = eval_epoch(model, val_loader, criterion, device)
            scheduler.step()

            log.info(f"Fold {fold+1} Ep {epoch:03d} | "
                     f"tr_loss={tr_loss:.4f} tr_acc={tr_acc:.3f} | "
                     f"val_loss={val_loss:.4f} val_acc={val_acc:.3f}")

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                patience_count = 0
                torch.save({
                    "epoch": epoch,
                    "fold": fold + 1,
                    "model_state": model.state_dict(),
                    "val_acc": val_acc,
                    "tech_dim": tech_dim,
                    "sent_dim": sent_dim,
                    "macro_dim": macro_dim,
                    "n_symbols": n_symbols,
                    "n_sectors": n_sectors,
                    "symbol_to_idx": symbol_to_idx,
                    "symbol_to_sector": symbol_to_sector,
                }, fold_ckpt)
            else:
                patience_count += 1
                if patience_count >= patience:
                    log.info(f"Early stopping at epoch {epoch}")
                    break

        log.info(f"Fold {fold+1} best val_acc: {best_val_acc:.4f}")

        # Keep track of best model across all folds
        if best_val_acc > best_global_val_acc:
            best_global_val_acc = best_val_acc
            import shutil
            shutil.copy2(fold_ckpt, best_model_path)
            log.info(f"New best model saved: fold {fold+1}, val_acc={best_val_acc:.4f}")

    log.info(f"Training complete. Best val_acc across all folds: {best_global_val_acc:.4f}")
    log.info(f"Best model saved to: {best_model_path}")


if __name__ == "__main__":
    main()
