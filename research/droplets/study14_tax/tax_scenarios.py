"""Study 14 — ISK vs depå 10-year terminal-wealth math.

Analytic model per HYPOTHESIS.md (written first). No price data, no
strategy tuning. Run:  py -3 research/droplets/study14_tax/tax_scenarios.py
Writes scenario_results.csv next to this file and prints a summary.
"""

from __future__ import annotations

import csv
import os

HORIZON = 10
SIZES = [100_000, 300_000, 1_000_000, 3_000_000]
CAGRS = [0.08, 0.12, 0.16]
FRICTIONS = {"low": 0.0060, "mid": 0.0120, "high": 0.0250}

ALLOWANCE = 300_000.0          # SEK, 2026 grundnivå, held nominal
SCHABLON_RATE = 0.0355         # SLR 2.55% (2025-11-30) + 1pp
TAX_ON_SCHABLON = 0.30         # => 1.065% of base above allowance
CG_TAX = 0.30                  # depå capital-gains tax


def isk_terminal(w0: float, r: float, friction: float,
                 schablon_rate: float = SCHABLON_RATE,
                 allowance: float = ALLOWANCE) -> float:
    """Yearly: grow at (r - friction), pay 30% x schablon_rate on the
    kapitalunderlag above the allowance. Kapitalunderlag = mean of the
    four quarter-opening values + deposits/4 (initial deposit counts in
    year 1)."""
    g = 1.0 + (r - friction)
    w = w0
    for year in range(HORIZON):
        quarters = [w * g ** (q / 4.0) for q in range(4)]
        base = sum(quarters) / 4.0
        if year == 0:
            base += w0 / 4.0  # the funding deposit is added to the base
        tax = max(0.0, base - allowance) * schablon_rate * TAX_ON_SCHABLON
        w = w * g - tax
    return w


def depa_terminal(w0: float, r: float) -> float:
    """Full annual realization at ~8x turnover: after-tax growth 1+0.7r."""
    return w0 * (1.0 + (1.0 - CG_TAX) * r) ** HORIZON


def buyhold_terminal(w0: float, r: float) -> float:
    """Depå, single sale in year 10 (tax deferral reference)."""
    gross = w0 * (1.0 + r) ** HORIZON
    return gross - CG_TAX * (gross - w0)


def cagr(w0: float, wt: float) -> float:
    return (wt / w0) ** (1.0 / HORIZON) - 1.0


def breakeven_friction(w0: float, r: float) -> float:
    """Friction at which ISK terminal == depå terminal (bisection)."""
    target = depa_terminal(w0, r)
    lo, hi = 0.0, 0.10
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if isk_terminal(w0, r, mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def main() -> None:
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "scenario_results.csv")
    rows = []
    for w0 in SIZES:
        for r in CAGRS:
            t_depa = depa_terminal(w0, r)
            t_bh = buyhold_terminal(w0, r)
            row = {
                "size_sek": w0,
                "cagr_gross": r,
                "depa_terminal": round(t_depa),
                "depa_cagr_net": round(cagr(w0, t_depa), 6),
                "buyhold_terminal": round(t_bh),
                "buyhold_cagr_net": round(cagr(w0, t_bh), 6),
                "breakeven_friction_bps": round(
                    breakeven_friction(w0, r) * 1e4, 1),
            }
            for name, f in FRICTIONS.items():
                t_isk = isk_terminal(w0, r, f)
                row[f"isk_{name}_terminal"] = round(t_isk)
                row[f"isk_{name}_cagr_net"] = round(cagr(w0, t_isk), 6)
                row[f"isk_{name}_adv_bps"] = round(
                    (cagr(w0, t_isk) - cagr(w0, t_depa)) * 1e4, 1)
            # schablon sensitivity at MID friction
            for tag, sr in (("floor", 0.0125), ("peak2024", 0.0362)):
                t = isk_terminal(w0, r, FRICTIONS["mid"], schablon_rate=sr)
                row[f"isk_mid_adv_bps_{tag}"] = round(
                    (cagr(w0, t) - cagr(w0, t_depa)) * 1e4, 1)
            rows.append(row)

    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {out}")
    hdr = (f"{'size':>9} {'cagr':>5} | {'depa':>10} {'bh_spy':>10} "
           f"{'isk_low':>10} {'isk_mid':>10} {'isk_high':>10} | "
           f"{'adv_mid':>8} {'adv_low':>8} {'adv_high':>8} {'f*':>6}")
    print(hdr)
    for row in rows:
        print(f"{row['size_sek']:>9,} {row['cagr_gross']:>5.0%} | "
              f"{row['depa_terminal']:>10,} {row['buyhold_terminal']:>10,} "
              f"{row['isk_low_terminal']:>10,} {row['isk_mid_terminal']:>10,} "
              f"{row['isk_high_terminal']:>10,} | "
              f"{row['isk_mid_adv_bps']:>8} {row['isk_low_adv_bps']:>8} "
              f"{row['isk_high_adv_bps']:>8} "
              f"{row['breakeven_friction_bps']:>6}")


if __name__ == "__main__":
    main()
