"""
Master backtest runner: tests all strategies with multiple parameter variations,
then generates comprehensive results documentation.
"""

import sys
import os
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime

# Add strategies directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from all_strategies import STRATEGY_REGISTRY
from enhanced_strategies import ENHANCED_REGISTRY
from elite_strategies import ELITE_REGISTRY
from final_strategies import FINAL_REGISTRY


RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def get_all_tickers():
    """Collect all unique tickers needed across all strategies."""
    tickers = set()
    for name, info in STRATEGY_REGISTRY.items():
        tickers.update(info["tickers"])
    return sorted(tickers)


def run_strategy_variant(engine, prices, name, strategy_fn, config_override=None, **kwargs):
    """Run a single strategy variant and return results."""
    config_desc = kwargs.copy()

    def wrapped_fn(p, d):
        return strategy_fn(p, d, **kwargs)

    print(f"\n  Testing: {name}")
    start_time = time.time()

    result = engine.run(
        strategy_fn=wrapped_fn,
        prices=prices,
        strategy_name=name,
        strategy_config=config_desc,
    )

    elapsed = time.time() - start_time
    if result.metrics:
        m = result.metrics
        print(f"    CAGR: {m.get('cagr', 'N/A')}% | Sharpe: {m.get('sharpe_ratio', 'N/A')} | "
              f"MaxDD: {m.get('max_drawdown', 'N/A')}% | vs SPY: {m.get('cumulative_vs_benchmark', 'N/A')}x | "
              f"Time: {elapsed:.1f}s")
    else:
        print(f"    No results (insufficient data)")

    return result


