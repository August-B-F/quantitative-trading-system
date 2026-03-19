"""Custom loss functions."""
import torch
import torch.nn as nn
import torch.nn.functional as F


class LabelSmoothingCrossEntropy(nn.Module):
    """
    Cross-entropy with label smoothing.
    Smoothing prevents overconfident predictions.
    """
    def __init__(self, smoothing: float = 0.05, num_classes: int = 5):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probs = F.log_softmax(logits, dim=-1)
        # smooth targets
        with torch.no_grad():
            smooth_targets = torch.full_like(log_probs, self.smoothing / (self.num_classes - 1))
            smooth_targets.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)
        loss = -(smooth_targets * log_probs).sum(dim=-1).mean()
        return loss


class WeightedDirectionalLoss(nn.Module):
    """
    Cross-entropy that penalises directional mistakes more than magnitude mistakes.
    e.g. predicting strong_buy when actual is strong_sell is penalised heavily.
    Classes assumed: 0=strong_sell, 1=sell, 2=hold, 3=buy, 4=strong_buy
    """
    def __init__(self, num_classes: int = 5, smoothing: float = 0.05):
        super().__init__()
        self.num_classes = num_classes
        self.smoothing = smoothing
        # directional penalty matrix: penalty[pred][true]
        penalty = torch.zeros(num_classes, num_classes)
        for i in range(num_classes):
            for j in range(num_classes):
                penalty[i][j] = abs(i - j) ** 1.5
        self.register_buffer("penalty", penalty)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probs = F.log_softmax(logits, dim=-1)
        # weighted NLL
        target_penalties = self.penalty[targets]  # (B, C)
        with torch.no_grad():
            smooth_targets = torch.full_like(log_probs, self.smoothing / (self.num_classes - 1))
            smooth_targets.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)
        loss = -(smooth_targets * log_probs * (1 + target_penalties * 0.1)).sum(dim=-1).mean()
        return loss
