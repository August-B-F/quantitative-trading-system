# ARCHIVED: tier1b report builder — superseded by TIER1B_REPORT.md already produced
"""Assemble TIER1B_REPORT.md and TIER1B_VERDICT.md from all Block A/B/C/D JSON."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/experiments"


def fmt_pct(v):
    try:
        if v != v:
            return "n/a"
        return f"{100*v:.1f}%"
    except Exception:
        return "n/a"


def fmt_num(v, fmt=".2f"):
    try:
        if v != v:
            return "n/a"
        return format(v, fmt)
    except Exception:
        return "n/a"


def load(name):
    p = OUT / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def main():
    baselines = json.loads((ROOT / "results/baselines.json").read_text())
    B0 = baselines["B0_random"]
    B1 = baselines["B1_QQQ"]
    B2 = baselines["B3_mom63d"]

    EXPS = {
        "EA1": load("EA1"),
        "EA2": load("EA2"),
        "EA3": load("EA3_histgb_core_fwd42"),
        "EA4": load("EA4_histgb_core_fwd63"),
        "EA5": load("EA5"),
        "EB1": load("EB1_large_histgb_ext_t2"),
        "EB2": load("EB2_mlp_small_core_t2"),
        "EB3": load("EB3_mlp_big_ext_t2"),
        "EB4": load("EB4_deep_histgb_all_t2"),
        "EC1": load("EC1"),
        "EC2": load("EC2"),
        "ED1": load("ED1"),
        "ED2": load("ED2"),
        "ED3": load("ED3"),
        "ED4": load("ED4"),
        "ED5": load("ED5"),
        "ED6": load("ED6"),
    }

    # Tier 1 baselines pulled from existing reports
    tier1 = {
        "E01": load("E01"), "E02": load("E02"), "E03": load("E03"),
    }

    rep = []
    rep.append("# TIER 1B REPORT — Alternative Approaches")
    rep.append("")
    rep.append("Splitter: ExpandingSplitter (min_train=60mo, val=6mo, test=3mo, "
               "step=3mo, sample_every=5d, embargo=5d). Cross-sectional expansion "
               "where noted. Monthly aggregation.")
    rep.append("")
    rep.append("Baselines (from results/baselines.json):")
    rep.append(f"- **B0 random**: acc {fmt_pct(B0['monthly_accuracy'])}, CAGR "
               f"{fmt_pct(B0['cagr'])}, Sharpe {fmt_num(B0['sharpe_ann'])}, "
               f"MaxDD {fmt_pct(B0['max_dd'])}")
    rep.append(f"- **B1 QQQ buy&hold**: CAGR {fmt_pct(B1['cagr'])}, Sharpe "
               f"{fmt_num(B1['sharpe_ann'])}, MaxDD {fmt_pct(B1['max_dd'])}")
    rep.append(f"- **B2 systematic 63d momentum**: acc {fmt_pct(B2['monthly_accuracy'])}, "
               f"CAGR {fmt_pct(B2['cagr'])}, Sharpe {fmt_num(B2['sharpe_ann'])}, "
               f"MaxDD {fmt_pct(B2['max_dd'])}")
    rep.append("")

    # Main rotation table
    rep.append("## Rotation / Prediction Models")
    rep.append("")
    rep.append("| Exp | Approach | Acc | Top2 | WF CAGR | Sharpe | MaxDD | Δ CAGR vs B2 |")
    rep.append("|---|---|---|---|---|---|---|---|")
    def row(code, label, r):
        if r is None or "error" in r:
            return f"| {code} | {label} | — | — | — | — | — | FAILED |"
        acc = r.get("argmax_accuracy") or r.get("regime_accuracy") or r.get("inverted_accuracy")
        top2 = r.get("top2_accuracy")
        cagr = r.get("wf_cagr")
        sharpe = r.get("wf_sharpe")
        dd = r.get("wf_max_dd")
        delta = (cagr - B2["cagr"]) if cagr is not None else None
        return (f"| {code} | {label} | {fmt_pct(acc)} | {fmt_pct(top2)} | "
                f"{fmt_pct(cagr)} | {fmt_num(sharpe)} | {fmt_pct(dd)} | "
                f"{fmt_pct(delta) if delta is not None else 'n/a'} |")

    rows = [
        ("B2", "systematic 63d momentum", {"argmax_accuracy": B2["monthly_accuracy"],
                                            "wf_cagr": B2["cagr"], "wf_sharpe": B2["sharpe_ann"],
                                            "wf_max_dd": B2["max_dd"]}),
        ("B0", "random",                  {"argmax_accuracy": B0["monthly_accuracy"],
                                            "wf_cagr": B0["cagr"], "wf_sharpe": B0["sharpe_ann"],
                                            "wf_max_dd": B0["max_dd"]}),
        ("EA1", "regime classifier → ETF map",       EXPS["EA1"]),
        ("EA2", "leadership persistence (binary)",   EXPS["EA2"]),
        ("EA3", "HistGB CORE fwd42 regression",      EXPS["EA3"]),
        ("EA4", "HistGB CORE fwd63 regression",      EXPS["EA4"]),
        ("EB1", "large HistGB EXTENDED T2",          EXPS["EB1"]),
        ("EB2", "MLP small (128,64) CORE T2",        EXPS["EB2"]),
        ("EB3", "MLP big (256,128,64) EXT T2",       EXPS["EB3"]),
        ("EB4", "deep HistGB ALL features T2",       EXPS["EB4"]),
        ("EC1", "specialist team (5 models + rules)", EXPS["EC1"]),
        ("EC2", "stacked meta-learner",              EXPS["EC2"]),
        ("ED1", "k-NN similarity",                    EXPS["ED1"]),
        ("ED2", "contrarian (invert E03)",           EXPS["ED2"]),
        ("ED3", "signal disagreement heuristic",     EXPS["ED3"]),
        ("ED4", "LSTM temporal overlay",             EXPS["ED4"]),
        ("ED5", "dispersion predictor + overlay",    EXPS["ED5"]),
        ("ED6", "ensemble of all rotation models",   EXPS["ED6"]),
    ]
    for code, label, r in rows:
        rep.append(row(code, label, r))
    rep.append("")

    # Risk/protection-focused table
    rep.append("## Risk Signal Experiments")
    rep.append("")
    rep.append("| Exp | Metric | Value | Notes |")
    rep.append("|---|---|---|---|")
    if EXPS["EA5"] and "error" not in EXPS["EA5"]:
        r = EXPS["EA5"]
        rep.append(f"| EA5 | F1 / AUC | {fmt_num(r.get('f1'),'.3f')} / "
                   f"{fmt_num(r.get('auc'),'.3f')} | "
                   f"overlay CAGR {fmt_pct(r.get('overlay_cagr'))} vs weekly sys "
                   f"{fmt_pct(r.get('sys_weekly_cagr'))} |")
    if EXPS["ED5"] and "error" not in EXPS["ED5"]:
        r = EXPS["ED5"]
        rep.append(f"| ED5 | pred-vs-actual dispersion corr | "
                   f"{fmt_num(r.get('pred_vs_actual_corr'),'.3f')} | "
                   f"overlay CAGR {fmt_pct(r.get('wf_cagr'))}, "
                   f"MaxDD {fmt_pct(r.get('wf_max_dd'))} |")
    if EXPS["ED4"] and "error" not in EXPS["ED4"]:
        r = EXPS["ED4"]
        rep.append(f"| ED4 | pred-avg sign accuracy | "
                   f"{fmt_num(r.get('sign_accuracy'),'.3f')} | "
                   f"corr {fmt_num(r.get('pred_vs_actual_corr'),'.3f')} |")
    rep.append("")

    # Annual returns top 3
    ranked = []
    for code, label, r in rows:
        if r is None or "error" in r:
            continue
        cagr = r.get("wf_cagr")
        if cagr is None or cagr != cagr:
            continue
        if code in ("B0", "B2"):
            continue
        ranked.append((code, label, r))
    ranked.sort(key=lambda t: t[2].get("wf_cagr", -1), reverse=True)
    top3 = ranked[:3]

    rep.append("## Annual Returns — Top 3 Models vs B2")
    rep.append("")
    years = set()
    for _, _, r in top3:
        ar = r.get("annual_returns", {}) or {}
        years.update(ar.keys())
    years = sorted(years, key=lambda y: int(y))
    header = "| Year | " + " | ".join(t[0] for t in top3) + " | B2 ref |"
    sep = "|---" * (len(top3) + 2) + "|"
    rep.append(header)
    rep.append(sep)
    for y in years:
        cells = []
        for _, _, r in top3:
            ar = r.get("annual_returns", {}) or {}
            cells.append(fmt_pct(ar.get(y) if ar.get(y) is not None else float("nan")))
        rep.append(f"| {y} | " + " | ".join(cells) + " | — |")
    rep.append("")
    rep.append(f"Top 3 legend: " + "; ".join(f"**{c}** = {l}" for c, l, _ in top3))
    rep.append("")

    # Q&A
    rep.append("## Q&A")
    rep.append("")
    best_cagr = max(ranked, key=lambda t: t[2].get("wf_cagr", -1)) if ranked else None
    best_sharpe = max(ranked, key=lambda t: t[2].get("wf_sharpe") or -1) if ranked else None
    best_dd = None
    for _, _, r in ranked:
        dd = r.get("wf_max_dd")
        cg = r.get("wf_cagr")
        if dd is None or cg is None:
            continue
        if cg > 0.17 and (dd - B2["max_dd"]) > 0.05:  # DD reduced by >5pp
            if best_dd is None or dd > best_dd[2]["wf_max_dd"]:
                best_dd = (_, _, r)  # placeholder
    # recompute properly
    best_dd = None
    for code, label, r in ranked:
        dd = r.get("wf_max_dd"); cg = r.get("wf_cagr")
        if dd is None or cg is None:
            continue
        if cg > 0.17 and (dd - B2["max_dd"]) > 0.05:
            if best_dd is None or dd > best_dd[2]["wf_max_dd"]:
                best_dd = (code, label, r)

    if best_cagr:
        c, l, r = best_cagr
        gap = r["wf_cagr"] - B2["cagr"]
        rep.append(f"**Q1 (any approach beat B2 in WF CAGR?):** Best = **{c}** ({l}) "
                   f"CAGR {fmt_pct(r['wf_cagr'])} vs B2 {fmt_pct(B2['cagr'])} "
                   f"(Δ {fmt_pct(gap)}). "
                   f"{'YES' if gap > 0.0 else 'NO'}.")
    else:
        rep.append("**Q1:** No valid rotation results available.")

    if best_dd:
        c, l, r = best_dd
        rep.append(f"**Q2 (reduce MaxDD >5pp with CAGR >17%?):** **{c}** ({l}) "
                   f"MaxDD {fmt_pct(r['wf_max_dd'])} (B2 {fmt_pct(B2['max_dd'])}), "
                   f"CAGR {fmt_pct(r['wf_cagr'])}. YES.")
    else:
        rep.append(f"**Q2 (reduce MaxDD >5pp with CAGR >17%?):** NO. No approach met "
                   f"both thresholds.")

    # Block-level summary
    def block_best(prefix):
        items = [(c, l, r) for c, l, r in ranked if c.startswith(prefix)]
        if not items:
            return None
        return max(items, key=lambda t: t[2].get("wf_cagr", -1))
    blocks = {
        "A": block_best("EA"),
        "B": block_best("EB"),
        "C": block_best("EC"),
        "D": block_best("ED"),
    }
    block_lines = []
    for b, best in blocks.items():
        if best is None:
            block_lines.append(f"  - Block {b}: no results")
        else:
            c, l, r = best
            block_lines.append(f"  - Block {b} best = **{c}** ({l}) CAGR {fmt_pct(r['wf_cagr'])} "
                               f"Sharpe {fmt_num(r.get('wf_sharpe'))}")
    rep.append("**Q3 (which BLOCK showed most promise?):**")
    rep.extend(block_lines)

    # Specialist detail
    if EXPS["EC1"] and "error" not in EXPS["EC1"]:
        sp = EXPS["EC1"].get("specialist_perf", {})
        rep.append(f"**Q4 (specialists show individual skill?):** "
                   f"M1 regime fold acc = "
                   f"{fmt_pct(sp.get('M1_regime_fold_acc'))}, "
                   f"M3 momentum fold acc = {fmt_pct(sp.get('M3_momentum_fold_acc'))}. "
                   f"Team combined CAGR = {fmt_pct(EXPS['EC1'].get('wf_cagr'))}.")

    # Contrarian
    if EXPS["ED2"] and "error" not in EXPS["ED2"]:
        r = EXPS["ED2"]
        rep.append(f"**Q5 (contrarian inversion > random?):** inverted acc = "
                   f"{fmt_pct(r.get('inverted_accuracy'))} vs random "
                   f"{fmt_pct(B0['monthly_accuracy'])}. "
                   f"Original E03 = {fmt_pct(r.get('original_e03_accuracy'))}.")

    # Dispersion
    if EXPS["ED5"] and "error" not in EXPS["ED5"]:
        r = EXPS["ED5"]
        rep.append(f"**Q6 (dispersion prediction works?):** pred-vs-actual corr = "
                   f"{fmt_num(r.get('pred_vs_actual_corr'),'.3f')}. Overlay CAGR "
                   f"{fmt_pct(r.get('wf_cagr'))}.")
    rep.append("")

    (ROOT / "results/TIER1B_REPORT.md").write_text("\n".join(rep), encoding="utf-8")
    print("wrote TIER1B_REPORT.md")

    # Verdict
    verdict_lines = []
    beat_b2_cagr = best_cagr and best_cagr[2]["wf_cagr"] > B2["cagr"]
    beat_b2_sharpe = best_sharpe and (best_sharpe[2].get("wf_sharpe") or -1) > B2["sharpe_ann"]
    dd_value = best_dd is not None

    if beat_b2_cagr:
        c, l, r = best_cagr
        verdict = "PROCEED_TIER2_FOCUSED"
        verdict_lines.append(
            f"Best model **{c}** ({l}) achieves WF CAGR {fmt_pct(r['wf_cagr'])} "
            f"vs B2 {fmt_pct(B2['cagr'])}. Proceed to Tier 2 focused on this approach.")
    elif dd_value:
        c, l, r = best_dd
        verdict = "PROCEED_DRAWDOWN_OVERLAY"
        verdict_lines.append(
            f"No rotation model beats B2 CAGR, but **{c}** ({l}) reduces MaxDD to "
            f"{fmt_pct(r['wf_max_dd'])} (B2 {fmt_pct(B2['max_dd'])}) while keeping "
            f"CAGR {fmt_pct(r['wf_cagr'])}. Proceed to integration as a drawdown overlay.")
    else:
        verdict = "STOP"
        verdict_lines.append(
            f"Across Blocks A–D ({len([r for _,_,r in ranked])} valid experiments), "
            f"no approach beats B2 meaningfully on CAGR, Sharpe, or drawdown. "
            f"The systematic 63d momentum strategy stands alone at this monthly "
            f"frequency. Move to Phase 6 rules-based improvements.")

    # Supporting numbers
    verdict_lines.append("")
    verdict_lines.append("## Supporting numbers")
    verdict_lines.append("")
    verdict_lines.append(f"- B2 (systematic): CAGR {fmt_pct(B2['cagr'])}, Sharpe "
                         f"{fmt_num(B2['sharpe_ann'])}, MaxDD {fmt_pct(B2['max_dd'])}")
    for code, label, r in ranked[:8]:
        verdict_lines.append(
            f"- {code} ({label}): CAGR {fmt_pct(r.get('wf_cagr'))}, "
            f"Sharpe {fmt_num(r.get('wf_sharpe'))}, MaxDD {fmt_pct(r.get('wf_max_dd'))}")

    (ROOT / "results/TIER1B_VERDICT.md").write_text(
        f"# TIER 1B VERDICT: {verdict}\n\n" + "\n".join(verdict_lines) + "\n",
        encoding="utf-8",
    )
    print("wrote TIER1B_VERDICT.md")
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
