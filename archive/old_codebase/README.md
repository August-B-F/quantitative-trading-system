# ARCHIVED: pre-Phase-3 codebase

This directory holds code that was part of the project before the Phase 3
rewrite. None of it is imported by the current production pipeline (verified
by grep against `src/` and `scripts/`).

Contents:

- `config/` — old `config.yaml`/`model.yaml`/`training.yaml`. Only referenced
  by `ultimate_trader/utils/config_loader.py`. The production config dir is
  `/configs/` (plural) at the repo root.
- `strategies/` — old strategy implementations, superseded by the Phase 3
  strategy modules under `src/`.
- `ultimate_trader/` — old end-to-end trader codebase. Replaced by the
  current `src/` tree.
- `main.py` — old entrypoint.
- `test_all.py` — old integration test runner.
- `review_outputs.py` — old results review helper.

Kept for historical reference only. Do not import from here.
