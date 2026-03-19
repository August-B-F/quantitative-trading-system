"""Custom loss functions for training."""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class WeightedFocalLoss(nn.Module):
    """
    Focal Loss with per-class weights.

    Focal Loss down-weights easy examples and focuses training on hard,
    misclassified examples.  Especially useful for imbalanced class distributions
    (which is typical: most days are 'hold').

    L_focal = -alpha_t * (1 - p_t)^gamma * log(p_t)

    Args:
        class_weights: 1D tensor of per-class weights (inverse frequency)
        gamma: focusing parameter (0 = standard CE, 2 is typical)
    """

    def __init__(self, class_weights: torch.Tensor = None, gamma: float = 2.0):
        super().__init__()
        self.gamma = gamma
        self.register_buffer("class_weights", class_weights)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # logits: (B, C), targets: (B,)
        log_probs = F.log_softmax(logits, dim=-1)
        probs = log_probs.exp()
        
        # Gather p_t for true class
        p_t = probs.gather(1, targets.unsqueeze(1)).squeeze(1)
        log_p_t = log_probs.gather(1, targets.unsqueeze(1)).squeeze(1)

        focal_weight = (1.0 - p_t) ** self.gamma

        if self.class_weights is not None:
            alpha_t = self.class_weights[targets]
            loss = -alpha_t * focal_weight * log_p_t
        else:
            loss = -focal_weight * log_p_t

        return loss.mean()


def compute_class_weights(labels: np.ndarray, num_classes: int = 5) -> torch.Tensor:
    """
    Compute inverse-frequency class weights from label array.
    Returns a FloatTensor of shape (num_classes,).
    """
    counts = np.bincount(labels, minlength=num_classes).astype(np.float32)
    counts = np.where(counts == 0, 1, counts)  # avoid div by zero
    weights = 1.0 / counts
    weights = weights / weights.sum() * num_classes  # normalise to sum = num_classes
    return torch.tensor(weights, dtype=torch.float32)
