"""Multi-branch PyTorch model for stock direction prediction.

Architecture:
  Branch 1 - Price/Technical: Bi-LSTM -> Self-Attention (full sequence mean pooling)
  Branch 2 - Sentiment:       Bi-LSTM -> mean pool (full sequence)
  Branch 3 - Macro:           Bi-LSTM -> mean pool (full sequence)
  Branch 4 - Symbol identity: Embedding(n_symbols, d_sym)
  Branch 5 - Sector identity: Embedding(n_sectors, d_sec)
  Cross-Attention: tech attends over sentiment branch
  Regime embedding: injected into MLP head
  All branches -> Concat -> LayerNorm -> MLP -> 5-class softmax

MC Dropout uncertainty:
  model.train() kept on at inference -> dropout stochastic -> run N times

Deep Ensemble:
  EnsembleModel wraps N independently trained UltraTradingModels
"""
import torch
import torch.nn as nn
from typing import Tuple, List, Optional

NUM_REGIMES = 4  # bull, bear, sideways, unknown


class BranchLSTM(nn.Module):
    """Bi-LSTM encoder returning full sequence output."""

    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int, dropout: float):
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
        """Returns full sequence: (B, T, hidden*2)"""
        out, _ = self.lstm(x)
        return self.dropout(out)


class SelfAttentionPooling(nn.Module):
    """Multi-head self-attention -> mean pool over sequence."""

    def __init__(self, d_model: int, num_heads: int, dropout: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model, num_heads=num_heads,
            dropout=dropout, batch_first=True
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (mean_pooled, last_token) - both (B, d_model)"""
        attn_out, _ = self.attn(x, x, x)
        x = self.norm(x + self.dropout(attn_out))
        return x.mean(dim=1), x[:, -1, :]  # mean pool + last token


class CrossAttention(nn.Module):
    """Cross-attention: query=tech, key/value=sentiment.
    Lets tech branch attend to sentiment when relevant.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float):
        super().__init__()
        # Project sentiment to same dim as tech if needed
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model, num_heads=num_heads,
            dropout=dropout, batch_first=True
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, tech_seq: torch.Tensor, sent_seq: torch.Tensor) -> torch.Tensor:
        """tech_seq attends to sent_seq. Returns (B, d_tech)."""
        # sent_seq may be shorter; that's fine for cross-attention
        attn_out, _ = self.attn(query=tech_seq, key=sent_seq, value=sent_seq)
        x = self.norm(tech_seq + self.dropout(attn_out))
        return x.mean(dim=1)  # (B, d_model)


