# NOT EXECUTED IN-SESSION — run offline. Estimated runtime: ~5 minutes
# (no retrain — uses cached classifier; pure replay with alternate rebal dates).
#
# REFACTOR REQUIRED: the current stress_harness.run_strategy_from_cache rebalances
# monthly at `month_last` (last test day per month). Test 5 needs to vary the
# rebalance date-of-month (1st, 10th, 15th, 20th, last) and rebalance frequency
# (weekly / biweekly / monthly / quarterly). This requires:
#
#   1. Exposing the rebalance-date sequence as a parameter of run_strategy_from_cache
#      (e.g. `rebal_dates: pd.DatetimeIndex`).
#   2. Generalizing the fwd21 return used per rebal to reflect the period until the
#      NEXT rebalance, not a fixed 21-day forward (otherwise quarterly/weekly returns
#      will be mis-scaled).
#   3. For cost accounting, recomputing weight matrices on the new schedule.
#
# Until that refactor is landed, this script demonstrates the intended surface
# but does not run.
"""Rebalance-timing stress test (NOT EXECUTED — pending harness refactor)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/model"))

from stress_harness import load_cache, run_strategy_from_cache  # noqa: E402

OUT = ROOT / "results/stress"


def main():
    # Intended matrix:
    frequencies = ["weekly", "biweekly", "monthly", "quarterly"]
    dom_offsets = [0, 5, 10, 15, -1]  # day-of-month offsets for monthly variant
    print("This test is pending harness refactor (see docstring).")
    print("Intended variants:", {"freqs": frequencies, "dom_offsets": dom_offsets})
    (OUT / "test5.json").write_text(json.dumps({
        "status": "NOT EXECUTED - harness refactor required",
        "refactor": [
            "expose rebal_dates param in run_strategy_from_cache",
            "use variable-horizon forward returns aligned to rebal schedule",
            "recompute weight matrices on new schedule",
        ],
        "intended_variants": {"freqs": frequencies, "dom_offsets": dom_offsets},
    }, indent=2))
    print(f"Wrote {OUT / 'test5.json'}")


if __name__ == "__main__":
    main()
