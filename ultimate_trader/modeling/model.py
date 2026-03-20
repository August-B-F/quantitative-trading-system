"""Multi-branch PyTorch model for stock direction prediction.

Architecture:
  Branch 1 - Price/Technical: TransformerEncoder (4L, 8H, ff=1024) -> Self-Attention mean+last pool
  Branch 2 - Sentiment:       TransformerEncoder (4L, 8H, ff=512)  -> mean pool
  Branch 3 - Macro:           TransformerEncoder (4L, 8H, ff=512)  -> mean pool
  Branch 4 - Fundamentals:    MLP (static features) -> 64-dim
  Branch 5 - Symbol identity: Embedding(n_symbols, d_sym)
  Branch 6 - Sector identity: Embedding(n_sectors, d_sec)
  Cross-Attention: tech attends over projected sentiment branch
  Regime embedding: injected into MLP head
  All branches -> Concat -> LayerNorm -> MLP(512->256->128) -> 5-class

Temperature scaling:
  model.temperature is a learned scalar (init=1.0) applied to logits at inference.
  TemperatureScaler.fit() optimises it post-hoc using L-BFGS on a val set.

MC Dropout uncertainty:
  model.train() kept on at inference -> dropout stochastic -> run N times

Deep Ensemble:
  EnsembleModel wraps N independently trained UltraTradingModels
"""
import math
import torch
import torch.nn as nn
from typing import Tuple, List, Optional

NUM_REGIMES = 5  # bull, bear, sideways, crisis, unknown

REGIME_TO_IDX = {
    "bull": 1,
    "bear": 2,
    "sideways": 3,
    "crisis": 4,
    "unknown": 0,
}


# ── Positional Encoding ───────────────────────────────────────────────────────

class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding added to sequence embeddings."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


# ── Branch Transformer ────────────────────────────────────────────────────────

class BranchTransformer(nn.Module):
    """
    TransformerEncoder branch with linear input projection and sinusoidal PE.
    Replaces the former BranchLSTM with a faster, more expressive architecture.
    """

    def __init__(
        self,
        input_dim: int,
        d_model: int,
        num_layers: int,
        num_heads: int,
        ff_dim: int,
        dropout: float,
    ):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        self.pos_enc = PositionalEncoding(d_model, dropout=dropout)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=ff_dim,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
            norm_first=True,   # Pre-LN for training stability
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers,
        )
        self.out_dim = d_model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, T, input_dim)  ->  (B, T, d_model)"""
        x = self.input_proj(x)
        x = self.pos_enc(x)
        return self.encoder(x)


# ── Attention Pooling ─────────────────────────────────────────────────────────

class SelfAttentionPooling(nn.Module):
    """Multi-head self-attention -> (mean_pooled, last_token) concat."""

    def __init__(self, d_model: int, num_heads: int, dropout: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model, num_heads=num_heads,
            dropout=dropout, batch_first=True,
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (mean_pooled, last_token) — both (B, d_model)"""
        attn_out, _ = self.attn(x, x, x)
        x = self.norm(x + self.dropout(attn_out))
        return x.mean(dim=1), x[:, -1, :]


