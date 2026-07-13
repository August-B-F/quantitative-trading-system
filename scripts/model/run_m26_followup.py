"""M26 follow-up: leave-one-out 2018, 3d deep dive, asymmetric windows.

Imports setup from run_m26_deep (guarded under __main__), reuses all the
momentum arrays, regime classifier and monthly rebalance engine.

Outputs:
  results/M26_FOLLOWUP.md
  (updates results/OPTIMIZED_STRATEGY.md with the final M26 choice)
"""
from __future__ import annotations
import json

import pandas as pd

import run_m26_deep as deep

ROOT = deep.ROOT
ETFS = deep.ETFS
NDAYS = deep.NDAYS
DATES = deep.DATES
fomc_day_idx = deep.fomc_day_idx
run_variant = deep.run_variant
stats = deep.stats
annual_returns = deep.annual_returns
drawdown_periods = deep.drawdown_periods
fomc_window_mask = deep.fomc_window_mask


def stats_excl(s, exclude_year):
    mask = s.index.year != exclude_year
    return stats(s[mask].values)


def fomc_in_range(start, end):
    start = pd.Timestamp(start); end = pd.Timestamp(end)
    return [DATES[i].strftime("%Y-%m-%d") for i in fomc_day_idx
            if start <= DATES[i] <= end]


# FOLLOW-UP 1 — Leave-one-out 2018
print("\n=== FOLLOW-UP 1: leave-one-out 2018 ===")

FOMC_SYM = fomc_window_mask(2, 2)

base_s, base_picks = run_variant(deferral_days=0, event_mask=None)
m26_5d_s, m26_5d_picks = run_variant(deferral_days=5, event_mask=FOMC_SYM)
m26_3d_s, m26_3d_picks = run_variant(deferral_days=3, event_mask=FOMC_SYM)

loo_rows = []
for label, s in [("base", base_s), ("m26_5d", m26_5d_s), ("m26_3d", m26_3d_s)]:
    full = stats(s.values)
    ex2018 = stats_excl(s, 2018)
    loo_rows.append({
        "variant": label,
        "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_maxdd": full["max_dd"],
        "ex2018_cagr": ex2018["cagr"], "ex2018_sharpe": ex2018["sharpe"], "ex2018_maxdd": ex2018["max_dd"],
        "d_cagr": ex2018["cagr"] - full["cagr"],
        "d_maxdd": ex2018["max_dd"] - full["max_dd"],
    })
    print(f"  {label:8s}  full: {full['cagr']*100:5.2f}% / {full['max_dd']*100:6.2f}%   "
          f"ex2018: {ex2018['cagr']*100:5.2f}% / {ex2018['maxdd'] if False else ex2018['max_dd']*100:6.2f}%")

# vs base, excluding 2018
base_ex = stats_excl(base_s, 2018)
m26_5d_ex = stats_excl(m26_5d_s, 2018)
m26_3d_ex = stats_excl(m26_3d_s, 2018)
dd_imp_5d_ex = (m26_5d_ex["max_dd"] - base_ex["max_dd"]) * 100
dd_imp_3d_ex = (m26_3d_ex["max_dd"] - base_ex["max_dd"]) * 100
cagr_d_5d_ex = (m26_5d_ex["cagr"] - base_ex["cagr"]) * 100
cagr_d_3d_ex = (m26_3d_ex["cagr"] - base_ex["cagr"]) * 100
print(f"\n  Excluding 2018:")
print(f"    5d vs base : dCAGR {cagr_d_5d_ex:+.2f}pp  dMaxDD {dd_imp_5d_ex:+.2f}pp")
print(f"    3d vs base : dCAGR {cagr_d_3d_ex:+.2f}pp  dMaxDD {dd_imp_3d_ex:+.2f}pp")


# FOLLOW-UP 2 — 3d deep dive (Test 4 + Test 5)
print("\n=== FOLLOW-UP 2: 3d deep dive ===")

base_dd = drawdown_periods(base_s, top_n=5)
m26_3d_dd = drawdown_periods(m26_3d_s, top_n=5)

def summarize_dd(eps, label):
    rows = []
    for e in eps:
        fds = fomc_in_range(e["start"], e["end"])
        rows.append({
            "start": str(e["start"].date()),
            "trough": str(e["trough"].date()),
            "end": str(e["end"].date()),
            "dd_pct": round(e["dd"] * 100, 2),
            "n_fomc": len(fds),
        })
        print(f"  {label}: {e['start'].date()} -> {e['trough'].date()} -> {e['end'].date()}  dd={e['dd']*100:.2f}%  FOMC={len(fds)}")
    return rows

print("  Base top-5 DDs:")
base_dd_rows = summarize_dd(base_dd, "BASE")
print("  3d  top-5 DDs:")
m26_3d_dd_rows = summarize_dd(m26_3d_dd, "M26_3d")

