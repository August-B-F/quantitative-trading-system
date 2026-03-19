"""
model.py

Multi-input LSTM + Transformer hybrid PyTorch model.

Architecture:
  1. Price/Technical Branch   : BiLSTM -> Self-Attention -> Pool
  2. Sentiment Branch         : BiLSTM -> Pool
  3. Macro Branch             : MLP
  4. Company Embedding Branch : Embedding(n_companies, d_company)
  5. Sector Embedding Branch  : Embedding(n_sectors, d_sector)
  6. Regime Branch            : Linear(3 -> d)
  Fusion: Concat all -> LayerNorm -> MLP -> Dropout -> Classification head

Uncertainty:
  MC Dropout is done by keeping model in train() mode during inference
  for `mc_samples` forward passes. This is the correct implementation.
  (The old bot called model.predict() which DISABLES dropout, giving
  identical outputs each run and a std of ~0.)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple


class ScaledDotProductAttention(nn.Module):
    """Standard scaled dot-product self-attention over time dimension."""

    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_k = d_model // n_heads
        self.n_heads = n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.out = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, D)
        B, T, D = x.shape
        qkv = self.qkv(x).reshape(B, T, 3, self.n_heads, self.d_k)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # (3, B, H, T, d_k)
        q, k, v = qkv[0], qkv[1], qkv[2]

        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)
        attn = self.dropout(F.softmax(scores, dim=-1))
        out = torch.matmul(attn, v)  # (B, H, T, d_k)
        out = out.transpose(1, 2).reshape(B, T, D)
        return self.out(out)


class PriceBranch(nn.Module):
    """
    Bidirectional LSTM followed by multi-head self-attention.
    Returns a fixed-size vector (mean-pooled over time).
    """

    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int,
                 n_heads: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        lstm_out_dim = hidden_dim * 2  # bidirectional
        self.attn = ScaledDotProductAttention(lstm_out_dim, n_heads, dropout)
        self.norm = nn.LayerNorm(lstm_out_dim)
        self.dropout = nn.Dropout(dropout)
        self.out_dim = lstm_out_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F)
        lstm_out, _ = self.lstm(x)
        attn_out = self.attn(lstm_out)
        out = self.norm(lstm_out + attn_out)  # residual
        out = self.dropout(out.mean(dim=1))   # mean pool over time
        return out


class SentimentBranch(nn.Module):
    """Bidirectional LSTM for sentiment sequence -> mean pool."""

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.out_dim = hidden_dim * 2

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.dropout(out.mean(dim=1))


class MacroBranch(nn.Module):
    """Simple MLP for macro features (flat, no strong temporal structure)."""

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        flat_dim = input_dim  # will be flattened
        self.net = nn.Sequential(
            nn.Linear(flat_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.out_dim = hidden_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F) -> flatten time
        B = x.shape[0]
        return self.net(x.reshape(B, -1))


class StockPredictor(nn.Module):
    """
    Full multi-input prediction model.

    Inputs:
      price_x   : (B, price_window,    n_price_features)
      sent_x    : (B, sentiment_window, n_sent_features)
      macro_x   : (B, macro_window,     n_macro_features)
      regime_x  : (B, 3)    one-hot
      company   : (B,)      int index
      sector    : (B,)      int index

    Output:
      logits    : (B, num_classes)  -- pass through softmax for probs
    """

    def __init__(
        self,
        n_price_features: int,
        n_sent_features: int,
        n_macro_features: int,
        n_companies: int,
        n_sectors: int = 8,
        price_window: int = 40,
        macro_window: int = 20,
        price_hidden: int = 128,
        sent_hidden: int = 64,
        macro_hidden: int = 64,
        fusion_hidden: int = 256,
        num_lstm_layers: int = 2,
        n_heads: int = 4,
        company_emb_dim: int = 16,
        sector_emb_dim: int = 8,
        num_classes: int = 5,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.price_branch = PriceBranch(
            n_price_features, price_hidden, num_lstm_layers, n_heads, dropout
        )
        self.sent_branch = SentimentBranch(n_sent_features, sent_hidden, dropout)
        self.macro_branch = MacroBranch(n_macro_features * macro_window, macro_hidden, dropout)

        self.company_emb = nn.Embedding(n_companies + 1, company_emb_dim)
        self.sector_emb = nn.Embedding(n_sectors + 1, sector_emb_dim)
        self.regime_proj = nn.Linear(3, 16)

        fusion_in = (
            self.price_branch.out_dim
            + self.sent_branch.out_dim
            + macro_hidden
            + company_emb_dim
            + sector_emb_dim
            + 16  # regime
        )

        self.fusion = nn.Sequential(
            nn.LayerNorm(fusion_in),
            nn.Linear(fusion_in, fusion_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_hidden, fusion_hidden // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_hidden // 2, num_classes),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, 0, 0.01)

    def forward(
        self,
        price_x: torch.Tensor,
        sent_x: torch.Tensor,
        macro_x: torch.Tensor,
        regime_x: torch.Tensor,
        company: torch.Tensor,
        sector: torch.Tensor,
    ) -> torch.Tensor:

        price_feat = self.price_branch(price_x)
        sent_feat = self.sent_branch(sent_x)
        macro_feat = self.macro_branch(macro_x)
        company_feat = self.company_emb(company)
        sector_feat = self.sector_emb(sector)
        regime_feat = F.relu(self.regime_proj(regime_x))

        fused = torch.cat([
            price_feat, sent_feat, macro_feat,
            company_feat, sector_feat, regime_feat
        ], dim=-1)

        return self.fusion(fused)

    # ------------------------------------------------------------------
    # MC Dropout inference
    # ------------------------------------------------------------------

    def predict_with_uncertainty(
        self,
        price_x: torch.Tensor,
        sent_x: torch.Tensor,
        macro_x: torch.Tensor,
        regime_x: torch.Tensor,
        company: torch.Tensor,
        sector: torch.Tensor,
        n_samples: int = 50,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs n_samples stochastic forward passes (dropout ON).
        Returns:
          mean_probs  : (B, num_classes)  mean softmax probabilities
          uncertainty : (B,)              predictive entropy (higher = less sure)
        """
        self.train()  # CRITICAL: enables dropout for MC sampling
        with torch.no_grad():
            all_probs = []
            for _ in range(n_samples):
                logits = self(
                    price_x, sent_x, macro_x,
                    regime_x, company, sector
                )
                probs = F.softmax(logits, dim=-1)  # (B, C)
                all_probs.append(probs.unsqueeze(0))

        all_probs = torch.cat(all_probs, dim=0)  # (S, B, C)
        mean_probs = all_probs.mean(dim=0)        # (B, C)

        # Predictive entropy: H = -sum(p * log(p))
        entropy = -(mean_probs * (mean_probs + 1e-10).log()).sum(dim=-1)  # (B,)
        # Normalize to [0, 1] by dividing by max entropy (log(n_classes))
        max_entropy = torch.log(torch.tensor(mean_probs.shape[-1], dtype=torch.float))
        uncertainty = entropy / max_entropy  # (B,)  0=certain, 1=maximally uncertain

        self.eval()  # back to eval for any non-MC usage
        return mean_probs, uncertainty