class CrossAttention(nn.Module):
    """Cross-attention: query=tech, key/value=sentiment.
    Lets tech branch attend to sentiment when semantically relevant.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model, num_heads=num_heads,
            dropout=dropout, batch_first=True,
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, tech_seq: torch.Tensor, sent_seq: torch.Tensor) -> torch.Tensor:
        """tech_seq attends to sent_seq. Returns (B, d_model)."""
        attn_out, _ = self.attn(query=tech_seq, key=sent_seq, value=sent_seq)
        x = self.norm(tech_seq + self.dropout(attn_out))
        return x.mean(dim=1)


# ── Main Model ────────────────────────────────────────────────────────────────

class UltraTradingModel(nn.Module):
    """
    Full multi-branch trading model with:
    - Transformer encoders (not LSTM) for all sequence branches
    - Sinusoidal positional encoding on all sequence inputs
    - Cross-branch attention (tech attends to sentiment)
    - Fundamentals MLP branch (static features)
    - Regime embedding injected into MLP head
    - Temperature scalar for post-hoc calibration
    - MC Dropout uncertainty estimation
    """

    def __init__(
        self,
        tech_input_dim: int,
        sent_input_dim: int,
        macro_input_dim: int,
        fund_input_dim: int,
        n_symbols: int,
        n_sectors: int,
        hidden_dim: int = 256,
        num_transformer_layers: int = 4,
        num_attn_heads: int = 8,
        transformer_ff_dim: int = 1024,
        company_embedding_dim: int = 16,
        sector_embedding_dim: int = 8,
        macro_hidden_dim: int = 128,
        final_hidden_dims: Tuple[int, ...] = (512, 256, 128),
        dropout: float = 0.25,
        num_classes: int = 5,
        regime_embedding_dim: int = 8,
    ):
        super().__init__()
        self.dropout_p = dropout

        sent_dim = hidden_dim // 2      # 128 for hidden_dim=256
        macro_dim = macro_hidden_dim    # 128

        # ── Branch 1: Tech/Price (Transformer) ───────────────────────────────
        self.tech_transformer = BranchTransformer(
            tech_input_dim, hidden_dim,
            num_transformer_layers, num_attn_heads, transformer_ff_dim, dropout,
        )
        self.tech_attn = SelfAttentionPooling(hidden_dim, num_attn_heads, dropout)
        tech_out = hidden_dim * 2   # mean + last

        # ── Branch 2: Sentiment (Transformer) ────────────────────────────────
        sent_ff = transformer_ff_dim // 2
        self.sent_transformer = BranchTransformer(
            sent_input_dim, sent_dim,
            num_transformer_layers, num_attn_heads, sent_ff, dropout,
        )
        sent_out = sent_dim   # mean pool

        # ── Cross-attention: tech queries sentiment ───────────────────────────
        self.sent_proj = nn.Linear(sent_dim, hidden_dim)  # project sent to tech dim
        self.cross_attn = CrossAttention(hidden_dim, num_attn_heads, dropout)
        cross_out = hidden_dim

        # ── Branch 3: Macro (Transformer) ────────────────────────────────────
        macro_ff = transformer_ff_dim // 2
        self.macro_transformer = BranchTransformer(
            macro_input_dim, macro_dim,
            num_transformer_layers, num_attn_heads, macro_ff, dropout,
        )
        macro_out = macro_dim   # mean pool

        # ── Branch 4: Fundamentals (MLP, static features) ────────────────────
        fund_hidden = 128
        fund_out = 64
        if fund_input_dim > 0:
            self.fund_mlp = nn.Sequential(
                nn.Linear(fund_input_dim, fund_hidden),
                nn.LayerNorm(fund_hidden),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(fund_hidden, fund_out),
                nn.LayerNorm(fund_out),
                nn.GELU(),
            )
        else:
            self.fund_mlp = None
            fund_out = 0

        # ── Branch 5 & 6: Identity Embeddings ────────────────────────────────
        self.sym_embed = nn.Embedding(n_symbols + 1, company_embedding_dim, padding_idx=0)
        self.sym_dropout = nn.Dropout(dropout)
        self.sec_embed = nn.Embedding(n_sectors + 1, sector_embedding_dim, padding_idx=0)

        # ── Regime embedding ──────────────────────────────────────────────────
        self.regime_embed = nn.Embedding(NUM_REGIMES + 1, regime_embedding_dim, padding_idx=0)

        # ── Temperature scalar (for post-hoc calibration) ─────────────────────
        self.temperature = nn.Parameter(torch.ones(1), requires_grad=False)

        # ── MLP head ──────────────────────────────────────────────────────────
        total_dim = (
            tech_out + sent_out + cross_out + macro_out + fund_out
            + company_embedding_dim + sector_embedding_dim + regime_embedding_dim
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
        fund: torch.Tensor,         # (B, fund_dim) — static fundamentals
        sym_idx: torch.Tensor,      # (B,) long
        sec_idx: torch.Tensor,      # (B,) long
        regime_idx: torch.Tensor,   # (B,) long  0=unknown,1=bull,2=bear,3=sideways,4=crisis
    ) -> torch.Tensor:

        # ── Tech branch: Transformer -> self-attention -> mean+last concat ────
        tech_seq = self.tech_transformer(tech)             # (B, T, H)
        tech_mean, tech_last = self.tech_attn(tech_seq)
        tech_feat = torch.cat([tech_mean, tech_last], dim=-1)  # (B, H*2)

        # ── Sentiment branch: Transformer -> mean pool ────────────────────────
        sent_seq = self.sent_transformer(sent)             # (B, T, H//2)
        sent_feat = sent_seq.mean(dim=1)                   # (B, H//2)

        # ── Cross-attention: tech queries projected sentiment ─────────────────
        sent_proj = self.sent_proj(sent_seq)               # (B, T, H)
        cross_feat = self.cross_attn(tech_seq, sent_proj)  # (B, H)

        # ── Macro branch: Transformer -> mean pool ────────────────────────────
        macro_seq = self.macro_transformer(macro)          # (B, T, macro_H)
        macro_feat = macro_seq.mean(dim=1)                 # (B, macro_H)

        # ── Fundamentals branch: MLP ──────────────────────────────────────────
        if self.fund_mlp is not None:
            fund_feat = self.fund_mlp(fund)                # (B, 64)
            parts = [tech_feat, sent_feat, cross_feat, macro_feat, fund_feat]
        else:
            parts = [tech_feat, sent_feat, cross_feat, macro_feat]

        # ── Identity + regime embeddings ──────────────────────────────────────
        sym_feat = self.sym_dropout(self.sym_embed(sym_idx))
        sec_feat = self.sec_embed(sec_idx)
        reg_feat = self.regime_embed(regime_idx)

        # ── Concat + classify ─────────────────────────────────────────────────
        combined = torch.cat(parts + [sym_feat, sec_feat, reg_feat], dim=-1)
        return self.classifier(combined)

    def predict_with_uncertainty(
        self,
        tech, sent, macro, fund, sym_idx, sec_idx, regime_idx,
        n_samples: int = 50,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        MC Dropout inference with temperature scaling.
        Returns (mean_probs, uncertainty) both (B, C).
        uncertainty = normalised predictive entropy [0, 1].
        """
        self.train()  # keep dropout active
        all_probs = []
        with torch.no_grad():
            for _ in range(n_samples):
                logits = self(tech, sent, macro, fund, sym_idx, sec_idx, regime_idx)
                # Apply temperature scaling at inference
                scaled = logits / self.temperature.clamp(min=0.1)
                all_probs.append(torch.softmax(scaled, dim=-1).unsqueeze(0))

        all_probs = torch.cat(all_probs, dim=0)    # (n_samples, B, C)
        mean_probs = all_probs.mean(dim=0)          # (B, C)
        entropy = -(mean_probs * (mean_probs + 1e-9).log()).sum(dim=-1)
        max_entropy = torch.log(torch.tensor(float(mean_probs.shape[-1])))
        uncertainty = entropy / max_entropy
        self.eval()
        return mean_probs, uncertainty


