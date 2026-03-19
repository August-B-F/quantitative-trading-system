"""Loss functions for multi-class trading prediction."""
import torch
import torch.nn as nn
import numpy as np
from typing import List


def compute_class_weights(labels: List[int], num_classes: int = 5) -> torch.Tensor:
    """
    Compute inverse-frequency class weights to handle class imbalance.
    'Hold' is typically dominant; buy/sell signals are rare.
    """
    counts = np.bincount(labels, minlength=num_classes).astype(float)
    counts = np.maximum(counts, 1)  # avoid zero
    weights = 1.0 / counts
    weights = weights / weights.sum() * num_classes  # normalize
    return torch.tensor(weights, dtype=torch.float32)


class FocalLoss(nn.Module):
    """
    Focal loss: down-weights easy examples (the common 'hold' class)
    and focuses training on hard rare examples (buy/sell signals).
    gamma=2 is a common default.
    """

    def __init__(self, gamma: float = 2.0, weight: torch.Tensor = None):
        super().__init__()
        self.gamma = gamma
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = nn.functional.cross_entropy(logits, targets,
                                          weight=self.weight, reduction="none")
        pt = torch.exp(-ce)
        focal = ((1 - pt) ** self.gamma) * ce
        return focal.mean()


class LabelSmoothingLoss(nn.Module):
    """Cross-entropy with label smoothing to prevent overconfident predictions."""

    def __init__(self, smoothing: float = 0.1, num_classes: int = 5,
                 weight: torch.Tensor = None):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probs = nn.functional.log_softmax(logits, dim=-1)
        # Hard label cross-entropy
        nll = nn.functional.nll_loss(log_probs, targets, weight=self.weight)
        # Uniform smoothing
        smooth = -log_probs.mean(dim=-1).mean()
        return (1 - self.smoothing) * nll + self.smoothing * smooth