# Targeted windows for 3d
targets = [
    ("March 2020", "2020-02-01", "2020-06-01"),
    ("Q4 2018",    "2018-09-01", "2019-02-01"),
    ("2022",       "2022-01-01", "2023-01-01"),
]
target_3d = []
for name, s0, s1 in targets:
    bw = base_s[(base_s.index >= s0) & (base_s.index <= s1)]
    mw = m26_3d_s[(m26_3d_s.index >= s0) & (m26_3d_s.index <= s1)]
    bc = float((1 + bw).prod() - 1); mc = float((1 + mw).prod() - 1)
    fds = fomc_in_range(s0, s1)
    defhere = m26_3d_picks[(m26_3d_picks["rebal_date"] >= s0) & (m26_3d_picks["rebal_date"] <= s1) & m26_3d_picks["deferred"]]
    target_3d.append({
        "name": name,
        "base_cum_pct": round(bc * 100, 2),
        "m26_3d_cum_pct": round(mc * 100, 2),
        "delta_pp": round((mc - bc) * 100, 2),
        "n_fomc": len(fds),
        "n_deferred": int(len(defhere)),
    })
    print(f"  {name:12s}: base {bc*100:+.2f}%  3d {mc*100:+.2f}%  d {(mc-bc)*100:+.2f}pp  FOMC={len(fds)}  deferred={len(defhere)}")

# Test 5: false cost for 3d
print("  False cost 3d:")
merged_3d = base_picks.merge(m26_3d_picks, on="rebal_date", suffixes=("_base", "_m26"))
def3 = merged_3d[merged_3d["deferred_m26"]].copy()
def3["top1_changed"] = def3["top1_base"] != def3["top1_m26"]
def3["topk_changed"] = def3.apply(lambda r: tuple(r["topk_base"]) != tuple(r["topk_m26"]), axis=1)
def3["ret_delta"] = def3["ret_m26"] - def3["ret_base"]
n3_def = len(def3)
n3_t1 = int(def3["top1_changed"].sum())
n3_tk = int(def3["topk_changed"].sum())
n3_better = int((def3.loc[def3["top1_changed"], "ret_delta"] > 0).sum())
n3_worse = int((def3.loc[def3["top1_changed"], "ret_delta"] < 0).sum())
avg3 = float(def3.loc[def3["top1_changed"], "ret_delta"].mean()) if n3_t1 else 0.0
print(f"    deferred={n3_def} top1_changed={n3_t1} ({n3_t1/max(n3_def,1)*100:.0f}%) better={n3_better} worse={n3_worse} avg_dret={avg3*100:+.2f}pp")

fc_3d = {
    "n_deferred": n3_def, "n_top1_changed": n3_t1, "n_topk_changed": n3_tk,
    "n_better": n3_better, "n_worse": n3_worse,
    "avg_ret_delta_pp": round(avg3 * 100, 3),
}


# FOLLOW-UP 3 — Asymmetric windows
print("\n=== FOLLOW-UP 3: asymmetric windows ===")

PRE_MASK = fomc_window_mask(2, 0)   # [i_f-2, i_f]
POST_MASK = fomc_window_mask(0, 2)  # [i_f, i_f+2]
SYM_MASK = fomc_window_mask(2, 2)   # [i_f-2, i_f+2]

asym_results = {}
for days in (3, 5):
    for lbl, mk in [("pre", PRE_MASK), ("post", POST_MASK), ("sym", SYM_MASK)]:
        s, p = run_variant(deferral_days=days, event_mask=mk)
        st = stats(s.values)
        n_def = int(p["deferred"].sum())
        asym_results[f"M26_{lbl}_{days}d"] = {**st, "n_deferred": n_def}
        print(f"  {lbl:4s} {days}d  CAGR {st['cagr']*100:5.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:6.2f}%  deferred={n_def}")


# FINAL VERDICT
print("\n=== FINAL PICK ===")
# Rank by: (DD improvement * 1.0) + (CAGR delta * 1.0)  — user cares about DD primarily
base_full = stats(base_s.values)
candidates = []
for name, st in asym_results.items():
    d_cagr = (st["cagr"] - base_full["cagr"]) * 100
    d_dd = (st["max_dd"] - base_full["max_dd"]) * 100
    score = d_dd + d_cagr  # both "higher is better"
    candidates.append((name, st, d_cagr, d_dd, score))
candidates.sort(key=lambda x: -x[4])
for name, st, dc, dd, sc in candidates:
    print(f"  {name:20s}  dCAGR {dc:+.2f}pp  dDD {dd:+.2f}pp  score {sc:+.2f}")
final_name, final_st, final_dc, final_dd, _ = candidates[0]
print(f"\n  WINNER: {final_name}")