# ── Deep Ensemble ─────────────────────────────────────────────────────────────

class EnsembleModel(nn.Module):
    """
    Deep Ensemble of N independently trained UltraTradingModels.
    Averages probabilities across all members for better calibration.
    """

    def __init__(self, models: List[UltraTradingModel]):
        super().__init__()
        self.members = nn.ModuleList(models)

    def predict(
        self, tech, sent, macro, fund, sym_idx, sec_idx, regime_idx,
        mc_samples: int = 10,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Average MC Dropout predictions across all ensemble members."""
        all_probs = []
        for member in self.members:
            probs, _ = member.predict_with_uncertainty(
                tech, sent, macro, fund, sym_idx, sec_idx, regime_idx,
                n_samples=mc_samples,
            )
            all_probs.append(probs.unsqueeze(0))

        stacked = torch.cat(all_probs, dim=0)   # (N, B, C)
        mean_probs = stacked.mean(dim=0)         # (B, C)
        entropy = -(mean_probs * (mean_probs + 1e-9).log()).sum(dim=-1)
        max_entropy = torch.log(torch.tensor(float(mean_probs.shape[-1])))
        uncertainty = entropy / max_entropy
        return mean_probs, uncertainty


# ── Factory ───────────────────────────────────────────────────────────────────

def build_model(
    cfg,
    n_symbols: int,
    n_sectors: int,
    tech_dim: int,
    sent_dim: int,
    macro_dim: int,
    fund_dim: int = 6,
) -> UltraTradingModel:
    """Build model from config."""
    m = cfg.model
    return UltraTradingModel(
        tech_input_dim=tech_dim,
        sent_input_dim=sent_dim,
        macro_input_dim=macro_dim,
        fund_input_dim=fund_dim,
        n_symbols=n_symbols,
        n_sectors=n_sectors,
        hidden_dim=getattr(m, "hidden_dim", 256),
        num_transformer_layers=getattr(m, "num_transformer_layers", 4),
        num_attn_heads=getattr(m, "num_attn_heads", 8),
        transformer_ff_dim=getattr(m, "transformer_ff_dim", 1024),
        company_embedding_dim=getattr(m, "company_embedding_dim", 16),
        sector_embedding_dim=getattr(m, "sector_embedding_dim", 8),
        macro_hidden_dim=getattr(m, "macro_hidden_dim", 128),
        final_hidden_dims=tuple(getattr(m, "final_hidden_dims", [512, 256, 128])),
        dropout=getattr(m, "dropout", 0.25),
        num_classes=getattr(m, "num_classes", 5),
        regime_embedding_dim=getattr(m, "regime_embedding_dim", 8),
    )
