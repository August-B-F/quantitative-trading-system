"""Loss functions for training."""
import torch
import torch.nn as nn
import numpy as np


def compute_class_weights(labels: np.ndarray, num_classes: int = 5) -> torch.Tensor:
    """Inverse-frequency class weights to handle imbalance."""
    counts = np.bincount(labels, minlength=num_classes).astype(float)
    counts = np.where(counts == 0, 1, counts)  # avoid division by zero
    weights = 1.0 / counts
    weights = weights / weights.sum() * num_classes  # normalise
    return torch.tensor(weights, dtype=torch.float32)


class LabelSmoothingCrossEntropy(nn.Module):
    """Cross-entropy with label smoothing to prevent overconfidence."""
    def __init__(self, num_classes: int = 5, smoothing: float = 0.1,
                 weight: torch.Tensor | None = None):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probs = torch.log_softmax(logits, dim=-1)
        smooth_targets = torch.full_like(log_probs, self.smoothing / (self.num_classes - 1))
        smooth_targets.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)

        loss = (-smooth_targets * log_probs).sum(dim=-1)
        if self.weight is not None:
            w = self.weight.to(logits.device)[targets]
            loss = loss * w
        return loss.mean()