# SAVE JSON + MARKDOWN
payload = {
    "description": "M26 follow-up: LOO-2018, 3d deep dive, asymmetric windows",
    "followup1_leave_one_out_2018": loo_rows,
    "followup1_vs_base_ex2018": {
        "5d":  {"d_cagr_pp": round(cagr_d_5d_ex, 3), "d_maxdd_pp": round(dd_imp_5d_ex, 3)},
        "3d":  {"d_cagr_pp": round(cagr_d_3d_ex, 3), "d_maxdd_pp": round(dd_imp_3d_ex, 3)},
    },
    "followup2_3d_drawdowns_base": base_dd_rows,
    "followup2_3d_drawdowns_m26": m26_3d_dd_rows,
    "followup2_3d_targeted": target_3d,
    "followup2_3d_false_cost": fc_3d,
    "followup3_asymmetric": asym_results,
    "final_pick": {"name": final_name, **final_st, "d_cagr_pp": round(final_dc, 3), "d_maxdd_pp": round(final_dd, 3)},
}
(ROOT / "results/experiments/M26_followup.json").write_text(json.dumps(payload, indent=2, default=str))
print(f"\nWrote results/experiments/M26_followup.json")

def fmt_pct(v): return f"{v*100:.2f}%" if v == v else "n/a"

md = []
md.append("# M26 FOLLOW-UP — 2018 Dependency, 3d Deep Dive, Asymmetric Windows\n")
md.append("Follow-up to [M26_ANALYSIS.md](M26_ANALYSIS.md). Tests whether M26's benefit survives removing the 2018 episode, whether the 3d window reduces the false-cost of the 5d variant, and whether an asymmetric (pre-only or post-only) window isolates the mechanism.\n")

md.append("## Follow-up 1 — Leave-one-out 2018\n")
md.append("| Variant | Full CAGR | Full MaxDD | Ex-2018 CAGR | Ex-2018 MaxDD | dCAGR | dMaxDD |")
md.append("|---|---|---|---|---|---|---|")
for r in loo_rows:
    md.append(f"| {r['variant']} | {fmt_pct(r['full_cagr'])} | {fmt_pct(r['full_maxdd'])} | "
              f"{fmt_pct(r['ex2018_cagr'])} | {fmt_pct(r['ex2018_maxdd'])} | "
              f"{r['d_cagr']*100:+.2f}pp | {r['d_maxdd']*100:+.2f}pp |")

md.append("\n**Vs base, with 2018 excluded:**\n")
md.append(f"- 5d variant: dCAGR **{cagr_d_5d_ex:+.2f}pp**, dMaxDD **{dd_imp_5d_ex:+.2f}pp**")
md.append(f"- 3d variant: dCAGR **{cagr_d_3d_ex:+.2f}pp**, dMaxDD **{dd_imp_3d_ex:+.2f}pp**")

if dd_imp_3d_ex > 3.0:
    md.append("\nThe 3d variant keeps >3pp MaxDD improvement after removing 2018 → **benefit is distributed across multiple events.**\n")
else:
    md.append("\nMost of the MaxDD improvement came from the single 2018 episode. Still valuable as a one-time insurance payout but **not a systematic edge**.\n")

md.append("## Follow-up 2 — 3d variant deep dive\n")
md.append("### Top-5 drawdowns (OPTIMIZED base)\n")
md.append("| Start | Trough | End | DD | FOMC in range |")
md.append("|---|---|---|---|---|")
for r in base_dd_rows:
    md.append(f"| {r['start']} | {r['trough']} | {r['end']} | {r['dd_pct']}% | {r['n_fomc']} |")

md.append("\n### Top-5 drawdowns (OPTIMIZED + M26 3d)\n")
md.append("| Start | Trough | End | DD | FOMC in range |")
md.append("|---|---|---|---|---|")
for r in m26_3d_dd_rows:
    md.append(f"| {r['start']} | {r['trough']} | {r['end']} | {r['dd_pct']}% | {r['n_fomc']} |")

md.append("\n### Targeted windows (3d)\n")
md.append("| Period | Base | M26 3d | Δ | FOMC | Deferred |")
md.append("|---|---|---|---|---|---|")
for t in target_3d:
    md.append(f"| {t['name']} | {t['base_cum_pct']:+.2f}% | {t['m26_3d_cum_pct']:+.2f}% | {t['delta_pp']:+.2f}pp | {t['n_fomc']} | {t['n_deferred']} |")

md.append("\n### False-cost check (3d)\n")
md.append(f"- Deferred rebalances: **{n3_def}**")
md.append(f"- Top-1 pick changed: **{n3_t1}** ({n3_t1/max(n3_def,1)*100:.0f}%)")
md.append(f"- Top-k set changed: {n3_tk}")
md.append(f"- When top-1 changed: better={n3_better}, worse={n3_worse}, avg Δret={avg3*100:+.2f}pp\n")
md.append("For comparison, the 5d variant changed top-1 in **9 / 28 (32%)** with avg Δret **−2.92pp**.\n")
if n3_t1 < 5:
    md.append("→ 3d changes far fewer picks. Signal drift is largely eliminated; benefit is closer to free.\n")
