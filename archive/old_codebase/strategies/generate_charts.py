"""Generate all analysis charts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import json
import glob
import os

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.dpi'] = 120
plt.rcParams['font.size'] = 10

# Load winning strategy data
eq = pd.read_csv(os.path.join(RESULTS, 'fn_abs_mom_optimized_equity.csv'), index_col=0, parse_dates=True)
eq.columns = ['equity']
bm = pd.read_csv(os.path.join(RESULTS, 'fn_abs_mom_optimized_benchmark.csv'), index_col=0, parse_dates=True)
bm.columns = ['benchmark']
weights = pd.read_csv(os.path.join(RESULTS, 'fn_abs_mom_optimized_weights.csv'), index_col=0, parse_dates=True)

with open(os.path.join(RESULTS, 'fn_abs_mom_optimized_metrics.json')) as f:
    metrics = json.load(f)['metrics']

eq_norm = eq['equity'] / eq['equity'].iloc[0] * 100
bm_norm = bm['benchmark'] / bm['benchmark'].iloc[0] * 100

# ========= FIGURE 1: Equity Curve + Drawdown + Rolling Returns =========
fig, axes = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [3, 1, 1]})

ax1 = axes[0]
ax1.plot(eq_norm.index, eq_norm.values, linewidth=2, color='#2196F3',
         label=f'Strategy ({metrics["cagr"]}% CAGR, {metrics["sharpe_ratio"]} Sharpe)')
ax1.plot(bm_norm.index, bm_norm.values, linewidth=1.5, color='#FF5722', alpha=0.7,
         label=f'S&P 500 ({metrics["benchmark_cagr"]}% CAGR)')
ax1.fill_between(eq_norm.index, eq_norm.values, bm_norm.values,
                  where=eq_norm.values >= bm_norm.values, alpha=0.15, color='green')
ax1.fill_between(eq_norm.index, eq_norm.values, bm_norm.values,
                  where=eq_norm.values < bm_norm.values, alpha=0.15, color='red')
ax1.set_ylabel('Growth of $100')
ax1.set_title('Abs Momentum Growth + Energy Rotation vs S&P 500 (2018-2025)',
              fontsize=14, fontweight='bold')
ax1.legend(loc='upper left', fontsize=9)
ax1.set_yscale('log')
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:.0f}'))
ax1.grid(True, alpha=0.3)

# Drawdown
cummax_s = eq['equity'].cummax()
dd_s = (eq['equity'] - cummax_s) / cummax_s * 100
cummax_b = bm['benchmark'].cummax()
dd_b = (bm['benchmark'] - cummax_b) / cummax_b * 100

ax2 = axes[1]
ax2.fill_between(dd_s.index, dd_s.values, 0, alpha=0.6, color='#2196F3', label='Strategy')
ax2.fill_between(dd_b.index, dd_b.values, 0, alpha=0.3, color='#FF5722', label='SPY')
ax2.set_ylabel('Drawdown %')
ax2.set_title('Drawdown Comparison', fontsize=11)
ax2.legend(loc='lower left', fontsize=8)
ax2.grid(True, alpha=0.3)

# Rolling 12-month return
strat_ret = eq['equity'].pct_change()
bm_ret = bm['benchmark'].pct_change()
roll_s = (1 + strat_ret).rolling(252).apply(lambda x: x.prod() - 1, raw=False) * 100
roll_b = (1 + bm_ret).rolling(252).apply(lambda x: x.prod() - 1, raw=False) * 100

ax3 = axes[2]
ax3.plot(roll_s.index, roll_s.values, linewidth=1.5, color='#2196F3', label='Strategy')
ax3.plot(roll_b.index, roll_b.values, linewidth=1, color='#FF5722', alpha=0.7, label='SPY')
ax3.axhline(y=0, color='black', linewidth=0.5)
ax3.set_ylabel('Rolling 12M Return %')
ax3.set_title('Rolling 12-Month Returns', fontsize=11)
ax3.legend(loc='upper left', fontsize=8)
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(RESULTS, 'chart_equity_curve.png'), bbox_inches='tight')
plt.close()
print('Saved: chart_equity_curve.png')

# ========= FIGURE 2: Annual Returns =========
fig, ax = plt.subplots(figsize=(12, 6))
years = sorted(metrics['annual_returns'].keys())
strat_annual = [metrics['annual_returns'][y] for y in years]
bm_annual = [metrics['annual_benchmark_returns'][y] for y in years]
x = np.arange(len(years))
width = 0.35

bars1 = ax.bar(x - width/2, strat_annual, width, label='Strategy', color='#2196F3', edgecolor='white')
bars2 = ax.bar(x + width/2, bm_annual, width, label='S&P 500', color='#FF5722', alpha=0.7, edgecolor='white')
ax.set_xlabel('Year')
ax.set_ylabel('Annual Return (%)')
ax.set_title('Annual Returns: Strategy vs S&P 500', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(years)
ax.legend()
ax.axhline(y=0, color='black', linewidth=0.5)

for bar in bars1:
    h = bar.get_height()
    ax.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width()/2, h),
                xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8)
for bar in bars2:
    h = bar.get_height()
    offset = 3 if h >= 0 else -12
    va = 'bottom' if h >= 0 else 'top'
    ax.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width()/2, h),
                xytext=(0, offset), textcoords='offset points', ha='center', va=va, fontsize=8)

plt.tight_layout()
plt.savefig(os.path.join(RESULTS, 'chart_annual_returns.png'), bbox_inches='tight')
plt.close()
print('Saved: chart_annual_returns.png')

# ========= FIGURE 3: Asset Allocation =========
fig, ax = plt.subplots(figsize=(14, 5))
w = weights.fillna(0)
cols = [c for c in w.columns if w[c].abs().max() > 0]
colors_map = {'SOXX': '#4CAF50', 'QQQ': '#2196F3', 'XLK': '#9C27B0', 'VGT': '#FF9800',
              'IGV': '#00BCD4', 'XLE': '#F44336', 'GLD': '#FFD700', 'SHY': '#607D8B',
              'IEF': '#795548', 'TLT': '#3F51B5'}
ax.stackplot(w.index, [w[c].values for c in cols],
             labels=cols, colors=[colors_map.get(c, '#999') for c in cols], alpha=0.8)
ax.set_ylabel('Weight')
ax.set_title('Asset Allocation Over Time (Winning Strategy)', fontsize=14, fontweight='bold')
ax.legend(loc='upper left', ncol=5, fontsize=8)
ax.set_ylim(0, 1.05)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS, 'chart_allocation.png'), bbox_inches='tight')
plt.close()
print('Saved: chart_allocation.png')

# ========= FIGURE 4: AI Model Analysis =========
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

ai_eq = pd.read_csv(os.path.join(DATA, 'backtest_results/equity_curve.csv'), parse_dates=['date'])
ai_preds = pd.read_csv(os.path.join(DATA, 'backtest_results/predictions.csv'))
ai_trades = pd.read_csv(os.path.join(DATA, 'backtest_results/trades.csv'))

# AI Equity curve
ax = axes[0, 0]
ax.plot(ai_eq['date'], ai_eq['equity'], linewidth=2, color='#4CAF50')
ax.axhline(y=100000, color='gray', linestyle='--', alpha=0.5)
ax.set_title('AI Model Equity Curve (Jan-Mar 2024)', fontsize=11, fontweight='bold')
ax.set_ylabel('Portfolio Value ($)')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
ax.grid(True, alpha=0.3)

# AI Prediction distribution
ax = axes[0, 1]
class_names = ['Strong\nSell', 'Sell', 'Hold', 'Buy', 'Strong\nBuy']
counts = ai_preds['pred_class'].value_counts().sort_index()
all_classes = pd.Series(0, index=range(5))
all_classes.update(counts)
bar_colors = ['#F44336', '#FF9800', '#9E9E9E', '#8BC34A', '#4CAF50']
bars = ax.bar(range(5), all_classes.values, color=bar_colors)
ax.set_xticks(range(5))
ax.set_xticklabels(class_names, fontsize=9)
ax.set_title('AI Prediction Distribution (5,250 preds)', fontsize=11, fontweight='bold')
ax.set_ylabel('Count')
for i, v in enumerate(all_classes.values):
    if v > 0:
        ax.text(i, v + 50, str(int(v)), ha='center', fontsize=9)

# AI Confidence
ax = axes[1, 0]
ax.hist(ai_preds['confidence'], bins=40, color='#2196F3', alpha=0.7, edgecolor='white')
ax.axvline(x=0.2, color='red', linestyle='--', linewidth=2, label='Random (0.20)')
ax.axvline(x=ai_preds['confidence'].mean(), color='green', linestyle='--', linewidth=2,
           label=f'Mean ({ai_preds["confidence"].mean():.3f})')
ax.set_title('AI Confidence Distribution', fontsize=11, fontweight='bold')
ax.set_xlabel('Max Class Probability')
ax.set_ylabel('Count')
ax.legend(fontsize=9)

# AI Trade PnL
ax = axes[1, 1]
wins = ai_trades[ai_trades['pnl_pct'] > 0]['pnl_pct'] * 100
losses = ai_trades[ai_trades['pnl_pct'] <= 0]['pnl_pct'] * 100
ax.hist(wins, bins=20, alpha=0.7, color='#4CAF50', label=f'Wins ({len(wins)})', edgecolor='white')
ax.hist(losses, bins=20, alpha=0.7, color='#F44336', label=f'Losses ({len(losses)})', edgecolor='white')
ax.axvline(x=0, color='black', linewidth=1)
wr = (ai_trades['pnl_pct'] > 0).mean() * 100
ax.set_title(f'Trade P&L Distribution ({wr:.0f}% win rate)', fontsize=11, fontweight='bold')
ax.set_xlabel('Trade Return (%)')
ax.set_ylabel('Count')
ax.legend()

plt.tight_layout()
plt.savefig(os.path.join(RESULTS, 'chart_ai_model.png'), bbox_inches='tight')
plt.close()
print('Saved: chart_ai_model.png')

# ========= FIGURE 5: Strategy Comparison =========
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

all_m = []
for f in glob.glob(os.path.join(RESULTS, '*_metrics.json')):
    with open(f) as fp:
        d = json.load(fp)
        if d.get('metrics') and d['metrics'].get('cagr', 0) > 3:
            all_m.append(d)
all_m.sort(key=lambda x: x['metrics']['cagr'], reverse=True)

# Sharpe vs CAGR
ax = axes[0, 0]
for d in all_m:
    m = d['metrics']
    name = d['strategy']
    c = '#4CAF50' if m.get('cumulative_vs_benchmark', 0) >= 2.0 else (
        '#F44336' if 'FN_' in name else '#2196F3' if 'EL_' in name else '#9E9E9E')
    s = 120 if m.get('cumulative_vs_benchmark', 0) >= 2.0 else 20
    ax.scatter(m['cagr'], m['sharpe_ratio'], s=s, c=c, alpha=0.5, edgecolors='white', linewidth=0.5)
for d in all_m:
    m = d['metrics']
    if m.get('cumulative_vs_benchmark', 0) >= 2.0:
        ax.annotate(d['strategy'][:25], (m['cagr'], m['sharpe_ratio']),
                    fontsize=7, fontweight='bold')
ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='Sharpe=1.0')
ax.axvline(x=14.2, color='red', linestyle='--', alpha=0.5, label='SPY CAGR')
ax.set_xlabel('CAGR (%)')
ax.set_ylabel('Sharpe Ratio')
ax.set_title('CAGR vs Sharpe: All 316 Strategies', fontsize=11, fontweight='bold')
ax.legend(fontsize=8)

# Return vs Drawdown
ax = axes[0, 1]
for d in all_m:
    m = d['metrics']
    c = '#4CAF50' if m.get('cumulative_vs_benchmark', 0) >= 2.0 else '#2196F3'
    s = 120 if m.get('cumulative_vs_benchmark', 0) >= 2.0 else 20
    ax.scatter(abs(m['max_drawdown']), m['cagr'], s=s, c=c, alpha=0.5, edgecolors='white')
ax.set_xlabel('Max Drawdown (%)')
ax.set_ylabel('CAGR (%)')
ax.set_title('Return vs Risk Trade-off', fontsize=11, fontweight='bold')

# Top 10 by CAGR
ax = axes[1, 0]
top10 = all_m[:10]
names = [d['strategy'][:30] for d in top10]
cagrs = [d['metrics']['cagr'] for d in top10]
c_bar = ['#4CAF50' if d['metrics'].get('cumulative_vs_benchmark', 0) >= 2.0 else '#2196F3' for d in top10]
ax.barh(range(len(names)), cagrs, color=c_bar, edgecolor='white')
ax.set_yticks(range(len(names)))
ax.set_yticklabels(names, fontsize=8)
ax.set_xlabel('CAGR (%)')
ax.set_title('Top 10 Strategies by CAGR', fontsize=11, fontweight='bold')
ax.axvline(x=14.2, color='red', linestyle='--', alpha=0.5, label='SPY')
ax.legend(fontsize=8)
ax.invert_yaxis()

# Consistency: neg years vs CAGR
ax = axes[1, 1]
for d in all_m:
    m = d['metrics']
    neg = m.get('negative_years', 0)
    c = '#4CAF50' if m.get('cumulative_vs_benchmark', 0) >= 2.0 else '#2196F3'
    s = 120 if m.get('cumulative_vs_benchmark', 0) >= 2.0 else 20
    ax.scatter(neg + np.random.uniform(-0.15, 0.15), m['cagr'], s=s, c=c, alpha=0.5, edgecolors='white')
ax.set_xlabel('Negative Years')
ax.set_ylabel('CAGR (%)')
ax.set_title('Consistency vs Returns (green=2x+ SPY)', fontsize=11, fontweight='bold')
ax.set_xticks(range(0, 5))

plt.tight_layout()
plt.savefig(os.path.join(RESULTS, 'chart_strategy_comparison.png'), bbox_inches='tight')
plt.close()
print('Saved: chart_strategy_comparison.png')

print('\nAll charts generated!')
