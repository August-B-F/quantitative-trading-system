"""Loss functions for training."""
import torch
import torch.nn as nn
import torch.nn.functional as F


class LabelSmoothingCrossEntropy(nn.Module):
    """Cross-entropy with label smoothing to prevent overconfidence."""
    def __init__(self, smoothing: float = 0.05, weight: torch.Tensor = None):
        super().__init__()
        self.smoothing = smoothing
        self.weight = weight

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        n_classes = logits.size(-1)
        log_prob = F.log_softmax(logits, dim=-1)
        smooth_target = torch.full_like(log_prob, self.smoothing / (n_classes - 1))
        smooth_target.scatter_(1, target.unsqueeze(1), 1.0 - self.smoothing)
        if self.weight is not None:
            w = self.weight[target].unsqueeze(1).to(logits.device)
            loss = -(smooth_target * log_prob * w).sum(dim=-1)
        else:
            loss = -(smooth_target * log_prob).sum(dim=-1)
        return loss.mean()


def compute_class_weights(labels, n_classes: int = 5) -> torch.Tensor:
    """Inverse-frequency class weights to handle label imbalance."""
    counts = torch.zeros(n_classes)
    for c in range(n_classes):
        counts[c] = (labels == c).sum().float()
    counts = counts.clamp(min=1)
    weights = 1.0 / counts
    return weights / weights.sum() * n_classes  # normalise
