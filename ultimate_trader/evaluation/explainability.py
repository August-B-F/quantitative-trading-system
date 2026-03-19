"""SHAP-based feature importance analysis for the trading model."""
import numpy as np
import torch
from pathlib import Path
from typing import Optional
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)


def explain_model(
    model,
    sample_price_seqs:     np.ndarray,
    sample_sent_seqs:      np.ndarray,
    sample_macro_seqs:     np.ndarray,
    sample_company_ids:    np.ndarray,
    price_feature_names:   list,
    sent_feature_names:    list,
    macro_feature_names:   list,
    output_dir:            str = "data/explainability",
    n_background_samples:  int = 100,
    n_explain_samples:     int = 50,
    device:                str = "cpu",
):
    """
    Compute SHAP values for the flattened price, sentiment, and macro inputs.
    Saves a CSV of mean absolute SHAP per feature to output_dir.
    Requires shap >= 0.44 installed.

    Returns: dict of feature_name -> mean_abs_shap
    """
    try:
        import shap
    except ImportError:
        log.warning("shap not installed. Skipping explainability analysis.")
        return {}

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # flatten the 3D inputs to 2D for SHAP DeepExplainer
    B = sample_price_seqs.shape[0]
    price_flat = sample_price_seqs.reshape(B, -1)
    sent_flat  = sample_sent_seqs.reshape(B, -1)
    macro_flat = sample_macro_seqs.reshape(B, -1)
    combined   = np.concatenate([price_flat, sent_flat, macro_flat], axis=1)

    # build feature names
    Tp = sample_price_seqs.shape[1]
    Ts = sample_sent_seqs.shape[1]
    Tm = sample_macro_seqs.shape[1]
    feat_names = (
        [f"price_t{-Tp+i}_{n}" for i in range(Tp) for n in price_feature_names] +
        [f"sent_t{-Ts+i}_{n}"  for i in range(Ts) for n in sent_feature_names] +
        [f"macro_t{-Tm+i}_{n}" for i in range(Tm) for n in macro_feature_names]
    )

    model.eval()
    model.to(device)

    # wrapper to take flat input and return logits for class 3+4 (bullish)
    def model_fn(x_flat):
        x = torch.tensor(x_flat, dtype=torch.float32, device=device)
        p = x[:, :Tp * len(price_feature_names)].reshape(-1, Tp, len(price_feature_names))
        s = x[:, Tp*len(price_feature_names): Tp*len(price_feature_names) + Ts*len(sent_feature_names)]
        s = s.reshape(-1, Ts, len(sent_feature_names))
        m = x[:, -Tm*len(macro_feature_names):].reshape(-1, Tm, len(macro_feature_names))
        cids = torch.zeros(x.shape[0], dtype=torch.long, device=device)
        with torch.no_grad():
            logits = model(p, s, m, cids)
            probs = torch.softmax(logits, dim=-1)
        # return bullish probability (class 3 + 4)
        return (probs[:, 3] + probs[:, 4]).unsqueeze(1).cpu().numpy()

    background = combined[:n_background_samples]
    explainer  = shap.KernelExplainer(model_fn, background)
    shap_values = explainer.shap_values(combined[:n_explain_samples], nsamples=100)

    mean_abs_shap = np.abs(shap_values).mean(axis=0).flatten()

    import pandas as pd
    df = pd.DataFrame({
        "feature":       feat_names[:len(mean_abs_shap)],
        "mean_abs_shap": mean_abs_shap,
    }).sort_values("mean_abs_shap", ascending=False)

    out_path = Path(output_dir) / "feature_importance.csv"
    df.to_csv(out_path, index=False)
    log.info(f"Feature importance saved to {out_path}")

    # log top 20
    log.info("Top 20 features by SHAP:\n" + df.head(20).to_string(index=False))
    return dict(zip(df["feature"], df["mean_abs_shap"]))
