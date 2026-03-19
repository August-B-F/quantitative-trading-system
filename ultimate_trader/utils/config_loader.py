import os
import yaml
from dotenv import load_dotenv

load_dotenv()


def _resolve_env(value):
    """
    Recursively resolve ${ENV_VAR} placeholders in config values.
    """
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        resolved = os.getenv(env_key)
        if resolved is None:
            raise EnvironmentError(f"Environment variable '{env_key}' not set. Check your .env file.")
        return resolved
    elif isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return _resolve_env(raw)


class Config:
    """
    Unified config object. Loads and merges config.yaml, model.yaml, training.yaml.
    Access keys as attributes: cfg.alpaca.key_id, cfg.model.hidden_dim, etc.
    """

    def __init__(self, config_dir: str = "config"):
        self._data = {}
        for fname in ["config.yaml", "model.yaml", "training.yaml"]:
            path = os.path.join(config_dir, fname)
            if os.path.exists(path):
                self._data.update(load_config(path))

    def __getattr__(self, key):
        if key.startswith("_"):
            raise AttributeError(key)
        val = self._data.get(key)
        if isinstance(val, dict):
            return _DictAccessor(val)
        return val

    def get(self, key, default=None):
        return self._data.get(key, default)

    def raw(self) -> dict:
        return self._data


class _DictAccessor:
    """Allows dot-access on nested dicts."""

    def __init__(self, d: dict):
        self._d = d

    def __getattr__(self, key):
        if key.startswith("_"):
            raise AttributeError(key)
        val = self._d.get(key)
        if isinstance(val, dict):
            return _DictAccessor(val)
        return val

    def __getitem__(self, key):
        return self._d[key]

    def __repr__(self):
        return repr(self._d)
