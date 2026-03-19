"""Multi-branch PyTorch model for stock direction prediction.

Architecture:
  Branch 1 - Price/Technical: Bi-LSTM -> Self-Attention
  Branch 2 - Sentiment:       Bi-LSTM
  Branch 3 - Macro:           Bi-LSTM
  Branch 4 - Symbol identity: Embedding(n_symbols, d_sym)
  Branch 5 - Sector identity: Embedding(n_sectors, d_sec)
  All branches -> Concat -> LayerNorm -> MLP -> 5-class softmax

MC Dropout uncertainty:
  model.train() kept on at inference -> dropout stochastic -> run N times
"""
import torch
import torch.nn as nn
from typing import Tuple


class BranchLSTM(nn.Module):
    """Bi-LSTM encoder for a time-series branch."""

    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int,
                 dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.out_dim = hidden_dim * 2  # bidirectional

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq, features)
        out, _ = self.lstm(x)
        # Use last timestep from both directions
        out = self.dropout(out[:, -1, :])
        return out


class SelfAttention(nn.Module):
    """Multi-head self-attention pooling over sequence."""

    def __init__(self, d_model: int, num_heads: int, dropout: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model, num_heads=num_heads,
            dropout=dropout, batch_first=True
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq, d_model)
        attn_out, _ = self.attn(x, x, x)
        x = self.norm(x + self.dropout(attn_out))
        return x[:, -1, :]  # take last token after attention


class UltraTradingModel(nn.Module):
    """
    Full multi-branch trading model.
    """

    def __init__(
        self,
        tech_input_dim: int,
        sent_input_dim: int,
        macro_input_dim: int,
        n_symbols: int,
        n_sectors: int,
        hidden_dim: int = 128,
        num_lstm_layers: int = 2,
        num_attn_heads: int = 4,
        company_embedding_dim: int = 16,
        sector_embedding_dim: int = 8,
        macro_hidden_dim: int = 64,
        final_hidden_dims: Tuple[int] = (256, 128),
        dropout: float = 0.25,
        num_classes: int = 5,
    ):
        super().__init__()
        self.dropout = dropout

        # Branch 1: Tech/Price with LSTM + attention
        self.tech_lstm = BranchLSTM(tech_input_dim, hidden_dim, num_lstm_layers, dropout)
        self.tech_attn = SelfAttention(hidden_dim * 2, num_attn_heads, dropout)
        # We feed both last-timestep and attention output into classifier
        tech_out = hidden_dim * 4  # lstm_out + attn_out

        # Branch 2: Sentiment LSTM
        self.sent_lstm = BranchLSTM(sent_input_dim, hidden_dim // 2, num_lstm_layers, dropout)
        sent_out = hidden_dim

        # Branch 3: Macro LSTM
        self.macro_lstm = BranchLSTM(macro_input_dim, macro_hidden_dim, 1, dropout)
        macro_out = macro_hidden_dim * 2

        # Branch 4: Symbol embedding
        self.sym_embed = nn.Embedding(n_symbols + 1, company_embedding_dim, padding_idx=0)
        self.sym_dropout = nn.Dropout(dropout)

        # Branch 5: Sector embedding
        self.sec_embed = nn.Embedding(n_sectors + 1, sector_embedding_dim, padding_idx=0)

        # Concat all branches
        total_dim = tech_out + sent_out + macro_out + company_embedding_dim + sector_embedding_dim

        # MLP head
        layers = []
        in_dim = total_dim
        for out_dim in final_hidden_dims:
            layers += [
                nn.Linear(in_dim, out_dim),
                nn.LayerNorm(out_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            ]
            in_dim = out_dim
        layers.append(nn.Linear(in_dim, num_classes))
        self.classifier = nn.Sequential(*layers)

    def forward(
        self,
        tech: torch.Tensor,       # (B, price_window, tech_dim)
        sent: torch.Tensor,       # (B, sent_window, sent_dim)
        macro: torch.Tensor,      # (B, macro_window, macro_dim)
        sym_idx: torch.Tensor,    # (B,) long
        sec_idx: torch.Tensor,    # (B,) long
    ) -> torch.Tensor:
        # Tech branch: run LSTM, then attention on LSTM output
        lstm_out_seq, _ = self.tech_lstm.lstm(tech)
        lstm_last = self.tech_lstm.dropout(lstm_out_seq[:, -1, :])
        attn_out = self.tech_attn(lstm_out_seq)
        tech_feat = torch.cat([lstm_last, attn_out], dim=-1)

        # Sentiment branch
        sent_feat = self.sent_lstm(sent)

        # Macro branch
        macro_feat = self.macro_lstm(macro)

        # Embedding branches
        sym_feat = self.sym_dropout(self.sym_embed(sym_idx))
        sec_feat = self.sec_embed(sec_idx)

        # Concatenate
        combined = torch.cat([tech_feat, sent_feat, macro_feat, sym_feat, sec_feat], dim=-1)

        return self.classifier(combined)

    def predict_with_uncertainty(
        self, tech, sent, macro, sym_idx, sec_idx, n_samples: int = 50
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        MC Dropout inference: run forward pass n_samples times with dropout ON.
        Returns (mean_probs, uncertainty) both shape (B, num_classes).
        uncertainty = predictive entropy across samples.
        """
        self.train()  # keep dropout active
        all_probs = []

        with torch.no_grad():
            for _ in range(n_samples):
                logits = self(tech, sent, macro, sym_idx, sec_idx)
                probs = torch.softmax(logits, dim=-1)
                all_probs.append(probs.unsqueeze(0))

        all_probs = torch.cat(all_probs, dim=0)  # (n_samples, B, C)
        mean_probs = all_probs.mean(dim=0)        # (B, C)

        # Predictive entropy: H = -sum(p * log(p))
        entropy = -(mean_probs * (mean_probs + 1e-9).log()).sum(dim=-1)  # (B,)
        # Normalize to [0, 1] by dividing by max entropy = log(num_classes)
        max_entropy = torch.log(torch.tensor(float(mean_probs.shape[-1])))
        uncertainty = entropy / max_entropy

        self.eval()
        return mean_probs, uncertainty


def build_model(cfg, n_symbols: int, n_sectors: int,
                tech_dim: int, sent_dim: int, macro_dim: int) -> UltraTradingModel:
    """Build model from config."""
    m = cfg.model
    return UltraTradingModel(
        tech_input_dim=tech_dim,
        sent_input_dim=sent_dim,
        macro_input_dim=macro_dim,
        n_symbols=n_symbols,
        n_sectors=n_sectors,
        hidden_dim=m.hidden_dim,
        num_lstm_layers=m.num_lstm_layers,
        num_attn_heads=m.num_attn_heads,
        company_embedding_dim=m.company_embedding_dim,
        sector_embedding_dim=m.sector_embedding_dim,
        macro_hidden_dim=m.macro_hidden_dim,
        final_hidden_dims=tuple(m.final_hidden_dims),
        dropout=m.dropout,
        num_classes=m.num_classes,
    )
