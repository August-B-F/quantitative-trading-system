"""Study 11 — ex-ante universe construction (NOT a backtest; no returns used).

Rules declared BEFORE running this script (2026-07-02):
  U1  first bar on or before 2010-01-04 (first trading day of 2010).
  U2  median daily dollar-volume proxy (close * volume) over
      2010-01-04..2017-12-29 >= $10,000,000.  Threshold pre-declared.
  U3  exclude VIX products (_VIX, VIXY, UVXY) and leveraged/inverse
      products (UVXY is the only one on disk).
  U4  duplicate / near-twin pairs named in advance — within each pair keep
      the member with the HIGHER U2 median dollar volume, drop the other:
      (SOXX,SMH) (XLK,VGT) (AGG,BND) (VNQ,IYR) (DBC,PDBC) (GBTC,BITO).
      XBI and IBB are BOTH kept (different indexes, different cap tilts) —
      declared in advance.
  U5  SHV is excluded from the ranked universe: it is the cash sleeve and
      the absolute-filter hurdle.

No performance (return) data is consulted anywhere in this script.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PRICES = ROOT / "data" / "clean" / "prices"

FIRST_BAR_CUTOFF = pd.Timestamp("2010-01-04")
DV_WINDOW = (pd.Timestamp("2010-01-04"), pd.Timestamp("2017-12-29"))
DV_THRESHOLD = 10_000_000.0

VIX_LEVERED = {"_VIX", "VIXY", "UVXY"}
HURDLE = {"SHV"}
TWIN_PAIRS = [("SOXX", "SMH"), ("XLK", "VGT"), ("AGG", "BND"),
              ("VNQ", "IYR"), ("DBC", "PDBC"), ("GBTC", "BITO")]


def main() -> None:
    rows = []
    for p in sorted(PRICES.glob("*.parquet")):
        t = p.stem
        df = pd.read_parquet(p)
        dv = (df["close"] * df["volume"]).loc[DV_WINDOW[0]:DV_WINDOW[1]]
        rows.append({
            "ticker": t,
            "first_bar": df.index.min().date(),
            "last_bar": df.index.max().date(),
            "n_bars": len(df),
            "median_dv_2010_2017_usd": float(dv.median()) if len(dv) else float("nan"),
        })
    survey = pd.DataFrame(rows).set_index("ticker")

    reasons = {}
    for t, r in survey.iterrows():
        if t in VIX_LEVERED:
            reasons[t] = "U3 vix/leveraged"
        elif t in HURDLE:
            reasons[t] = "U5 hurdle/cash sleeve"
        elif pd.Timestamp(r["first_bar"]) > FIRST_BAR_CUTOFF:
            reasons[t] = f"U1 first bar {r['first_bar']} > 2010-01-04"
        elif not (r["median_dv_2010_2017_usd"] >= DV_THRESHOLD):
            reasons[t] = f"U2 median $vol {r['median_dv_2010_2017_usd'] / 1e6:.1f}M < 10M"
    for a, b in TWIN_PAIRS:
        alive = [x for x in (a, b) if x not in reasons and x in survey.index]
        if len(alive) == 2:
            dva = survey.loc[a, "median_dv_2010_2017_usd"]
            dvb = survey.loc[b, "median_dv_2010_2017_usd"]
            drop = a if dva < dvb else b
            keep = b if drop == a else a
            reasons[drop] = f"U4 twin of {keep} (lower median $vol)"

    survey["excluded_reason"] = [reasons.get(t, "") for t in survey.index]
    survey["in_universe"] = survey["excluded_reason"] == ""
    survey = survey.sort_values(["in_universe", "median_dv_2010_2017_usd"],
                                ascending=[False, False])
    out = Path(__file__).parent / "universe_survey.csv"
    survey.to_csv(out)

    uni = sorted(survey.index[survey["in_universe"]])
    print(f"UNIVERSE ({len(uni)} tickers):")
    print(" ".join(uni))
    print("\nEXCLUDED:")
    for t, r in survey[~survey["in_universe"]].iterrows():
        print(f"  {t:6s} {r['excluded_reason']}")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
