"""SHAP-based feature importance analysis."""
import numpy as np
import torch
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)


def compute_shap_importances(
    model,
    sample_batch: dict,
    feature_names_price: list[str],
    feature_names_sent: list[str],
    feature_names_macro: list[str],
    n_background: int = 50,
    n_test: int = 20
) -> dict:
    """
    Use SHAP DeepExplainer to compute feature importances for the model.

    sample_batch keys: price_seq, sentiment_seq, macro_seq,
                       symbol_idx, regime (all torch tensors)

    Returns dict with:
      'price': array (n_features,) mean abs SHAP for price branch
      'sentiment': array (n_features,) for sentiment branch
      'macro': array (n_features,) for macro branch
    """
    try:
        import shap
    except ImportError:
        log.error("SHAP not installed. Run: pip install shap")
        return {}

    model.eval()

    # Wrap the model's forward in a function that takes a single concatenated tensor
    # SHAP works best on single-input models, so we explain the price branch in isolation
    bg_price = sample_batch["price_seq"][:n_background]  # (N, T, F)
    test_price = sample_batch["price_seq"][n_background:n_background + n_test]

    # Fixed other inputs (use their means as "baseline")
    bg_sent = sample_batch["sentiment_seq"][:n_background].mean(0, keepdim=True).expand(n_background, -1, -1)
    bg_macro = sample_batch["macro_seq"][:n_background].mean(0, keepdim=True).expand(n_background, -1, -1)
    bg_sym = sample_batch["symbol_idx"][:n_background]
    bg_reg = sample_batch["regime"][:n_background]

    def model_fn(price_input):
        """Forward with price branch varying, others fixed."""
        with torch.no_grad():
            inp = torch.tensor(price_input, dtype=torch.float32)
            logits = model(inp, bg_sent[:len(inp)], bg_macro[:len(inp)],
                           bg_sym[:len(inp)], bg_reg[:len(inp)])
            return torch.softmax(logits, dim=-1).numpy()

    # Flatten time x features for SHAP
    bg_flat = bg_price.numpy().reshape(n_background, -1)
    test_flat = test_price.numpy().reshape(n_test, -1)

    explainer = shap.KernelExplainer(model_fn, bg_flat)
    shap_values = explainer.shap_values(test_flat, nsamples=100)

    # shap_values is list of arrays (one per class) or single array
    if isinstance(shap_values, list):
        combined = np.abs(np.array(shap_values)).mean(axis=0)  # avg over classes
    else:
        combined = np.abs(shap_values)

    mean_abs_shap = combined.mean(axis=0)  # (T*F,)

    T = bg_price.shape[1]
    F = bg_price.shape[2]
    shap_per_feature = mean_abs_shap.reshape(T, F).mean(axis=0)  # avg over time steps

    result = {
        "price": dict(zip(feature_names_price, shap_per_feature.tolist()))
    }

    log.info("SHAP top-5 price features: " +
             str(sorted(result["price"].items(), key=lambda x: -x[1])[:5]))
    return result