class UltraTradingModel(nn.Module):
    """
    Full multi-branch trading model with:
    - Cross-branch attention (tech attends to sentiment)
    - Full sequence mean pooling on all branches
    - Regime embedding injected into MLP head
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
        final_hidden_dims: Tuple[int, ...] = (256, 128),
        dropout: float = 0.25,
        num_classes: int = 5,
        regime_embedding_dim: int = 8,
    ):
        super().__init__()
        self.dropout_p = dropout

        # ── Branch 1: Tech/Price ──────────────────────────────────────
        self.tech_lstm = BranchLSTM(tech_input_dim, hidden_dim, num_lstm_layers, dropout)
        self.tech_attn = SelfAttentionPooling(hidden_dim * 2, num_attn_heads, dropout)
        # tech produces: mean_pool + last_token = hidden*4
        tech_out = hidden_dim * 4

        # ── Branch 2: Sentiment ───────────────────────────────────────
        sent_hidden = hidden_dim // 2
        self.sent_lstm = BranchLSTM(sent_input_dim, sent_hidden, num_lstm_layers, dropout)
        # Full sequence mean pooling (replaces last-timestep only)
        sent_out = sent_hidden * 2

        # ── Cross-attention: tech queries sentiment ───────────────────
        # Project sent to tech dim for cross-attn
        self.sent_proj = nn.Linear(sent_hidden * 2, hidden_dim * 2)
        self.cross_attn = CrossAttention(hidden_dim * 2, num_attn_heads, dropout)
        cross_out = hidden_dim * 2

        # ── Branch 3: Macro ───────────────────────────────────────────
        self.macro_lstm = BranchLSTM(macro_input_dim, macro_hidden_dim, 1, dropout)
        macro_out = macro_hidden_dim * 2

        # ── Branch 4 & 5: Embeddings ──────────────────────────────────
        self.sym_embed = nn.Embedding(n_symbols + 1, company_embedding_dim, padding_idx=0)
        self.sym_dropout = nn.Dropout(dropout)
        self.sec_embed = nn.Embedding(n_sectors + 1, sector_embedding_dim, padding_idx=0)

        # ── Regime embedding (injected into head) ─────────────────────
        self.regime_embed = nn.Embedding(NUM_REGIMES + 1, regime_embedding_dim, padding_idx=0)

        # ── MLP head ─────────────────────────────────────────────────
        total_dim = (
            tech_out + sent_out + cross_out + macro_out
            + company_embedding_dim + sector_embedding_dim
            + regime_embedding_dim
        )
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
        tech: torch.Tensor,         # (B, price_window, tech_dim)
        sent: torch.Tensor,         # (B, sent_window, sent_dim)
        macro: torch.Tensor,        # (B, macro_window, macro_dim)
        sym_idx: torch.Tensor,      # (B,) long
        sec_idx: torch.Tensor,      # (B,) long
        regime_idx: torch.Tensor,   # (B,) long  0=unknown,1=bull,2=bear,3=sideways
    ) -> torch.Tensor:

        # ── Tech branch: LSTM -> self-attention -> mean+last concat ──
        tech_seq = self.tech_lstm(tech)           # (B, T, H*2)
        tech_mean, tech_last = self.tech_attn(tech_seq)
        tech_feat = torch.cat([tech_mean, tech_last], dim=-1)  # (B, H*4)

        # ── Sentiment branch: LSTM -> mean pool ──────────────────────
        sent_seq = self.sent_lstm(sent)           # (B, T, Hs*2)
        sent_feat = sent_seq.mean(dim=1)          # (B, Hs*2)

        # ── Cross-attention: tech queries sentiment ───────────────────
        sent_proj = self.sent_proj(sent_seq)      # (B, T, H*2)
        cross_feat = self.cross_attn(tech_seq, sent_proj)  # (B, H*2)

        # ── Macro branch: LSTM -> mean pool ──────────────────────────
        macro_seq = self.macro_lstm(macro)
        macro_feat = macro_seq.mean(dim=1)        # (B, Hm*2)

        # ── Embeddings ───────────────────────────────────────────────
        sym_feat = self.sym_dropout(self.sym_embed(sym_idx))
        sec_feat = self.sec_embed(sec_idx)
        reg_feat = self.regime_embed(regime_idx)

        # ── Concat + classify ────────────────────────────────────────
        combined = torch.cat(
            [tech_feat, sent_feat, cross_feat, macro_feat,
             sym_feat, sec_feat, reg_feat], dim=-1
        )
        return self.classifier(combined)

    def predict_with_uncertainty(
        self,
        tech, sent, macro, sym_idx, sec_idx, regime_idx,
        n_samples: int = 50
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        MC Dropout inference. Returns (mean_probs, uncertainty) both (B, C).
        uncertainty = normalised predictive entropy [0, 1].
        """
        self.train()  # keep dropout active
        all_probs = []
        with torch.no_grad():
            for _ in range(n_samples):
                logits = self(tech, sent, macro, sym_idx, sec_idx, regime_idx)
                all_probs.append(torch.softmax(logits, dim=-1).unsqueeze(0))

        all_probs = torch.cat(all_probs, dim=0)   # (n_samples, B, C)
        mean_probs = all_probs.mean(dim=0)         # (B, C)
        entropy = -(mean_probs * (mean_probs + 1e-9).log()).sum(dim=-1)
        max_entropy = torch.log(torch.tensor(float(mean_probs.shape[-1])))
        uncertainty = entropy / max_entropy
        self.eval()
        return mean_probs, uncertainty


class EnsembleModel(nn.Module):
    """
    Deep Ensemble of N independently trained UltraTradingModels.
    At inference: averages probabilities across all members.
    Better calibrated than MC Dropout alone.
    """

    def __init__(self, models: List[UltraTradingModel]):
        super().__init__()
        self.members = nn.ModuleList(models)

    def predict(
        self, tech, sent, macro, sym_idx, sec_idx, regime_idx,
        mc_samples: int = 10
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Average MC Dropout predictions from all ensemble members.
        Returns (mean_probs, uncertainty).
        """
        all_probs = []
        for member in self.members:
            probs, _ = member.predict_with_uncertainty(
                tech, sent, macro, sym_idx, sec_idx, regime_idx,
                n_samples=mc_samples
            )
            all_probs.append(probs.unsqueeze(0))

        stacked = torch.cat(all_probs, dim=0)  # (N, B, C)
        mean_probs = stacked.mean(dim=0)       # (B, C)
        # Ensemble disagreement as additional uncertainty
        entropy = -(mean_probs * (mean_probs + 1e-9).log()).sum(dim=-1)
        max_entropy = torch.log(torch.tensor(float(mean_probs.shape[-1])))
        uncertainty = entropy / max_entropy
        return mean_probs, uncertainty


REGIME_TO_IDX = {"bull": 1, "bear": 2, "sideways": 3, "unknown": 0}


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
