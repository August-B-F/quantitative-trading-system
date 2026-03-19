"""Multi-input LSTM + Transformer stock prediction model (PyTorch).

Architecture:
  - Price/technical branch:  BiLSTM -> Self-Attention
  - Sentiment branch:        BiLSTM
  - Macro branch:            BiLSTM
  - Company embedding:       nn.Embedding
  - Regime embedding:        nn.Embedding
  - All concat -> MLP head -> 5-class output

Uncertainty: MC-Dropout at inference (model.train() with torch.no_grad())
"""
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path


class AttentionPooling(nn.Module):
    """Learnable weighted pooling over a sequence."""
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, H)
        weights = torch.softmax(self.attn(x), dim=1)  # (B, T, 1)
        return (weights * x).sum(dim=1)               # (B, H)


class SequenceBranch(nn.Module):
    """BiLSTM + attention pooling for one input stream."""
    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim // 2,   # bidirectional doubles it back
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        self.drop = nn.Dropout(dropout)
        self.pool = AttentionPooling(hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, input_dim)
        out, _ = self.lstm(x)          # (B, T, hidden_dim)
        out = self.drop(out)
        out = self.pool(out)           # (B, hidden_dim)
        return self.norm(out)


class TransformerBranch(nn.Module):
    """Small Transformer encoder for the price branch."""
    def __init__(self, input_dim: int, hidden_dim: int, num_heads: int, dropout: float):
        super().__init__()
        self.proj = nn.Linear(input_dim, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True,
            norm_first=True   # Pre-LN for stability
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.pool = AttentionPooling(hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.proj(x)           # (B, T, hidden_dim)
        x = self.encoder(x)        # (B, T, hidden_dim)
        x = self.pool(x)           # (B, hidden_dim)
        return self.norm(x)


class StockPredictor(nn.Module):
    def __init__(
        self,
        n_price_features: int,
        n_sent_features: int,
        n_macro_features: int,
        n_symbols: int,
        cfg: dict
    ):
        super().__init__()
        m = cfg["model"]
        self.hidden_dim = m["hidden_dim"]
        self.dropout_rate = m["dropout"]
        emb_dim = m["company_embedding_dim"]
        num_regimes = 3
        regime_emb_dim = 8

        # --- Input branches
        self.price_branch = TransformerBranch(
            n_price_features, self.hidden_dim, m["num_attention_heads"], m["dropout"]
        )
        self.sentiment_branch = SequenceBranch(
            n_sent_features, self.hidden_dim, m["num_lstm_layers"], m["dropout"]
        )
        self.macro_branch = SequenceBranch(
            n_macro_features, m["macro_hidden_dim"], 1, m["dropout"]
        )

        # --- Embeddings
        self.symbol_emb = nn.Embedding(n_symbols + 1, emb_dim, padding_idx=0)
        self.regime_emb = nn.Embedding(num_regimes, regime_emb_dim)

        # --- MLP head
        combined_dim = (
            self.hidden_dim       # price
            + self.hidden_dim     # sentiment
            + m["macro_hidden_dim"]  # macro
            + emb_dim             # symbol
            + regime_emb_dim      # regime
        )
        fc_dims = m["fc_dims"]
        layers = []
        in_dim = combined_dim
        for out_dim in fc_dims:
            layers += [
                nn.Linear(in_dim, out_dim),
                nn.GELU(),
                nn.Dropout(m["dropout"]),
                nn.LayerNorm(out_dim)
            ]
            in_dim = out_dim
        layers.append(nn.Linear(in_dim, m["num_classes"]))
        self.head = nn.Sequential(*layers)

    def forward(
        self,
        price_seq: torch.Tensor,      # (B, T_p, F_p)
        sentiment_seq: torch.Tensor,  # (B, T_s, F_s)
        macro_seq: torch.Tensor,      # (B, T_m, F_m)
        symbol_idx: torch.Tensor,     # (B,)
        regime: torch.Tensor          # (B,)
    ) -> torch.Tensor:
        p = self.price_branch(price_seq)
        s = self.sentiment_branch(sentiment_seq)
        m = self.macro_branch(macro_seq)
        sym = self.symbol_emb(symbol_idx)
        reg = self.regime_emb(regime)
        combined = torch.cat([p, s, m, sym, reg], dim=1)
        return self.head(combined)   # (B, num_classes) logits

    # ------------------------------------------------------------------ inference

    @torch.no_grad()
    def predict_with_uncertainty(
        self,
        price_seq: torch.Tensor,
        sentiment_seq: torch.Tensor,
        macro_seq: torch.Tensor,
        symbol_idx: torch.Tensor,
        regime: torch.Tensor,
        n_samples: int = 50
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        MC-Dropout inference: run the model n_samples times in train mode
        to get stochastic outputs via dropout.

        Returns:
          mean_probs: (B, num_classes) mean softmax probabilities
          uncertainty: (B,) predictive entropy as uncertainty score
        """
        self.train()   # Enable dropout
        probs_list = []
        for _ in range(n_samples):
            logits = self(
                price_seq, sentiment_seq, macro_seq, symbol_idx, regime
            )
            probs_list.append(torch.softmax(logits, dim=-1).cpu().numpy())
        self.eval()

        probs_stack = np.stack(probs_list, axis=0)  # (N, B, C)
        mean_probs = probs_stack.mean(axis=0)       # (B, C)
        # Predictive entropy: H = -sum(p * log(p))
        eps = 1e-8
        entropy = -np.sum(mean_probs * np.log(mean_probs + eps), axis=-1)  # (B,)
        # Normalise to [0,1] by dividing by max possible entropy log(num_classes)
        max_entropy = np.log(mean_probs.shape[-1])
        uncertainty = entropy / max_entropy

        return mean_probs, uncertainty

    def save(self, path: str | Path) -> None:
        torch.save(self.state_dict(), path)

    @classmethod
    def load(cls, path: str | Path, cfg: dict, n_price_features: int,
             n_sent_features: int, n_macro_features: int, n_symbols: int) -> "StockPredictor":
        model = cls(n_price_features, n_sent_features, n_macro_features, n_symbols, cfg)
        model.load_state_dict(torch.load(path, map_location="cpu"))
        model.eval()
        return model