else:
    md.append("→ 3d still changes a similar fraction of picks; the drift problem persists.\n")

md.append("## Follow-up 3 — Asymmetric windows\n")
md.append("| Variant | CAGR | Sharpe | MaxDD | Deferrals |")
md.append("|---|---|---|---|---|")
order = ["M26_pre_3d", "M26_post_3d", "M26_sym_3d", "M26_pre_5d", "M26_post_5d", "M26_sym_5d"]
for name in order:
    st = asym_results[name]
    md.append(f"| {name} | {fmt_pct(st['cagr'])} | {st['sharpe']:.2f} | {fmt_pct(st['max_dd'])} | {st['n_deferred']} |")

pre3 = asym_results["M26_pre_3d"]; post3 = asym_results["M26_post_3d"]; sym3 = asym_results["M26_sym_3d"]
if pre3["max_dd"] < post3["max_dd"] and pre3["max_dd"] <= sym3["max_dd"] + 0.005:
    md.append("\n→ **Pre-only** captures most of the benefit. Mechanism confirmed: risk is rebalancing INTO an uncertain FOMC outcome.\n")
elif post3["max_dd"] < pre3["max_dd"] and post3["max_dd"] <= sym3["max_dd"] + 0.005:
    md.append("\n→ **Post-only** is best. The mechanism is avoiding rebalancing into post-FOMC volatility, not pre-meeting uncertainty.\n")
else:
    md.append("\n→ Symmetric window is best. Both directions contribute.\n")

md.append("\n## Final pick\n")
md.append(f"**{final_name}** — CAGR {fmt_pct(final_st['cagr'])}, Sharpe {final_st['sharpe']:.2f}, MaxDD {fmt_pct(final_st['max_dd'])}")
md.append(f" (dCAGR {final_dc:+.2f}pp, dMaxDD {final_dd:+.2f}pp vs OPTIMIZED base)\n")

# Honest concentration-risk assessment
concentration_note = "A meaningful share of the headline improvement is concentrated in the 2018 FOMC episode; expect the real-world benefit to be lumpy, not smooth."
if dd_imp_3d_ex > 3.0:
    concentration_note = "The DD improvement survives leaving out 2018, so the benefit is diversified across multiple events rather than one lucky trade."
md.append(f"**Concentration note:** {concentration_note}\n")

(ROOT / "results/M26_FOLLOWUP.md").write_text("\n".join(md), encoding="utf-8")
print(f"Wrote results/M26_FOLLOWUP.md")


# UPDATE OPTIMIZED_STRATEGY.md with the final winner
opt_path = ROOT / "results/OPTIMIZED_STRATEGY.md"
lines = opt_path.read_text(encoding="utf-8").splitlines()

# Parse winner name → (side, days)
parts = final_name.split("_")  # ['M26', <side>, '<n>d']
side = parts[1]
days = parts[2]
if side == "sym":
    window_desc = f"if rebalance falls within ±2 trading days of FOMC decision, defer {days}"
elif side == "pre":
    window_desc = f"if rebalance falls within 2 trading days BEFORE FOMC decision, defer {days}"
else:
    window_desc = f"if rebalance falls within 2 trading days AFTER FOMC decision, defer {days}"

updated = []
for ln in lines:
    if ln.startswith("- Rebalancing variant:"):
        updated.append(f"- Rebalancing variant: monthly + M26 final ({final_name}): {window_desc}")
    elif ln.startswith("- CAGR:"):
        updated.append(f"- CAGR: **{fmt_pct(final_st['cagr'])}**")
    elif ln.startswith("- Sharpe:"):
        updated.append(f"- Sharpe: **{final_st['sharpe']:.2f}**")
    elif ln.startswith("- MaxDD:"):
        updated.append(f"- MaxDD: **{fmt_pct(final_st['max_dd'])}**")
    else:
        updated.append(ln)
# Append a follow-up footnote once
footer = f"\n## M26 follow-up (final choice)\n\n- Variant: **{final_name}**\n- vs OPTIMIZED base: dCAGR {final_dc:+.2f}pp, dMaxDD {final_dd:+.2f}pp\n- Ex-2018 DD improvement (3d sym): {dd_imp_3d_ex:+.2f}pp\n- See [M26_FOLLOWUP.md](M26_FOLLOWUP.md)\n"
text = "\n".join(updated)
if "M26 follow-up (final choice)" not in text:
    text += footer
opt_path.write_text(text, encoding="utf-8")
print("Updated results/OPTIMIZED_STRATEGY.md")

print("\nDone.")
