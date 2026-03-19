"""Multi-branch PyTorch model for stock direction prediction.

Architecture:
  Branch 1 (price/technicals): Bidirectional LSTM + self-attention
  Branch 2 (sentiment):        Bidirectional LSTM
  Branch 3 (macro/regime):     Transformer encoder
  Company embedding:           nn.Embedding(num_symbols, embed_dim)
  Fusion:                      Concatenate -> MLP -> 5-class softmax

MC Dropout is correctly implemented: Dropout layers remain ACTIVE
during inference when called with model.train() context.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class SelfAttention(nn.Module):
    """Lightweight single-head self-attention over a sequence."""

    def __init__(self, hidden_dim: int):
        super().__init__()
        self.query = nn.Linear(hidden_dim, hidden_dim)
        self.key = nn.Linear(hidden_dim, hidden_dim)
        self.value = nn.Linear(hidden_dim, hidden_dim)
        self.scale = hidden_dim ** 0.5

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, H)
        Q = self.query(x)
        K = self.key(x)
        V = self.value(x)
        attn = torch.softmax(Q @ K.transpose(-2, -1) / self.scale, dim=-1)
        return (attn @ V).mean(dim=1)  # (B, H) — mean-pool attended output


class LSTMBranch(nn.Module):
    """Bidirectional LSTM with optional self-attention pooling."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        num_layers: int,
        dropout: float,
        use_attention: bool = True,
    ):
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
        self.use_attention = use_attention
        if use_attention:
            self.attention = SelfAttention(hidden_dim * 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, input_dim)
        out, _ = self.lstm(x)  # (B, T, hidden_dim*2)
        out = self.dropout(out)
        if self.use_attention:
            return self.attention(out)  # (B, hidden_dim*2)
        return out[:, -1, :]  # (B, hidden_dim*2) last timestep


class TransformerBranch(nn.Module):
    """Small Transformer encoder for macro features."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        num_heads: int,
        num_layers: int,
        dropout: float,
    ):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 2,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, input_dim)
        x = self.input_proj(x)  # (B, T, hidden_dim)
        x = self.encoder(x)     # (B, T, hidden_dim)
        return self.dropout(x.mean(dim=1))  # (B, hidden_dim)


class MultibranchPredictor(nn.Module):
    """
    Full multi-branch stock predictor.

    Inputs (all as tensors on the same device):
        x_price:  (B, price_window, n_price_features)
        x_sent:   (B, sent_window, n_sent_features)
        x_macro:  (B, macro_window, n_macro_features)
        sym_idx:  (B,) LongTensor of symbol indices

    Output:
        logits:   (B, num_classes)  — raw class logits
    """

    def __init__(
        self,
        n_price_features: int,
        n_sent_features: int,
        n_macro_features: int,
        num_symbols: int,
        num_classes: int = 5,
        hidden_dim: int = 128,
        num_lstm_layers: int = 2,
        num_transformer_heads: int = 4,
        num_transformer_layers: int = 2,
        dropout: float = 0.3,
        company_embedding_dim: int = 16,
        mlp_hidden_dims: list = None,
    ):
        super().__init__()

        if mlp_hidden_dims is None:
            mlp_hidden_dims = [256, 128, 64]

        # Branch 1: Price + technicals
        self.price_branch = LSTMBranch(
            input_dim=n_price_features,
            hidden_dim=hidden_dim,
            num_layers=num_lstm_layers,
            dropout=dropout,
            use_attention=True,
        )

        # Branch 2: Sentiment
        self.sent_branch = LSTMBranch(
            input_dim=n_sent_features,
            hidden_dim=hidden_dim // 2,
            num_layers=num_lstm_layers,
            dropout=dropout,
            use_attention=False,
        )

        # Branch 3: Macro / regime (Transformer)
        self.macro_branch = TransformerBranch(
            input_dim=n_macro_features,
            hidden_dim=hidden_dim // 2,
            num_heads=min(num_transformer_heads, hidden_dim // 2),
            num_layers=num_transformer_layers,
            dropout=dropout,
        )

        # Company embedding
        self.company_embedding = nn.Embedding(num_symbols + 1, company_embedding_dim, padding_idx=0)

        # Fusion MLP
        fusion_in = (
            hidden_dim * 2  # BiLSTM price
            + hidden_dim     # BiLSTM sent (hidden//2 * 2)
            + hidden_dim // 2  # Transformer macro
            + company_embedding_dim
        )
        layers = []
        prev = fusion_in
        for hdim in mlp_hidden_dims:
            layers += [nn.Linear(prev, hdim), nn.GELU(), nn.Dropout(dropout)]
            prev = hdim
        layers += [nn.Linear(prev, num_classes)]
        self.fusion = nn.Sequential(*layers)

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
        x_price: torch.Tensor,
        x_sent: torch.Tensor,
        x_macro: torch.Tensor,
        sym_idx: torch.Tensor,
    ) -> torch.Tensor:
        p = self.price_branch(x_price)          # (B, hidden_dim*2)
        s = self.sent_branch(x_sent)            # (B, hidden_dim)
        m = self.macro_branch(x_macro)          # (B, hidden_dim//2)
        e = self.company_embedding(sym_idx)     # (B, embed_dim)
        fused = torch.cat([p, s, m, e], dim=1)  # (B, fusion_in)
        return self.fusion(fused)               # (B, num_classes)


@torch.no_grad()
def mc_predict(
    model: nn.Module,
    x_price: torch.Tensor,
    x_sent: torch.Tensor,
    x_macro: torch.Tensor,
    sym_idx: torch.Tensor,
    n_samples: int = 50,
) -> dict:
    """
    Monte Carlo Dropout inference. Runs the model n_samples times with
    Dropout ACTIVE (model.train() mode) to sample the predictive distribution.

    Args:
        model: MultibranchPredictor
        x_price, x_sent, x_macro, sym_idx: input tensors (already on device)
        n_samples: number of stochastic forward passes

    Returns:
        dict with:
            mean_probs:  (B, num_classes) mean probabilities
            std_probs:   (B, num_classes) std of probabilities
            pred_class:  (B,) argmax of mean_probs
            uncertainty: (B,) predictive entropy H = -sum(p * log p)
            confidence:  (B,) 1 - normalised_entropy
    """
    model.train()  # CRITICAL: keep Dropout active
    all_probs = []
    for _ in range(n_samples):
        logits = model(x_price, x_sent, x_macro, sym_idx)
        probs = F.softmax(logits, dim=-1)   # (B, C)
        all_probs.append(probs.unsqueeze(0))  # (1, B, C)
    model.eval()

    stacked = torch.cat(all_probs, dim=0)  # (n_samples, B, C)
    mean_probs = stacked.mean(dim=0)       # (B, C)
    std_probs = stacked.std(dim=0)         # (B, C)
    pred_class = mean_probs.argmax(dim=1)  # (B,)

    # Predictive entropy
    eps = 1e-9
    entropy = -(mean_probs * (mean_probs + eps).log()).sum(dim=1)  # (B,)
    max_entropy = torch.log(torch.tensor(mean_probs.shape[1], dtype=torch.float))
    confidence = 1.0 - entropy / max_entropy  # (B,) in [0, 1]

    return {
        "mean_probs": mean_probs.cpu(),
        "std_probs": std_probs.cpu(),
        "pred_class": pred_class.cpu(),
        "uncertainty": entropy.cpu(),
        "confidence": confidence.cpu(),
    }
