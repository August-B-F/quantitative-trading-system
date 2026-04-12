# ARCHIVED: M26 post-3d LOO exploration — superseded by run_m26_followup
"""Leave-one-out 2018 for the winning M26_post_3d variant."""
from pathlib import Path
import pandas as pd
import run_m26_deep as deep

ROOT = deep.ROOT

POST_MASK = deep.fomc_window_mask(0, 2)  # [i_f, i_f+2]

base_s, _ = deep.run_variant(deferral_days=0, event_mask=None)
post3_s, post3_picks = deep.run_variant(deferral_days=3, event_mask=POST_MASK)

def stats_ex(s, yr):
    return deep.stats(s[s.index.year != yr].values)

base_full = deep.stats(base_s.values)
base_ex = stats_ex(base_s, 2018)
post3_full = deep.stats(post3_s.values)
post3_ex = stats_ex(post3_s, 2018)

rows = [
    ("base",         base_full, base_ex),
    ("m26_post_3d",  post3_full, post3_ex),
]
for name, full, ex in rows:
    print(f"  {name:14s}  full {full['cagr']*100:5.2f}% / {full['max_dd']*100:6.2f}%   "
          f"ex2018 {ex['cagr']*100:5.2f}% / {ex['max_dd']*100:6.2f}%")

dcagr_ex = (post3_ex["cagr"] - base_ex["cagr"]) * 100
ddd_ex = (post3_ex["max_dd"] - base_ex["max_dd"]) * 100
print(f"\n  post_3d vs base (ex-2018): dCAGR {dcagr_ex:+.2f}pp  dMaxDD {ddd_ex:+.2f}pp")

# Also count 2018 contribution to post_3d deferrals
def_2018 = post3_picks[post3_picks["deferred"] & (post3_picks["rebal_date"].dt.year == 2018)]
print(f"  post_3d deferrals in 2018: {len(def_2018)} / {int(post3_picks['deferred'].sum())} total")

def fmt(v): return f"{v*100:.2f}%" if v == v else "n/a"

md = []
md.append("\n---\n")
md.append("## Follow-up 4 — Leave-one-out 2018 for the winner (M26_post_3d)\n")
md.append("| Variant | Full CAGR | Full MaxDD | Ex-2018 CAGR | Ex-2018 MaxDD | Δ CAGR (ex) | Δ MaxDD (ex) |")
md.append("|---|---|---|---|---|---|---|")
md.append(f"| Base (no M26) | {fmt(base_full['cagr'])} | {fmt(base_full['max_dd'])} | {fmt(base_ex['cagr'])} | {fmt(base_ex['max_dd'])} | — | — |")
md.append(f"| M26_post_3d | {fmt(post3_full['cagr'])} | {fmt(post3_full['max_dd'])} | {fmt(post3_ex['cagr'])} | {fmt(post3_ex['max_dd'])} | "
          f"{dcagr_ex:+.2f}pp | {ddd_ex:+.2f}pp |")
md.append("")
md.append(f"- Post-3d deferrals in 2018: **{len(def_2018)} / {int(post3_picks['deferred'].sum())}** total across history")
md.append("")

# Verdict language per user's spec
if post3_ex["cagr"] >= base_ex["cagr"]:
    md.append("**Verdict:** Ex-2018 post-3d CAGR **≥** base ex-2018 CAGR → the post-only rule is "
              "**harmless-to-helpful outside 2018**. Ship with confidence.\n")
elif (base_ex["cagr"] - post3_ex["cagr"]) * 100 <= 0.5:
    md.append(f"**Verdict:** Ex-2018 post-3d CAGR is {dcagr_ex:+.2f}pp vs base (within 0.5pp). "
              "Effectively neutral outside 2018 — ship, with the concentration caveat that the "
              "headline DD win is almost entirely the Q4 2018 episode.\n")
else:
    md.append(f"**Verdict:** Ex-2018 post-3d underperforms base by {-dcagr_ex:.2f}pp CAGR — "
              "the rule has a small cost outside its one big win. Worth shipping as insurance but "
              "**document the concentration honestly**: this is a one-event insurance policy, "
              "not a systematic edge.\n")

out = ROOT / "results/M26_FOLLOWUP.md"
txt = out.read_text(encoding="utf-8")
if "Follow-up 4" not in txt:
    out.write_text(txt + "\n".join(md), encoding="utf-8")
    print(f"\nAppended to {out}")
else:
    print("\nFollow-up 4 section already present; skipped append.")
