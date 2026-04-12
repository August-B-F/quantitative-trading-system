"""Post-hoc temperature scaling calibration for UltraTradingModel.

Reference: Guo et al. (2017) "On Calibration of Modern Neural Networks"
https://arxiv.org/abs/1706.04599

Usage:
    scaler = TemperatureScaler()
    optimal_temp = scaler.fit(model, val_loader, device)
    scaler.save(model, "data/models/temperature.pt")

    # Later:
    scaler.load(model, "data/models/temperature.pt")
"""
import torch
import torch.nn as nn
from typing import TYPE_CHECKING
from ultimate_trader.utils.logging import get_logger

if TYPE_CHECKING:
    from ultimate_trader.modeling.model import UltraTradingModel

logger = get_logger(__name__)


class TemperatureScaler:
    """
    Post-hoc temperature scaling calibration.

    Freezes model weights and optimises the single temperature scalar
    on the validation set using NLL loss via L-BFGS optimiser.

    The model's self.temperature parameter is updated in-place.
    """

    def fit(
        self,
        model: "UltraTradingModel",
        val_loader,
        device: torch.device,
    ) -> float:
        """
        Optimise model.temperature using NLL on the validation set.
        Returns the optimal temperature found.
        """
        model.eval()

        # Collect all logits and labels (without temperature applied)
        all_logits, all_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                # batch = (tech, sent, macro, fund, sym_idx, sec_idx, regime_idx, labels)
                # or legacy (tech, sent, macro, sym_idx, sec_idx, regime_idx, labels)
                if len(batch) == 8:
                    tech, sent, macro, fund, sym_idx, sec_idx, regime_idx, labels = batch
                else:
                    tech, sent, macro, sym_idx, sec_idx, regime_idx, labels = batch
                    fund = torch.zeros(tech.size(0), 6)

                tech = tech.to(device)
                sent = sent.to(device)
                macro = macro.to(device)
                fund = fund.to(device)
                sym_idx = sym_idx.to(device)
                sec_idx = sec_idx.to(device)
                regime_idx = regime_idx.to(device)

                # Forward without temperature: temporarily set temp=1
                orig_temp = model.temperature.data.clone()
                model.temperature.data.fill_(1.0)
                logits = model(tech, sent, macro, fund, sym_idx, sec_idx, regime_idx)
                model.temperature.data.copy_(orig_temp)

                all_logits.append(logits.cpu())
                all_labels.append(labels.cpu())

        all_logits = torch.cat(all_logits, dim=0)
        all_labels = torch.cat(all_labels, dim=0)

        # Optimise temperature on CPU (avoids device mismatch)
        temperature = model.temperature.cpu().detach().clone().requires_grad_(True)
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.LBFGS([temperature], lr=0.01, max_iter=200,
                                       tolerance_grad=1e-7, tolerance_change=1e-9)

        def eval_fn():
            optimizer.zero_grad()
            scaled = all_logits / temperature.clamp(min=0.05)
            loss = criterion(scaled, all_labels)
            loss.backward()
            return loss

        try:
            optimizer.step(eval_fn)
        except Exception as e:
            logger.warning(f"Temperature optimisation failed: {e}")
            return 1.0

        optimal_temp = float(temperature.detach().clamp(min=0.05).item())
        optimal_temp = max(0.1, min(optimal_temp, 10.0))  # sanity clamp

        # Write back to model
        with torch.no_grad():
            model.temperature.fill_(optimal_temp)

        # Log calibration quality
        before_nll = criterion(all_logits, all_labels).item()
        after_nll = criterion(all_logits / optimal_temp, all_labels).item()
        logger.info(
            f"Temperature calibration: T={optimal_temp:.4f} | "
            f"NLL before={before_nll:.4f}, after={after_nll:.4f}"
        )
        return optimal_temp

    def save(self, model: "UltraTradingModel", path: str):
        """Save the calibrated temperature to disk."""
        torch.save({"temperature": model.temperature.data.clone()}, path)
        logger.info(f"Temperature saved to {path}")

    def load(self, model: "UltraTradingModel", path: str):
        """Load a saved temperature into the model."""
        data = torch.load(path, map_location="cpu")
        with torch.no_grad():
            model.temperature.copy_(data["temperature"])
        logger.info(
            f"Temperature loaded from {path}: T={model.temperature.item():.4f}"
        )
