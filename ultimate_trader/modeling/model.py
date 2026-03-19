"""Ultimate multi-input stock prediction model in PyTorch.

Architecture:
  Branch 1: Bidirectional LSTM + Attention  -> price/technical time series
  Branch 2: Bidirectional LSTM              -> sentiment time series
  Branch 3: Small MLP                       -> macro snapshot (VIX, yields, etc.)
  Branch 4: Embedding layer                 -> symbol identity
  Fusion:   Concat -> LayerNorm -> 2x Linear -> Dropout -> 5-class output

Uncertainty:
  MC Dropout: inference with model.train() for N samples.
  Confidence = 1 - entropy(mean_probs).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class AttentionPool(nn.Module):
    """Learnable attention pooling over a sequence (B, T, H) -> (B, H)."""
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        # x: (B, T, H)
        weights = torch.softmax(self.attn(x), dim=1)  # (B, T, 1)
        return (weights * x).sum(dim=1)               # (B, H)


class PriceBranch(nn.Module):
    """Bidirectional LSTM with attention pooling for price/technical features."""
    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attn = AttentionPool(hidden_dim * 2)
        self.dropout = nn.Dropout(dropout)
        self.output_dim = hidden_dim * 2

    def forward(self, x):
        # x: (B, T, input_dim)
        out, _ = self.lstm(x)           # (B, T, H*2)
        out = self.dropout(out)
        return self.attn(out)           # (B, H*2)


class SentimentBranch(nn.Module):
    """Bidirectional LSTM for sentiment time series."""
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        self.attn = AttentionPool(hidden_dim * 2)
        self.dropout = nn.Dropout(dropout)
        self.output_dim = hidden_dim * 2

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.attn(self.dropout(out))


class MacroBranch(nn.Module):
    """MLP for macro/regime snapshot features."""
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
        )
        self.output_dim = hidden_dim

    def forward(self, x):
        return self.net(x)


class UltimateStockModel(nn.Module):
    """
    Full multi-branch model.

    Args:
        price_input_dim:     number of price/technical features per timestep
        sentiment_input_dim: number of sentiment features per timestep
        macro_input_dim:     number of macro/regime scalar features
        num_symbols:         vocabulary size for symbol embedding
        cfg:                 model config dict
    """
    def __init__(
        self,
        price_input_dim: int,
        sentiment_input_dim: int,
        macro_input_dim: int,
        num_symbols: int,
        cfg: dict,
    ):
        super().__init__()
        mcfg = cfg["model"]
        hidden = mcfg["hidden_dim"]
        dropout = mcfg["dropout"]

        # Branches
        self.price_branch = PriceBranch(
            price_input_dim, hidden, mcfg["num_layers"], dropout
        )
        self.sentiment_branch = SentimentBranch(
            sentiment_input_dim, hidden // 2, dropout
        )
        self.macro_branch = MacroBranch(
            macro_input_dim, mcfg["macro_hidden_dim"], dropout
        )
        self.symbol_embedding = nn.Embedding(
            num_symbols, mcfg["company_embedding_dim"]
        )

        # Fusion
        fusion_in = (
            self.price_branch.output_dim
            + self.sentiment_branch.output_dim
            + self.macro_branch.output_dim
            + mcfg["company_embedding_dim"]
        )
        fusion_hidden = mcfg["fusion_hidden_dim"]
        self.fusion = nn.Sequential(
            nn.LayerNorm(fusion_in),
            nn.Linear(fusion_in, fusion_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_hidden, fusion_hidden // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_hidden // 2, 5),  # 5-class output
        )

    def forward(
        self,
        price_seq,       # (B, T_price, price_input_dim)
        sentiment_seq,   # (B, T_sent, sentiment_input_dim)
        macro_snap,      # (B, macro_input_dim)
        symbol_idx,      # (B,) long
    ):
        p = self.price_branch(price_seq)
        s = self.sentiment_branch(sentiment_seq)
        m = self.macro_branch(macro_snap)
        e = self.symbol_embedding(symbol_idx)          # (B, emb_dim)
        fused = torch.cat([p, s, m, e], dim=-1)
        return self.fusion(fused)                      # (B, 5) logits


# ── Inference utilities ──────────────────────────────────────────────────────

def mc_dropout_predict(
    model: UltimateStockModel,
    price_seq: torch.Tensor,
    sentiment_seq: torch.Tensor,
    macro_snap: torch.Tensor,
    symbol_idx: torch.Tensor,
    n_samples: int = 50,
    device: str = "cpu",
) -> dict:
    """
    MC Dropout inference. model.train() is used to keep dropout active.
    Returns dict with mean_probs, std_probs, confidence, predicted_class.

    confidence = 1 - normalised_entropy(mean_probs)
    """
    model.train()   # CRITICAL: keeps dropout stochastic
    model.to(device)

    all_probs = []
    with torch.no_grad():
        for _ in range(n_samples):
            logits = model(
                price_seq.to(device),
                sentiment_seq.to(device),
                macro_snap.to(device),
                symbol_idx.to(device),
            )
            probs = F.softmax(logits, dim=-1).cpu().numpy()
            all_probs.append(probs)

    all_probs = np.array(all_probs)          # (N, B, 5)
    mean_probs = all_probs.mean(axis=0)      # (B, 5)
    std_probs = all_probs.std(axis=0)        # (B, 5)

    # entropy-based confidence
    eps = 1e-8
    entropy = -np.sum(mean_probs * np.log(mean_probs + eps), axis=-1)  # (B,)
    max_entropy = np.log(mean_probs.shape[-1])                          # log(5)
    confidence = 1.0 - entropy / max_entropy                           # (B,)

    predicted_class = mean_probs.argmax(axis=-1)                       # (B,)

    return {
        "mean_probs": mean_probs,
        "std_probs": std_probs,
        "confidence": confidence,
        "predicted_class": predicted_class,
    }


def save_model(model: nn.Module, path: str):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(model.state_dict(), path)


def load_model(model: nn.Module, path: str, device: str = "cpu") -> nn.Module:
    state = torch.load(path, map_location=device)
    model.load_state_dict(state)
    return model
