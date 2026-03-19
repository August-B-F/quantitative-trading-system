import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_config() -> dict:
    cfg = _load_yaml(_ROOT / "config" / "config.yaml")
    model_cfg = _load_yaml(_ROOT / "config" / "model.yaml")
    training_cfg = _load_yaml(_ROOT / "config" / "training.yaml")

    # Inject secrets from environment (never hard-code keys)
    cfg["alpaca"]["key_id"] = os.getenv("ALPACA_KEY", cfg["alpaca"].get("key_id", ""))
    cfg["alpaca"]["secret_key"] = os.getenv("ALPACA_SECRET", cfg["alpaca"].get("secret_key", ""))

    live = os.getenv("ALPACA_LIVE", "false").lower() == "true"
    if live:
        cfg["alpaca"]["base_url"] = "https://api.alpaca.markets"
    cfg["trading"]["live"] = live

    cfg["model"] = model_cfg["model"]
    cfg["targets"] = model_cfg["targets"]
    cfg["uncertainty"] = model_cfg["uncertainty"]
    cfg["training"] = training_cfg["training"]
    cfg["walk_forward"] = training_cfg["walk_forward"]
    cfg["hyperparam_search"] = training_cfg["hyperparam_search"]

    # Resolve absolute paths
    for key, rel in cfg["paths"].items():
        cfg["paths"][key] = str(_ROOT / rel)

    return cfg