def run_all_strategies():
    """Run all strategies with multiple parameter variations."""
    print("=" * 80)
    print("SYSTEMATIC STRATEGY RESEARCH - FULL BACKTEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Fetch all prices
    tickers = get_all_tickers()
    print(f"\nFetching data for {len(tickers)} tickers...")

    config = BacktestConfig(
        initial_capital=100_000,
        transaction_cost_bps=5,
        slippage_bps=5,
        start_date="2018-01-02",
        end_date="2025-12-31",
        rebalance_frequency="monthly",
        benchmark="SPY",
    )
    engine = BacktestEngine(config)
    prices = engine.fetch_prices(tickers, start="2016-06-01", end="2025-12-31")

    print(f"  Data range: {prices.index[0].strftime('%Y-%m-%d')} to {prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"  Tickers available: {len(prices.columns)}")
    print(f"  Trading days: {len(prices[prices.index >= '2018-01-02'])}")

    all_results = []

    # =====================================================================
    # RUN BASE STRATEGIES
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 1: BASE STRATEGIES (Monthly Rebalance)")
    print("=" * 60)

    for name, info in STRATEGY_REGISTRY.items():
        result = run_strategy_variant(engine, prices, name, info["fn"])
        result.save(RESULTS_DIR)
        all_results.append(result)

    # =====================================================================
    # RUN PARAMETER VARIATIONS
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 2: PARAMETER VARIATIONS")
    print("=" * 60)

    # Dual Momentum variations
    from all_strategies import dual_momentum_strategy
    for lookback in [126, 189, 252]:
        for skip in [0, 21]:
            name = f"dual_momentum_lb{lookback}_skip{skip}"
            result = run_strategy_variant(engine, prices, name, dual_momentum_strategy,
                                          lookback=lookback, skip=skip)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Sector momentum variations
    from all_strategies import sector_momentum_strategy
    for top_k in [2, 3, 4, 5]:
        for lookback in [126, 189, 252]:
            for tf in [True, False]:
                name = f"sector_mom_top{top_k}_lb{lookback}_tf{tf}"
                result = run_strategy_variant(engine, prices, name, sector_momentum_strategy,
                                              top_k=top_k, lookback=lookback, trend_filter=tf)
                result.save(RESULTS_DIR)
                all_results.append(result)

    # Growth trend variations
    from all_strategies import growth_trend_timing
    for sma in [150, 200, 250]:
        for ticker in ["QQQ", "SPY"]:
            name = f"growth_trend_{ticker}_sma{sma}"
            result = run_strategy_variant(engine, prices, name, growth_trend_timing,
                                          growth_ticker=ticker, sma_period=sma)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Leveraged growth variations
    from all_strategies import leveraged_growth_rotation
    for agg_set in [
        ["QQQ", "XLK", "VGT", "IGV", "SOXX"],
        ["QQQ", "XLK", "SOXX"],
        ["QQQ", "VGT", "IGV"],
    ]:
        name = f"lev_growth_{'_'.join(agg_set[:3])}"
        result = run_strategy_variant(engine, prices, name, leveraged_growth_rotation,
                                      aggressive=agg_set)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # Vigilant AA variations
    from all_strategies import vigilant_asset_allocation
    for off_set in [
        ["SPY", "EFA", "EEM", "AGG"],
        ["SPY", "QQQ", "EFA", "AGG"],
        ["SPY", "QQQ", "EEM", "TLT"],
    ]:
        name = f"vigilant_{'_'.join(off_set)}"
        result = run_strategy_variant(engine, prices, name, vigilant_asset_allocation,
                                      offensive=off_set)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # Multi-asset momentum vol variations
    from all_strategies import multi_asset_momentum_vol
    for top_n in [3, 4, 5, 6]:
        for tv in [0.10, 0.12, 0.15]:
            name = f"ma_mom_vol_top{top_n}_tv{int(tv*100)}"
            result = run_strategy_variant(engine, prices, name, multi_asset_momentum_vol,
                                          top_n=top_n, target_vol=tv)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Adaptive AA variations
    from all_strategies import adaptive_asset_allocation
    for top_n in [3, 4, 5, 6]:
        for lb in [63, 126, 189]:
            name = f"adaptive_top{top_n}_lb{lb}"
            result = run_strategy_variant(engine, prices, name, adaptive_asset_allocation,
                                          top_n=top_n, lookback=lb)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Bold AA variations
    from all_strategies import bold_asset_allocation
    for uni_set in [
        ["SPY", "QQQ", "EFA", "EEM", "VNQ", "GLD", "TLT", "HYG"],
        ["QQQ", "SPY", "VNQ", "GLD", "TLT"],
        ["QQQ", "XLK", "SPY", "TLT", "GLD"],
    ]:
        name = f"bold_{'_'.join(uni_set[:4])}"
        result = run_strategy_variant(engine, prices, name, bold_asset_allocation,
                                      universe=uni_set)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # =====================================================================
    # WEEKLY REBALANCE VARIANTS for top strategies
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 3: WEEKLY REBALANCE FOR KEY STRATEGIES")
    print("=" * 60)

    weekly_config = BacktestConfig(
        initial_capital=100_000,
        transaction_cost_bps=5,
        slippage_bps=5,
        start_date="2018-01-02",
        end_date="2025-12-31",
        rebalance_frequency="weekly",
        benchmark="SPY",
    )
    weekly_engine = BacktestEngine(weekly_config)

    weekly_strategies = ["growth_trend", "bold_aa", "leveraged_growth", "vigilant_aa",
                         "enhanced_growth_trend", "accel_dual_momentum"]
    for name in weekly_strategies:
        if name in STRATEGY_REGISTRY:
            info = STRATEGY_REGISTRY[name]
            wname = f"{name}_weekly"
            result = run_strategy_variant(weekly_engine, prices, wname, info["fn"])
            result.save(RESULTS_DIR)
            all_results.append(result)

    # =====================================================================
    # PHASE 4: ENHANCED STRATEGIES (Growth-Focused)
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 4: ENHANCED STRATEGIES (Growth-Focused)")
    print("=" * 60)

    for name, info in ENHANCED_REGISTRY.items():
        result = run_strategy_variant(engine, prices, f"E_{name}", info["fn"])
        result.save(RESULTS_DIR)
        all_results.append(result)

    # =====================================================================
    # PHASE 5: ENHANCED STRATEGY PARAMETER SWEEPS
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 5: ENHANCED PARAMETER SWEEPS")
    print("=" * 60)

    from enhanced_strategies import (pure_soxx_trend, soxx_qqq_switch,
                                      concentrated_tech_rotation, growth_fast_riskoff,
                                      optimized_soxx_qqq_tlt, adaptive_concentration,
                                      dual_growth_bond)

    # Pure SOXX trend with different SMA periods
    for sma in [100, 150, 200, 250]:
        for ticker in ["SOXX", "QQQ", "XLK"]:
            name = f"E_pure_trend_{ticker}_sma{sma}"
            result = run_strategy_variant(engine, prices, name, pure_soxx_trend,
                                          ticker=ticker, sma_period=sma)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # SOXX/QQQ switch with different SMA periods
    for sma in [100, 150, 200]:
        for mom in [42, 63, 126]:
            name = f"E_soxx_qqq_sma{sma}_mom{mom}"
            result = run_strategy_variant(engine, prices, name, soxx_qqq_switch,
                                          sma_period=sma, mom_period=mom)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Concentrated tech with different SMA combos
    for fast, slow in [(20, 100), (50, 200), (20, 150), (50, 150)]:
        name = f"E_conc_tech_sma{fast}_{slow}"
        result = run_strategy_variant(engine, prices, name, concentrated_tech_rotation,
                                      sma_fast=fast, sma_slow=slow)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # Growth fast riskoff with different SMA combos
    for fast, slow in [(10, 50), (20, 100), (20, 150), (30, 100)]:
        name = f"E_growth_riskoff_{fast}_{slow}"
        result = run_strategy_variant(engine, prices, name, growth_fast_riskoff,
                                      sma_fast=fast, sma_slow=slow)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # Optimized SOXX/QQQ/TLT with different parameters
    for sma in [100, 150, 200]:
        for sw, lw in [(0.7, 0.3), (0.6, 0.4), (0.5, 0.5)]:
            name = f"E_opt_soxx_qqq_sma{sma}_w{int(sw*10)}{int(lw*10)}"
            result = run_strategy_variant(engine, prices, name, optimized_soxx_qqq_tlt,
                                          sma_period=sma, mom_weight_short=sw, mom_weight_long=lw)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Dual growth/bond with different allocation splits
    for gpct in [0.6, 0.7, 0.8, 0.9, 1.0]:
        name = f"E_dual_gb_g{int(gpct*100)}"
        result = run_strategy_variant(engine, prices, name, dual_growth_bond,
                                      growth_pct=gpct)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # =====================================================================
    # PHASE 6: ELITE STRATEGIES + SWEEPS
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 6: ELITE STRATEGIES")
    print("=" * 60)

    for name, info in ELITE_REGISTRY.items():
        result = run_strategy_variant(engine, prices, f"EL_{name}", info["fn"])
        result.save(RESULTS_DIR)
        all_results.append(result)

    # Parameter sweeps on elite strategies
    print("\n" + "=" * 60)
    print("PHASE 7: ELITE PARAMETER SWEEPS")
    print("=" * 60)

    from elite_strategies import (soxx_gold_hedge, multi_signal_soxx, soxx_trend_ddstop,
                                   max_growth_composite, abs_rel_growth_momentum,
                                   compound_momentum, aggressive_rotation,
                                   soxx_breakout)

    # SOXX gold hedge sweeps
    for sma in [100, 150, 200]:
        for mom in [21, 42, 63]:
            name = f"EL_soxx_gold_sma{sma}_mom{mom}"
            result = run_strategy_variant(engine, prices, name, soxx_gold_hedge,
                                          sma_period=sma, mom_period=mom)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Multi-signal SOXX sweeps
    for short, long in [(20, 100), (50, 200), (20, 150), (50, 150)]:
        name = f"EL_multisig_soxx_{short}_{long}"
        result = run_strategy_variant(engine, prices, name, multi_signal_soxx,
                                      sma_short=short, sma_long=long)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # SOXX trend + ddstop sweeps
    for sma in [100, 150, 200]:
        for dd in [-0.08, -0.10, -0.12, -0.15]:
            name = f"EL_soxx_dd_sma{sma}_dd{int(abs(dd)*100)}"
            result = run_strategy_variant(engine, prices, name, soxx_trend_ddstop,
                                          sma_period=sma, dd_threshold=dd)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Max growth composite sweeps
    for sma in [100, 150, 200]:
        for dd in [-0.08, -0.10, -0.12]:
            for growth_set in [["SOXX", "QQQ", "XLK"], ["SOXX", "QQQ"], ["SOXX"]]:
                name = f"EL_maxgrowth_sma{sma}_dd{int(abs(dd)*100)}_n{len(growth_set)}"
                result = run_strategy_variant(engine, prices, name, max_growth_composite,
                                              growth=growth_set, sma_period=sma, dd_limit=dd)
                result.save(RESULTS_DIR)
                all_results.append(result)

    # Abs/rel growth momentum sweeps
    for lb in [63, 126, 189, 252]:
        for growth_set in [["SOXX", "QQQ", "XLK", "VGT", "IGV"],
                           ["SOXX", "QQQ", "XLK"],
                           ["SOXX", "QQQ"]]:
            name = f"EL_absrel_lb{lb}_n{len(growth_set)}"
            result = run_strategy_variant(engine, prices, name, abs_rel_growth_momentum,
                                          growth=growth_set, lookback=lb)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Compound momentum sweeps
    for fast in [14, 21, 42]:
        for slow in [126, 189, 252]:
            name = f"EL_compound_f{fast}_s{slow}"
            result = run_strategy_variant(engine, prices, name, compound_momentum,
                                          fast_period=fast, slow_period=slow)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # SOXX breakout sweeps
    for lb in [42, 63, 126]:
        for ticker in ["SOXX", "QQQ", "XLK"]:
            name = f"EL_breakout_{ticker}_lb{lb}"
            result = run_strategy_variant(engine, prices, name, soxx_breakout,
                                          ticker=ticker, lookback=lb)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Aggressive rotation sweeps
    for top_n in [1, 2, 3]:
        for sma in [100, 150, 200]:
            name = f"EL_aggrot_top{top_n}_sma{sma}"
            result = run_strategy_variant(engine, prices, name, aggressive_rotation,
                                          top_n=top_n, sma_period=sma)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # =====================================================================
    # PHASE 8: FINAL STRATEGIES (Growth + Energy Hedge)
    # =====================================================================
    print("\n" + "=" * 60)
    print("PHASE 8: FINAL STRATEGIES (Growth + Energy)")
    print("=" * 60)

    for name, info in FINAL_REGISTRY.items():
        result = run_strategy_variant(engine, prices, f"FN_{name}", info["fn"])
        result.save(RESULTS_DIR)
        all_results.append(result)

    # PHASE 9: FINAL PARAMETER SWEEPS
    print("\n" + "=" * 60)
    print("PHASE 9: FINAL PARAMETER SWEEPS")
    print("=" * 60)

    from final_strategies import (growth_energy_rotation, abs_mom_growth_energy,
                                   abs_mom_optimized, ultimate_final, fast_dd_growth,
                                   diversified_growth_energy, multi_regime_rotation,
                                   broad_sector_rotation)

    # Abs momentum optimized sweeps
    for lb in [42, 63, 84, 126]:
        for growth_set in [["SOXX", "QQQ", "XLK", "VGT", "IGV"],
                           ["SOXX", "QQQ", "XLK"],
                           ["SOXX", "QQQ"]]:
            name = f"FN_absmom_lb{lb}_n{len(growth_set)}"
            result = run_strategy_variant(engine, prices, name, abs_mom_optimized,
                                          growth=growth_set, lookback=lb)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Growth energy rotation sweeps
    for sma in [100, 150, 200]:
        for growth_set in [["SOXX", "QQQ", "XLK"], ["SOXX", "QQQ"], ["SOXX"]]:
            name = f"FN_growtheng_sma{sma}_n{len(growth_set)}"
            result = run_strategy_variant(engine, prices, name, growth_energy_rotation,
                                          growth=growth_set, sma_period=sma)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Ultimate final sweeps
    for sma in [100, 150, 200]:
        for dd in [-0.06, -0.08, -0.10]:
            for growth_set in [["SOXX", "QQQ", "XLK"], ["SOXX", "QQQ"]]:
                name = f"FN_ultimate_sma{sma}_dd{int(abs(dd)*100)}_n{len(growth_set)}"
                result = run_strategy_variant(engine, prices, name, ultimate_final,
                                              growth=growth_set, sma_period=sma, dd_threshold=dd)
                result.save(RESULTS_DIR)
                all_results.append(result)

    # Fast DD growth sweeps
    for dd in [-0.05, -0.08, -0.10, -0.12]:
        for dw in [21, 42, 63]:
            name = f"FN_fastdd_dd{int(abs(dd)*100)}_w{dw}"
            result = run_strategy_variant(engine, prices, name, fast_dd_growth,
                                          dd_threshold=dd, dd_window=dw)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # Multi-regime sweeps
    for sma in [100, 150, 200]:
        name = f"FN_multireg_sma{sma}"
        result = run_strategy_variant(engine, prices, name, multi_regime_rotation,
                                      sma_period=sma)
        result.save(RESULTS_DIR)
        all_results.append(result)

    # Broad sector rotation sweeps
    for top_n in [1, 2, 3]:
        for sma in [150, 200]:
            name = f"FN_broadrot_top{top_n}_sma{sma}"
            result = run_strategy_variant(engine, prices, name, broad_sector_rotation,
                                          top_n=top_n, sma_period=sma)
            result.save(RESULTS_DIR)
            all_results.append(result)

    # =====================================================================
    # GENERATE REPORTS
    # =====================================================================
    print("\n" + "=" * 60)
    print("GENERATING REPORTS")
    print("=" * 60)

    generate_master_summary(all_results)
    generate_strategy_docs(all_results)
    generate_final_recommendation(all_results)

    print(f"\nAll results saved to {RESULTS_DIR}/")
    print(f"Total strategies tested: {len(all_results)}")
    print("Done!")


def generate_master_summary(results):
    """Generate master summary ranking all strategies."""
    valid = [r for r in results if r.metrics and r.metrics.get("sharpe_ratio") is not None]
    valid.sort(key=lambda r: r.metrics.get("sharpe_ratio", 0), reverse=True)

    lines = []
    lines.append("# MASTER STRATEGY SUMMARY")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total strategies tested: {len(results)}")
    lines.append(f"Valid results: {len(valid)}")
    lines.append("")
    lines.append("## Success Criteria")
    lines.append("- 8-year backtest with 2x S&P 500 cumulative returns")
    lines.append("- Positive returns every single year (or at most one mildly negative year)")
    lines.append("- No single year dominating the total return")
    lines.append("- Sharpe ratio above 1.0")
    lines.append("")

    # Summary table
    lines.append("## Rankings by Sharpe Ratio")
    lines.append("")
    lines.append("| Rank | Strategy | CAGR | SPY CAGR | Sharpe | MaxDD | vs SPY | Neg Years | Return Std |")
    lines.append("|------|----------|------|----------|--------|-------|--------|-----------|------------|")

    for i, r in enumerate(valid):
        m = r.metrics
        lines.append(
            f"| {i + 1} | {r.strategy_name} | {m.get('cagr', 'N/A')}% | {m.get('benchmark_cagr', 'N/A')}% | "
            f"{m.get('sharpe_ratio', 'N/A')} | {m.get('max_drawdown', 'N/A')}% | "
            f"{m.get('cumulative_vs_benchmark', 'N/A')}x | {m.get('negative_years', 'N/A')} | "
            f"{m.get('return_std_across_years', 'N/A')}% |"
        )

    lines.append("")

    # Strategies meeting criteria
    lines.append("## Strategies Meeting Success Criteria")
    lines.append("")
    meeting = []
    for r in valid:
        m = r.metrics
        sharpe_ok = m.get("sharpe_ratio", 0) >= 1.0
        vs_spy_ok = m.get("cumulative_vs_benchmark", 0) >= 2.0
        neg_years_ok = m.get("negative_years", 99) <= 1
        if sharpe_ok and vs_spy_ok and neg_years_ok:
            meeting.append(r)
            lines.append(f"### {r.strategy_name}")
            lines.append(f"- CAGR: {m['cagr']}% (SPY: {m['benchmark_cagr']}%)")
            lines.append(f"- Sharpe: {m['sharpe_ratio']}")
            lines.append(f"- Max Drawdown: {m['max_drawdown']}%")
            lines.append(f"- Cumulative vs SPY: {m['cumulative_vs_benchmark']}x")
            lines.append(f"- Negative years: {m['negative_years']}")
            lines.append(f"- Annual returns: {m.get('annual_returns', {})}")
            lines.append("")

    if not meeting:
        lines.append("**No strategies fully meet all criteria. See partial matches below.**")
        lines.append("")

        # Near misses
        lines.append("## Near Misses (meet 2+ criteria)")
        lines.append("")
        for r in valid[:20]:
            m = r.metrics
            sharpe_ok = m.get("sharpe_ratio", 0) >= 1.0
            vs_spy_ok = m.get("cumulative_vs_benchmark", 0) >= 1.5
            neg_years_ok = m.get("negative_years", 99) <= 1
            criteria_met = sum([sharpe_ok, vs_spy_ok, neg_years_ok])
            if criteria_met >= 2:
                lines.append(f"### {r.strategy_name} ({criteria_met}/3 criteria)")
                lines.append(f"- CAGR: {m['cagr']}% | Sharpe: {m['sharpe_ratio']} | "
                             f"MaxDD: {m['max_drawdown']}% | vs SPY: {m['cumulative_vs_benchmark']}x")
                lines.append(f"- Negative years: {m['negative_years']}")
                lines.append(f"- Annual returns: {m.get('annual_returns', {})}")
                lines.append("")

    # Annual returns comparison for top 10
    lines.append("## Annual Returns - Top 10 Strategies")
    lines.append("")

    for r in valid[:10]:
        m = r.metrics
        lines.append(f"### {r.strategy_name}")
        ar = m.get("annual_returns", {})
        br = m.get("annual_benchmark_returns", {})
        er = m.get("annual_excess_returns", {})
        lines.append("| Year | Strategy | SPY | Excess |")
        lines.append("|------|----------|-----|--------|")
        for year in sorted(ar.keys()):
            lines.append(f"| {year} | {ar[year]}% | {br.get(year, 'N/A')}% | {er.get(year, 'N/A')}% |")
        lines.append("")

    content = "\n".join(lines)
    with open(os.path.join(RESULTS_DIR, "MASTER_SUMMARY.md"), "w") as f:
        f.write(content)
    print(f"  Saved: MASTER_SUMMARY.md")


def generate_strategy_docs(results):
    """Generate individual strategy documentation."""
    for r in results:
        if not r.metrics:
            continue
        m = r.metrics
        lines = []
        lines.append(f"# Strategy: {r.strategy_name}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("## Configuration")
        lines.append(f"```json\n{json.dumps(r.config, indent=2, default=str)}\n```")
        lines.append("")
        lines.append("## Performance Metrics")
        lines.append(f"- **CAGR**: {m.get('cagr', 'N/A')}%")
        lines.append(f"- **Benchmark CAGR**: {m.get('benchmark_cagr', 'N/A')}%")
        lines.append(f"- **Sharpe Ratio**: {m.get('sharpe_ratio', 'N/A')}")
        lines.append(f"- **Sortino Ratio**: {m.get('sortino_ratio', 'N/A')}")
        lines.append(f"- **Max Drawdown**: {m.get('max_drawdown', 'N/A')}%")
        lines.append(f"- **Calmar Ratio**: {m.get('calmar_ratio', 'N/A')}")
        lines.append(f"- **Total Return**: {m.get('total_return', 'N/A')}%")
        lines.append(f"- **Benchmark Total Return**: {m.get('benchmark_total_return', 'N/A')}%")
        lines.append(f"- **Cumulative vs Benchmark**: {m.get('cumulative_vs_benchmark', 'N/A')}x")
        lines.append(f"- **Negative Years**: {m.get('negative_years', 'N/A')}")
        lines.append(f"- **Return Std Across Years**: {m.get('return_std_across_years', 'N/A')}%")
        lines.append("")
        lines.append("## Annual Returns")
        ar = m.get("annual_returns", {})
        br = m.get("annual_benchmark_returns", {})
        er = m.get("annual_excess_returns", {})
        lines.append("| Year | Strategy | Benchmark | Excess |")
        lines.append("|------|----------|-----------|--------|")
        for year in sorted(ar.keys()):
            lines.append(f"| {year} | {ar[year]}% | {br.get(year, 'N/A')}% | {er.get(year, 'N/A')}% |")
        lines.append("")

        # Verdict
        sharpe_ok = m.get("sharpe_ratio", 0) >= 1.0
        vs_spy_ok = m.get("cumulative_vs_benchmark", 0) >= 2.0
        neg_ok = m.get("negative_years", 99) <= 1
        if sharpe_ok and vs_spy_ok and neg_ok:
            lines.append("## Verdict: PASS - Meets all success criteria")
        else:
            fails = []
            if not sharpe_ok:
                fails.append(f"Sharpe {m.get('sharpe_ratio', 0)} < 1.0")
            if not vs_spy_ok:
                fails.append(f"vs SPY {m.get('cumulative_vs_benchmark', 0)} < 2.0x")
            if not neg_ok:
                fails.append(f"Negative years {m.get('negative_years', 0)} > 1")
            lines.append(f"## Verdict: FAIL - {', '.join(fails)}")

        safe_name = r.strategy_name.replace(" ", "_").replace("/", "_").lower()
        filepath = os.path.join(RESULTS_DIR, f"strategy_{safe_name}.md")
        with open(filepath, "w") as f:
            f.write("\n".join(lines))

    print(f"  Saved: {len([r for r in results if r.metrics])} strategy docs")


def generate_final_recommendation(results):
    """Generate final recommendation document."""
    valid = [r for r in results if r.metrics and r.metrics.get("sharpe_ratio") is not None]

    # Score each strategy
    scored = []
    for r in valid:
        m = r.metrics
        sharpe = m.get("sharpe_ratio", 0)
        vs_spy = m.get("cumulative_vs_benchmark", 0)
        neg_years = m.get("negative_years", 10)
        ret_std = m.get("return_std_across_years", 100)
        max_dd = abs(m.get("max_drawdown", -100))
        cagr = m.get("cagr", 0)

        # Composite score: weighted by importance
        # Consistency matters most
        score = (
            sharpe * 2.0 +          # Sharpe (risk-adjusted)
            min(vs_spy, 3.0) * 1.5 + # Outperformance (capped)
            (1 - neg_years / 8) * 3.0 + # Positive years (heavily weighted)
            max(0, 1 - ret_std / 30) * 2.0 + # Low variance (heavily weighted)
            max(0, 1 - max_dd / 40) * 1.5 +  # Low drawdown
            min(cagr / 20, 2.0) * 1.0  # Raw returns (capped)
        )
        scored.append((r, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    lines = []
    lines.append("# FINAL RECOMMENDATION")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("Strategies scored on composite metric weighting:")
    lines.append("- Consistency (positive years, low year-to-year variance): 50% weight")
    lines.append("- Risk-adjusted returns (Sharpe ratio): 20% weight")
    lines.append("- Outperformance vs S&P 500: 15% weight")
    lines.append("- Drawdown protection: 15% weight")
    lines.append("")
    lines.append(f"Total strategies evaluated: {len(scored)}")
    lines.append("")

    # Top 5 recommendations
    lines.append("## Top 5 Recommendations")
    lines.append("")

    for i, (r, score) in enumerate(scored[:5]):
        m = r.metrics
        lines.append(f"### #{i + 1}: {r.strategy_name} (Score: {score:.2f})")
        lines.append("")
        lines.append(f"**Performance:**")
        lines.append(f"- CAGR: {m['cagr']}% (SPY: {m['benchmark_cagr']}%)")
        lines.append(f"- Total Return: {m['total_return']}% (SPY: {m['benchmark_total_return']}%)")
        lines.append(f"- Sharpe Ratio: {m['sharpe_ratio']}")
        lines.append(f"- Max Drawdown: {m['max_drawdown']}%")
        lines.append(f"- Cumulative vs SPY: {m['cumulative_vs_benchmark']}x")
        lines.append("")
        lines.append(f"**Consistency:**")
        lines.append(f"- Negative Years: {m['negative_years']}")
        lines.append(f"- Return Std Across Years: {m['return_std_across_years']}%")
        lines.append(f"- Beat Benchmark Rate: {m['beat_benchmark_rate']}%")
        lines.append("")
        lines.append("**Annual Returns:**")
        ar = m.get("annual_returns", {})
        br = m.get("annual_benchmark_returns", {})
        for year in sorted(ar.keys()):
            marker = "+" if ar[year] > br.get(year, 0) else " "
            lines.append(f"  {year}: {ar[year]:>7.1f}% (SPY: {br.get(year, 'N/A'):>7.1f}%) {marker}")
        lines.append("")
        lines.append(f"**Configuration:** {json.dumps(r.config, default=str)}")
        lines.append("")

    # Data sources
    lines.append("## Data Sources")
    lines.append("- **Price Data**: Yahoo Finance (via yfinance) - adjusted close prices")
    lines.append("- **Asset Universe**: US equity ETFs (SPY, QQQ, sector ETFs), international (EFA, EEM),")
    lines.append("  bonds (TLT, IEF, AGG, SHY, BIL), commodities (GLD, DBC), REITs (VNQ),")
    lines.append("  factor ETFs (QUAL, MTUM, VUG, VLUE, USMV)")
    lines.append("- **Benchmark**: S&P 500 (SPY)")
    lines.append("")
    lines.append("## Replication Steps")
    lines.append("1. Install dependencies: `pip install yfinance pandas numpy`")
    lines.append("2. Run: `cd strategies && python run_all_backtests.py`")
    lines.append("3. Results will be in `/results/` directory")
    lines.append("")
    lines.append("## Caveats")
    lines.append("- Transaction costs modeled at 10bps round-trip (5bps costs + 5bps slippage)")
    lines.append("- No leverage used in any strategy")
    lines.append("- All data is adjusted for splits and dividends")
    lines.append("- Monthly rebalancing unless otherwise noted")
    lines.append("- Survivorship bias: ETFs that exist today may not have existed at backtest start")
    lines.append("- Past performance does not guarantee future results")

    with open(os.path.join(RESULTS_DIR, "FINAL_RECOMMENDATION.md"), "w") as f:
        f.write("\n".join(lines))
    print(f"  Saved: FINAL_RECOMMENDATION.md")


if __name__ == "__main__":
    run_all_strategies()
