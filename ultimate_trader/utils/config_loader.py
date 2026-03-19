"""Load and merge YAML config files."""
import yaml
from pathlib import Path
from typing import Any


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    """Unified config object. Access keys as attributes or dict-style."""

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        try:
            val = self._data[name]
        except KeyError:
            raise AttributeError(f"Config has no key '{name}'")
        if isinstance(val, dict):
            return Config(val)
        return val

    def __getitem__(self, key):
        val = self._data[key]
        if isinstance(val, dict):
            return Config(val)
        return val

    def get(self, key, default=None):
        val = self._data.get(key, default)
        if isinstance(val, dict):
            return Config(val)
        return val

    def to_dict(self) -> dict:
        return self._data


def load_config(config_dir: str = "config") -> Config:
    """
    Load and merge config.yaml, model.yaml, training.yaml from config_dir.
    Returns a unified Config object.
    """
    config_path = Path(config_dir)
    merged: dict = {}
    for fname in ["config.yaml", "model.yaml", "training.yaml"]:
        fpath = config_path / fname
        if fpath.exists():
            with open(fpath) as f:
                data = yaml.safe_load(f) or {}
            merged = _deep_merge(merged, data)
    return Config(merged)
