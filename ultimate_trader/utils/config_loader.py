import yaml
import os
from typing import Any


class Config:
    """
    Hierarchical config loaded from YAML files.
    Access keys with dot notation: cfg.alpaca.key_id
    """

    def __init__(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, Config(value))
            else:
                setattr(self, key, value)

    def get(self, key: str, default: Any = None):
        return getattr(self, key, default)

    def to_dict(self) -> dict:
        out = {}
        for k, v in self.__dict__.items():
            out[k] = v.to_dict() if isinstance(v, Config) else v
        return out


def load_config(config_dir: str = "config") -> Config:
    """
    Loads and merges config.yaml, model.yaml, training.yaml into one Config object.
    """
    merged = {}
    for fname in ["config.yaml", "model.yaml", "training.yaml"]:
        fpath = os.path.join(config_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                data = yaml.safe_load(f)
            if data:
                merged.update(data)
    return Config(merged)
