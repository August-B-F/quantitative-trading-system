"""
losses.py

Custom loss functions for training.

1. WeightedCrossEntropy  : handles severe class imbalance (hold >> buys/sells)
2. OrdinalCrossEntropy   : penalizes predicting strong_buy when true = strong_sell
                           more than predicting buy when true = strong_sell.
                           Respects the ordinal nature of the labels.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional


class WeightedCrossEntropy(nn.Module):
    """
    Standard cross entropy with class weights computed from label frequency.
    Pass class_weights=None to use inverse-frequency weighting automatically.
    """

    def __init__(self, class_weights: Optional[torch.Tensor] = None, num_classes: int = 5):
        super().__init__()
        self.num_classes = num_classes
        self.register_buffer("class_weights", class_weights)

    @classmethod
    def from_labels(cls, labels: np.ndarray, num_classes: int = 5) -> "WeightedCrossEntropy":
        counts = np.bincount(labels, minlength=num_classes).astype(float)
        weights = 1.0 / (counts + 1e-6)
        weights /= weights.sum()
        weights = torch.tensor(weights * num_classes, dtype=torch.float32)
        return cls(class_weights=weights, num_classes=num_classes)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return F.cross_entropy(logits, targets, weight=self.class_weights)


class OrdinalCrossEntropy(nn.Module):
    """
    Cross entropy + ordinal penalty.
    The further a wrong prediction is from the truth on the ordinal scale,
    the higher the penalty.

    Loss = CE + lambda * |pred_class - true_class|^2 (normalized)
    """

    def __init__(self, num_classes: int = 5, ordinal_lambda: float = 0.5,
                 class_weights: Optional[torch.Tensor] = None):
        super().__init__()
        self.num_classes = num_classes
        self.ordinal_lambda = ordinal_lambda
        self.register_buffer("class_weights", class_weights)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, weight=self.class_weights)

        probs = F.softmax(logits, dim=-1)
        class_values = torch.arange(self.num_classes, dtype=torch.float32, device=logits.device)
        expected_class = (probs * class_values).sum(dim=-1)  # (B,)
        ordinal_penalty = ((expected_class - targets.float()) ** 2).mean()
        ordinal_penalty /= (self.num_classes - 1) ** 2  # normalize

        return ce_loss + self.ordinal_lambda * ordinal_penalty
