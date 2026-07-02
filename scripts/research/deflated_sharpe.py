"""Deflated Sharpe Ratio — Bailey & Lopez de Prado (2014).

Implements the Probabilistic Sharpe Ratio (PSR) and the Deflated Sharpe
Ratio (DSR), the selection-bias-corrected significance test that
CONSTITUTION.md rule 3 requires next to every reported Sharpe.

Formulas
--------
Probabilistic Sharpe Ratio (probability that the true SR exceeds a
benchmark SR*, given T observations and non-normal returns)::

    PSR(SR*) = Phi( (SR - SR*) * sqrt(T - 1)
                    / sqrt(1 - g3*SR + ((g4 - 1)/4) * SR^2) )

where ``g3`` is the skewness and ``g4`` the (non-excess) kurtosis of the
per-period returns (Gaussian: g3=0, g4=3), and ``Phi`` is the standard
normal CDF.

Expected maximum Sharpe of N unskilled (true SR = 0) trials with
cross-trial variance V[SR] (Euler-Mascheroni constant ``gamma``)::

    E[max SR] ~= sqrt(V[SR]) * ( (1 - gamma) * Z(1 - 1/N)
                                 + gamma     * Z(1 - 1/(N*e)) )

where ``Z`` is the standard normal quantile function.

Deflated Sharpe Ratio::

    DSR = PSR(SR* = E[max SR | N trials, V[SR]])

i.e. the probability that the observed SR is genuine skill rather than
the lucky best draw out of N tries. DSR < 0.95 means the track record
does not clear the selection-bias hurdle.

Units: ``sr``, ``sr_variance_across_trials`` and ``T`` must share the
same periodicity (e.g. annualized SR with annual-equivalent T, or
per-period SR with the raw observation count). Mixing annualized SRs
with monthly T (as the CLI examples in EVALUATION.md do, matching how
the trial ledger records Sharpes) is an approximation: numerator and
E[max SR] scale together, so the deflation comparison remains
meaningful, but treat the absolute probability with a grain of salt.

Reference:
    Bailey, D. H. and Lopez de Prado, M. (2014). "The Deflated Sharpe
    Ratio: Correcting for Selection Bias, Backtest Overfitting, and
    Non-Normality." The Journal of Portfolio Management, 40(5), 94-107.

CLI
---
::

    py -3 scripts/research/deflated_sharpe.py --sharpe 0.962 --T 96 \\
        --trials 316 --var 0.05
    py -3 scripts/research/deflated_sharpe.py --sharpe 0.962 --T 96 \\
        --ledger results/TRIAL_LEDGER.csv

With ``--ledger``, ``n_trials`` is the sum of the ledger's
``n_trials_represented`` column and ``V[SR]`` is the sample variance of
its non-empty ``sharpe`` column. Explicit ``--trials`` / ``--var``
override the ledger-derived values.
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import statistics
from pathlib import Path

from scipy.stats import norm

log = logging.getLogger(__name__)

EULER_GAMMA = 0.5772156649015329


def probabilistic_sharpe(
    sr: float, sr_benchmark: float, T: int, skew: float = 0.0, kurt: float = 3.0
) -> float:
    """PSR: probability that the true SR exceeds ``sr_benchmark``.

    ``T`` is the number of return observations behind ``sr``; ``skew``
    and ``kurt`` (non-excess, Gaussian=3) describe those returns.
    """
    if T < 2:
        raise ValueError(f"T must be >= 2, got {T}")
    denom_sq = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom_sq <= 0:
        raise ValueError(
            f"invalid moment combination: 1 - g3*SR + (g4-1)/4*SR^2 = {denom_sq:.4f} <= 0"
        )
    z = (sr - sr_benchmark) * math.sqrt(T - 1.0) / math.sqrt(denom_sq)
    return float(norm.cdf(z))


def expected_max_sharpe(
    n_trials: int, sr_variance: float, sr_mean: float = 0.0
) -> float:
    """E[max SR] across ``n_trials`` unskilled trials with variance ``sr_variance``.

    The expected best Sharpe produced by pure luck when ``n_trials``
    independent zero-skill (true SR = ``sr_mean``) strategies are tried
    and the best is reported.
    """
    if n_trials <= 1:
        return sr_mean
    if sr_variance < 0:
        raise ValueError(f"sr_variance must be >= 0, got {sr_variance}")
    sd = math.sqrt(sr_variance)
    z1 = norm.ppf(1.0 - 1.0 / n_trials)
    z2 = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sr_mean + sd * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(
    sr: float,
    T: int,
    skew: float,
    kurt: float,
    n_trials: int,
    sr_variance_across_trials: float,
) -> float:
    """DSR: PSR evaluated against the luck benchmark E[max SR | N, V[SR]].

    Returns the probability that ``sr`` reflects skill rather than
    being the best of ``n_trials`` noise draws.
    """
    sr0 = expected_max_sharpe(n_trials, sr_variance_across_trials)
    return probabilistic_sharpe(sr, sr0, T, skew=skew, kurt=kurt)


def ledger_stats(path: Path) -> tuple[int, float]:
    """Derive (n_trials, V[SR]) from a TRIAL_LEDGER.csv.

    n_trials = sum of ``n_trials_represented`` (default 1 per row);
    V[SR] = sample variance of the non-empty ``sharpe`` values.
    """
    n_trials = 0
    sharpes: list[float] = []
    with open(path, "r", newline="") as f:
        for row in csv.DictReader(f):
            raw_n = (row.get("n_trials_represented") or "").strip()
            n_trials += int(raw_n) if raw_n else 1
            raw_sr = (row.get("sharpe") or "").strip()
            if raw_sr:
                sharpes.append(float(raw_sr))
    if len(sharpes) < 2:
        raise ValueError(f"ledger {path} has < 2 sharpe values; cannot estimate V[SR]")
    return n_trials, statistics.variance(sharpes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014)")
    p.add_argument("--sharpe", type=float, required=True, help="observed Sharpe ratio")
    p.add_argument("--T", type=int, required=True, help="number of return observations")
    p.add_argument("--skew", type=float, default=0.0, help="return skewness (default 0)")
    p.add_argument("--kurt", type=float, default=3.0, help="return kurtosis, non-excess (default 3)")
    p.add_argument("--trials", type=int, default=None, help="number of trials behind the selection")
    p.add_argument("--var", type=float, default=None, help="variance of SR across trials")
    p.add_argument("--benchmark", type=float, default=0.0, help="PSR benchmark SR* (default 0)")
    p.add_argument("--ledger", type=Path, default=None,
                   help="TRIAL_LEDGER.csv to derive --trials/--var from (explicit flags override)")
    args = p.parse_args(argv)

    n_trials, sr_var = args.trials, args.var
    if args.ledger is not None:
        led_n, led_var = ledger_stats(args.ledger)
        if n_trials is None:
            n_trials = led_n
        if sr_var is None:
            sr_var = led_var
        log.info("ledger %s: n_trials=%d, V[SR]=%.6f", args.ledger, led_n, led_var)
    if n_trials is None or sr_var is None:
        p.error("provide --trials and --var, or --ledger")

    psr = probabilistic_sharpe(args.sharpe, args.benchmark, args.T, args.skew, args.kurt)
    sr0 = expected_max_sharpe(n_trials, sr_var)
    dsr = deflated_sharpe(args.sharpe, args.T, args.skew, args.kurt, n_trials, sr_var)

    print(f"SR={args.sharpe:.4f}  T={args.T}  skew={args.skew}  kurt={args.kurt}")
    print(f"n_trials={n_trials}  V[SR]={sr_var:.6f}")
    print(f"PSR (vs SR*={args.benchmark:.2f}): {psr:.4f}")
    print(f"E[max SR | {n_trials} trials]: {sr0:.4f}")
    print(f"DSR: {dsr:.4f}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
