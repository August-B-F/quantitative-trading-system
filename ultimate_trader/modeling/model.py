"""Multi-branch LSTM + Attention PyTorch model for stock direction classification."""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class TemporalAttention(nn.Module):
    """Scaled dot-product self-attention over a time sequence."""

    def __init__(self, hidden_dim: int, num_heads: int = 4):
        super().__init__()
        self.attn = nn.MultiheadAttention(hidden_dim, num_heads,
                                          dropout=0.1, batch_first=True)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, T, hidden_dim) -> (B, T, hidden_dim)"""
        out, _ = self.attn(x, x, x)
        return self.norm(x + out)


class LSTMBranch(nn.Module):
    """Bi-LSTM branch with attention pooling for a single time-series input."""

    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int,
                 dropout: float, num_heads: int = 4, use_attention: bool = True):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
            bidirectional=True,
        )
        out_dim = hidden_dim * 2  # bidirectional
        self.use_attention = use_attention
        if use_attention:
            self.attention = TemporalAttention(out_dim, num_heads)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, T, input_dim) -> (B, hidden_dim*2)"""
        out, _ = self.lstm(x)  # (B, T, hidden_dim*2)
        if self.use_attention:
            out = self.attention(out)  # (B, T, hidden_dim*2)
        # mean pooling over time
        pooled = out.mean(dim=1)  # (B, hidden_dim*2)
        return self.dropout(pooled)


class UltraTradingModel(nn.Module):
    """
    Multi-branch model for stock direction classification.

    Inputs:
        price_seq     : (B, price_window,     n_price_feats)
        sentiment_seq : (B, sentiment_window, n_sent_feats)
        macro_seq     : (B, macro_window,     n_macro_feats)
        company_id    : (B,)  int64 - company index for embedding

    Output:
        logits        : (B, num_classes)  -- use softmax for probs
    """

    def __init__(
        self,
        n_price_feats:   int,
        n_sent_feats:    int,
        n_macro_feats:   int,
        num_companies:   int,
        num_classes:     int   = 5,
        price_hidden:    int   = 128,
        price_layers:    int   = 2,
        sent_hidden:     int   = 64,
        sent_layers:     int   = 1,
        macro_hidden:    int   = 64,
        fusion_hidden:   int   = 256,
        fusion_layers:   int   = 3,
        company_emb_dim: int   = 16,
        sector_emb_dim:  int   = 8,
        num_sectors:     int   = 11,
        dropout:         float = 0.3,
        num_heads:       int   = 4,
        use_attention:   bool  = True,
    ):
        super().__init__()

        # branch 1: price + technicals
        self.price_branch = LSTMBranch(
            input_dim=n_price_feats, hidden_dim=price_hidden,
            num_layers=price_layers, dropout=dropout,
            num_heads=num_heads, use_attention=use_attention
        )
        price_out = price_hidden * 2

        # branch 2: sentiment
        self.sent_branch = LSTMBranch(
            input_dim=n_sent_feats, hidden_dim=sent_hidden,
            num_layers=sent_layers, dropout=dropout,
            num_heads=num_heads, use_attention=use_attention
        )
        sent_out = sent_hidden * 2

        # branch 3: macro
        self.macro_branch = LSTMBranch(
            input_dim=n_macro_feats, hidden_dim=macro_hidden,
            num_layers=1, dropout=dropout,
            num_heads=num_heads, use_attention=use_attention
        )
        macro_out = macro_hidden * 2

        # company + sector embeddings
        self.company_emb = nn.Embedding(num_companies, company_emb_dim)
        self.sector_emb  = nn.Embedding(num_sectors, sector_emb_dim)

        # fusion MLP
        fuse_in = price_out + sent_out + macro_out + company_emb_dim + sector_emb_dim
        layers = []
        in_dim = fuse_in
        for _ in range(fusion_layers):
            layers += [
                nn.Linear(in_dim, fusion_hidden),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.LayerNorm(fusion_hidden),
            ]
            in_dim = fusion_hidden
        layers.append(nn.Linear(fusion_hidden, num_classes))
        self.fusion = nn.Sequential(*layers)

    def forward(
        self,
        price_seq:     torch.Tensor,
        sentiment_seq: torch.Tensor,
        macro_seq:     torch.Tensor,
        company_id:    torch.Tensor,
        sector_id:     Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        p = self.price_branch(price_seq)
        s = self.sent_branch(sentiment_seq)
        m = self.macro_branch(macro_seq)
        c = self.company_emb(company_id)
        if sector_id is None:
            sector_id = torch.zeros(company_id.shape, dtype=torch.long,
                                    device=company_id.device)
        sec = self.sector_emb(sector_id)
        fused = torch.cat([p, s, m, c, sec], dim=-1)
        return self.fusion(fused)

    @torch.no_grad()
    def predict_with_uncertainty(
        self,
        price_seq:     torch.Tensor,
        sentiment_seq: torch.Tensor,
        macro_seq:     torch.Tensor,
        company_id:    torch.Tensor,
        sector_id:     Optional[torch.Tensor] = None,
        n_samples:     int = 50,
    ) -> dict:
        """
        MC Dropout uncertainty estimation.
        MUST call model.train() before this to activate dropout.
        Returns:
            mean_probs   : (B, num_classes) - mean softmax probabilities
            uncertainty  : (B,)             - predictive entropy
            pred_class   : (B,)             - argmax of mean probs
        """
        self.train()  # enable dropout
        all_probs = []
        for _ in range(n_samples):
            logits = self(price_seq, sentiment_seq, macro_seq, company_id, sector_id)
            probs = F.softmax(logits, dim=-1)  # (B, C)
            all_probs.append(probs.unsqueeze(0))
        self.eval()  # disable after sampling

        stacked   = torch.cat(all_probs, dim=0)  # (n_samples, B, C)
        mean_probs = stacked.mean(dim=0)          # (B, C)

        # predictive entropy as uncertainty measure
        eps = 1e-8
        entropy = -(mean_probs * (mean_probs + eps).log()).sum(dim=-1)  # (B,)

        return {
            "mean_probs":  mean_probs.cpu(),
            "uncertainty": entropy.cpu(),
            "pred_class":  mean_probs.argmax(dim=-1).cpu(),
        }
