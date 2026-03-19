import yaml
from pathlib import Path
from typing import Any


def load_config(path: str) -> dict:
    """Load a YAML config file and return as dict."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_full_config() -> dict:
    """
    Load and merge all three config files into a single dict.
    Returns:
        merged config dict with keys: 'alpaca', 'universe', 'data', 'news',
        'paths', 'trading', 'model', 'targets', 'uncertainty', 'training',
        'walk_forward', 'hyperparam_search'
    """
    base = Path("config")
    cfg = {}
    for fname in ["config.yaml", "model.yaml", "training.yaml"]:
        cfg.update(load_config(base / fname))
    return cfg


def nested_get(cfg: dict, *keys: str, default: Any = None) -> Any:
    """Safely get a nested config value."""
    for key in keys:
        if not isinstance(cfg, dict):
            return default
        cfg = cfg.get(key, default)
    return cfg
