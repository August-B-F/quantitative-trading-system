import yaml
from pathlib import Path


def load_config(path: str) -> dict:
    """Load a YAML config file and return as dict."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_all_configs(config_dir: str = "config") -> dict:
    """Load and merge config.yaml, model.yaml, training.yaml into one dict."""
    base = Path(config_dir)
    cfg = {}
    for fname in ["config.yaml", "model.yaml", "training.yaml"]:
        part = load_config(base / fname)
        if part:
            cfg.update(part)
    return cfg
