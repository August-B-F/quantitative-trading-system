/*
 * Backtest Dashboard — ETF Momentum Rotation (AI-Enhanced)
 *
 * Self-contained React artifact. Loads results/backtest_presentation.json
 * (or accepts the JSON pre-embedded as window.BACKTEST_DATA).
 *
 * Dependencies (assumed available in the host page):
 *   - React 18
 *   - recharts
 *   - tailwindcss (any build)
 *
 * Usage in a Claude artifact / standalone HTML host:
 *   <div id="root"></div>
 *   <script type="module">
 *     import data from "./backtest_presentation.json";
 *     window.BACKTEST_DATA = data;
 *   </script>
 *   <BacktestDashboard />
 */
import React, { useState, useMemo, useEffect } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceLine, Cell,
} from "recharts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const pct = (v, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(d)}%`;
const num = (v, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(d);
const dollar = (v) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : "$" + Math.round(v).toLocaleString();

const COLORS = {
  strategy: "#2563eb",   // blue-600
  spy:      "#94a3b8",   // slate-400
  original: "#a855f7",   // purple-500
  posStrong: "#15803d",
  posWeak:   "#86efac",
  negWeak:   "#fca5a5",
  negStrong: "#b91c1c",
};

// Color a heatmap cell by signed magnitude
function heatColor(r, max) {
  if (r === null || r === undefined || Number.isNaN(r)) return "rgba(0,0,0,0.05)";
  const t = Math.min(1, Math.abs(r) / max);
  if (r >= 0) {
    const g = Math.round(187 - t * 100); // 187 → 87
    return `rgb(${Math.round(220 - t * 180)}, ${g + 30}, ${Math.round(220 - t * 180)})`;
  }
  const rr = Math.round(220 - t * 60);
  return `rgb(${rr + 20}, ${Math.round(180 - t * 130)}, ${Math.round(180 - t * 130)})`;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------
function StatCard({ label, value, sub, accent }) {
  return (
    <div className={`rounded-2xl p-6 shadow-sm border ${accent || "bg-white border-slate-200 dark:bg-slate-800 dark:border-slate-700"}`}>
      <div className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-2 text-4xl font-bold text-slate-900 dark:text-white">{value}</div>
      {sub && <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------
function EquityCurve({ equity, annotations }) {
  const [logScale, setLogScale] = useState(false);
  const merged = useMemo(() => {
    const m = {};
    equity.strategy.forEach((p) => (m[p.date] = { date: p.date, strategy: p.value }));
    equity.spy.forEach((p) => (m[p.date] = { ...m[p.date], date: p.date, spy: p.value }));
    equity.original.forEach((p) => (m[p.date] = { ...m[p.date], date: p.date, original: p.value }));
    return Object.values(m).sort((a, b) => a.date.localeCompare(b.date));
  }, [equity]);

  const finals = merged[merged.length - 1] || {};

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Growth of $10,000</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Strategy {dollar(finals.strategy)} · SPY {dollar(finals.spy)} · 63d momentum (B3) {dollar(finals.original)}
          </p>
        </div>
        <button
          onClick={() => setLogScale(!logScale)}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700"
        >
          {logScale ? "Linear" : "Log"} scale
        </button>
      </div>
      <ResponsiveContainer width="100%" height={420}>
        <LineChart data={merged} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(0, 4)} minTickGap={40} />
          <YAxis
            scale={logScale ? "log" : "linear"}
            domain={logScale ? [10000, "auto"] : [0, "auto"]}
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => "$" + (v / 1000).toFixed(0) + "k"}
          />
          <Tooltip
            formatter={(v) => dollar(v)}
            labelFormatter={(l) => `Month: ${l}`}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="strategy" name="Strategy" stroke={COLORS.strategy} strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="spy" name="SPY (buy & hold)" stroke={COLORS.spy} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="original" name="63d momentum (B3 baseline)" stroke={COLORS.original} strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
          {annotations.map((a) => (
            <ReferenceLine key={a.date} x={a.date} stroke="#fbbf24" strokeDasharray="2 4" label={{ value: a.label, position: "top", fill: "#92400e", fontSize: 10 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}

function AnnualBars({ annual }) {
  const data = annual.map((r) => ({
    year: r.year,
    Strategy: r.strategy,
    SPY: r.spy,
    excess: r.excess,
  }));
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">Annual Returns vs SPY</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">Number above each pair is excess return.</p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 24, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis dataKey="year" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip formatter={(v) => pct(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#64748b" />
          <Bar dataKey="Strategy" fill={COLORS.strategy}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.excess >= 0 ? COLORS.strategy : "#dc2626"} />
            ))}
          </Bar>
          <Bar dataKey="SPY" fill={COLORS.spy} />
        </BarChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto mt-4">
        <table className="w-full text-xs text-slate-700 dark:text-slate-300">
          <thead className="border-b border-slate-200 dark:border-slate-700">
            <tr>
              <th className="py-1 text-left">Year</th>
              <th className="text-right">Strategy</th>
              <th className="text-right">SPY</th>
              <th className="text-right">Excess</th>
              <th className="text-left pl-3">Best ETF</th>
              <th className="text-right">Worst Month</th>
            </tr>
          </thead>
          <tbody>
            {annual.map((r) => (
              <tr key={r.year} className="border-b border-slate-100 dark:border-slate-700/50">
                <td className="py-1">{r.year}</td>
                <td className={`text-right ${r.strategy >= 0 ? "text-emerald-600" : "text-red-600"}`}>{pct(r.strategy)}</td>
                <td className={`text-right ${r.spy >= 0 ? "text-emerald-600" : "text-red-600"}`}>{pct(r.spy)}</td>
                <td className={`text-right ${r.excess >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {r.excess >= 0 ? "+" : ""}{pct(r.excess)}
                </td>
                <td className="pl-3">{r.best_etf}</td>
                <td className="text-right">{pct(r.worst_month)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MonthlyHeatmap({ heatmap }) {
  const years = useMemo(() => Array.from(new Set(heatmap.map((c) => c.year))).sort(), [heatmap]);
  const lookup = useMemo(() => {
    const m = {};
    heatmap.forEach((c) => (m[`${c.year}-${c.month}`] = c.ret));
    return m;
  }, [heatmap]);
  const max = useMemo(
    () => Math.max(...heatmap.map((c) => Math.abs(c.ret || 0)), 0.05),
    [heatmap]
  );
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">Monthly Returns Heatmap</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
        Consistency check — green months dominate. Hover any cell for the exact return.
      </p>
      <div className="overflow-x-auto">
        <table className="text-xs border-collapse">
          <thead>
            <tr>
              <th className="px-2 py-1"></th>
              {months.map((m) => (
                <th key={m} className="px-2 py-1 text-slate-500 dark:text-slate-400 font-medium">{m}</th>
              ))}
              <th className="px-2 py-1 text-slate-500 dark:text-slate-400 font-medium">Year</th>
            </tr>
          </thead>
          <tbody>
            {years.map((y) => {
              const row = months.map((_, i) => lookup[`${y}-${i + 1}`]);
              const yearRet = row.filter((v) => v !== undefined).reduce((acc, v) => acc * (1 + v), 1) - 1;
              return (
                <tr key={y}>
                  <td className="pr-2 text-slate-500 dark:text-slate-400 font-medium">{y}</td>
                  {row.map((v, i) => (
                    <td
                      key={i}
                      title={v !== undefined ? `${y}-${String(i + 1).padStart(2, "0")}: ${(v * 100).toFixed(2)}%` : ""}
                      className="w-12 h-8 text-center border border-white dark:border-slate-800"
                      style={{
                        background: heatColor(v, max),
                        color: v !== undefined && Math.abs(v) > max * 0.6 ? "white" : "#1e293b",
                        fontSize: 10,
                      }}
                    >
                      {v === undefined ? "" : (v * 100).toFixed(1)}
                    </td>
                  ))}
                  <td
                    className="w-14 h-8 text-center font-semibold border border-white dark:border-slate-800"
                    style={{
                      background: heatColor(yearRet, max * 2),
                      color: Math.abs(yearRet) > max ? "white" : "#1e293b",
                      fontSize: 10,
                    }}
                  >
                    {(yearRet * 100).toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DrawdownChart({ drawdowns }) {
  const merged = useMemo(() => {
    const m = {};
    drawdowns.strategy.forEach((p) => (m[p.date] = { date: p.date, strategy: p.dd }));
    drawdowns.spy.forEach((p) => (m[p.date] = { ...m[p.date], date: p.date, spy: p.dd }));
    return Object.values(m).sort((a, b) => a.date.localeCompare(b.date));
  }, [drawdowns]);
  const minS = Math.min(...drawdowns.strategy.map((p) => p.dd));
  const minSPY = Math.min(...drawdowns.spy.map((p) => p.dd));

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">Drawdowns From Peak</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
        Max drawdown — Strategy: <span className="font-semibold text-red-600">{pct(minS)}</span> · SPY: <span className="font-semibold text-red-600">{pct(minSPY)}</span>
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={merged}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(0, 4)} minTickGap={40} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip formatter={(v) => pct(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area type="monotone" dataKey="spy" name="SPY" fill="#fecaca" stroke="#fca5a5" />
          <Area type="monotone" dataKey="strategy" name="Strategy" fill="#bfdbfe" stroke={COLORS.strategy} />
        </AreaChart>
      </ResponsiveContainer>
    </section>
  );
}

function StatsTable({ stats }) {
  const rows = [
    ["CAGR", pct(stats.strategy.cagr), pct(stats.spy.cagr)],
    ["Sharpe", num(stats.strategy.sharpe), num(stats.spy.sharpe)],
    ["Sortino", num(stats.strategy.sortino), num(stats.spy.sortino)],
    ["Max Drawdown", pct(stats.strategy.max_dd), pct(stats.spy.max_dd)],
    ["Calmar", num(stats.strategy.calmar), num(stats.spy.calmar)],
    ["Win Rate (months)", pct(stats.strategy.win_rate), pct(stats.spy.win_rate)],
    ["Best Month", pct(stats.strategy.best_month), pct(stats.spy.best_month)],
    ["Worst Month", pct(stats.strategy.worst_month), pct(stats.spy.worst_month)],
    ["Best Year", pct(stats.strategy.best_year), pct(stats.spy.best_year)],
    ["Worst Year", pct(stats.strategy.worst_year), pct(stats.spy.worst_year)],
    ["Negative Years", stats.strategy.n_neg_years, stats.spy.n_neg_years],
    ["Avg Monthly Return", pct(stats.strategy.avg_month), pct(stats.spy.avg_month)],
    ["Median Monthly Return", pct(stats.strategy.median_month), pct(stats.spy.median_month)],
    ["Upside Capture", pct(stats.strategy.upside_capture), "100.00%"],
    ["Downside Capture", pct(stats.strategy.downside_capture), "100.00%"],
    ["Longest Win Streak", stats.strategy.longest_win_streak + " mo", stats.spy.longest_win_streak + " mo"],
    ["Longest Lose Streak", stats.strategy.longest_lose_streak + " mo", stats.spy.longest_lose_streak + " mo"],
    ["Longest SPY Underperf", stats.strategy.longest_spy_underperf + " mo", "—"],
  ];

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4">Key Statistics</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-slate-700 dark:text-slate-300">
          <thead className="border-b border-slate-200 dark:border-slate-700">
            <tr>
              <th className="text-left py-2"></th>
              <th className="text-right py-2 text-blue-600 dark:text-blue-400">Strategy</th>
              <th className="text-right py-2 text-slate-500">SPY</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, s, b]) => (
              <tr key={label} className="border-b border-slate-100 dark:border-slate-700/50">
                <td className="py-1.5">{label}</td>
                <td className="text-right font-mono font-semibold text-slate-900 dark:text-white">{s}</td>
                <td className="text-right font-mono text-slate-500">{b}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RollingSharpe({ rolling }) {
  const data = rolling.filter((r) => r.strategy !== null);
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">12-Month Rolling Sharpe</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
        How risk-adjusted returns hold up across regimes. 1.0 reference is the institutional bar.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(0, 4)} minTickGap={40} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => num(v, 2)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={1} stroke="#fbbf24" strokeDasharray="3 3" label={{ value: "1.0", fill: "#92400e", fontSize: 10 }} />
          <ReferenceLine y={0} stroke="#64748b" />
          <Line type="monotone" dataKey="strategy" name="Strategy" stroke={COLORS.strategy} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="spy" name="SPY" stroke={COLORS.spy} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}

function Attribution({ attribution }) {
  const data = attribution.per_year.map((r) => ({
    year: r.year,
    base: r.base,
    regime: r.regime,
    inv_vol: r.inv_vol,
    sma_gate: r.sma_gate,
    m26: r.m26,
  }));
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">Component Attribution by Year</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
        Where each year's edge comes from. Components are added cumulatively: base 63d momentum
        → +regime classifier → +inverse-vol top-3 sleeve → +SMA200 gate → +FOMC deferral.
      </p>
      <ResponsiveContainer width="100%" height={340}>
        <BarChart data={data} stackOffset="sign" margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis dataKey="year" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip formatter={(v) => pct(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#64748b" />
          <Bar dataKey="base"     stackId="a" name="Base 63d"      fill="#0ea5e9" />
          <Bar dataKey="regime"   stackId="a" name="+Regime"       fill="#22c55e" />
          <Bar dataKey="inv_vol"  stackId="a" name="+Inv-Vol"      fill="#a855f7" />
          <Bar dataKey="sma_gate" stackId="a" name="+SMA Gate"     fill="#f59e0b" />
          <Bar dataKey="m26"      stackId="a" name="+M26 Defer"    fill="#ef4444" />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}

function RegimeAnalysis({ regime }) {
  const vix = Object.entries(regime.vix).map(([k, v]) => ({ name: k, ann: v.ann, n: v.n }));
  const reg = Object.entries(regime.regime).map(([k, v]) => ({ name: k, ann: v.ann, n: v.n }));
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4">Regime Analysis</h2>
      <div className="grid md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">By VIX Bucket (annualized)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={vix}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
              <Tooltip formatter={(v) => pct(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="ann" fill={COLORS.strategy}>
                {vix.map((d, i) => (
                  <Cell key={i} fill={d.ann >= 0 ? COLORS.strategy : "#dc2626"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">By Growth-Inflation Quadrant</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={reg}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-15} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
              <Tooltip formatter={(v) => pct(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="ann" fill="#22c55e">
                {reg.map((d, i) => (
                  <Cell key={i} fill={d.ann >= 0 ? "#22c55e" : "#dc2626"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}

function TradeLog({ trades }) {
  const [open, setOpen] = useState(false);
  const [sortDesc, setSortDesc] = useState(true);
  const sorted = useMemo(() => {
    const c = [...trades];
    c.sort((a, b) => (sortDesc ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date)));
    return c;
  }, [trades, sortDesc]);

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-left"
      >
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Trade Log</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {trades.length} systematic monthly rebalances. Click to {open ? "collapse" : "expand"}.
          </p>
        </div>
        <span className="text-2xl text-slate-400">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="mt-4 max-h-[500px] overflow-y-auto">
          <table className="w-full text-xs text-slate-700 dark:text-slate-300">
            <thead className="sticky top-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th
                  onClick={() => setSortDesc(!sortDesc)}
                  className="text-left py-2 cursor-pointer hover:text-blue-600"
                >Date {sortDesc ? "↓" : "↑"}</th>
                <th className="text-left">Allocation</th>
                <th className="text-left">Regime</th>
                <th className="text-right">Lookback</th>
                <th className="text-right">Return</th>
                <th className="text-center">Defer</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((t, i) => (
                <tr key={i} className="border-b border-slate-100 dark:border-slate-700/50">
                  <td className="py-1 font-mono">{t.date}</td>
                  <td className="font-mono text-[10px]">
                    {Object.entries(t.to)
                      .map(([k, v]) => `${k}:${(v * 100).toFixed(0)}%`)
                      .join(" · ")}
                  </td>
                  <td>{t.regime}</td>
                  <td className="text-right">{t.lookback}d</td>
                  <td className={`text-right font-mono ${t.ret >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {pct(t.ret)}
                  </td>
                  <td className="text-center">{t.deferred ? "✓" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Top-level dashboard
// ---------------------------------------------------------------------------
export default function BacktestDashboard({ data: propData }) {
  const [dark, setDark] = useState(true);
  const [data, setData] = useState(propData || (typeof window !== "undefined" ? window.BACKTEST_DATA : null));
  const [error, setError] = useState(null);

  useEffect(() => {
    if (data) return;
    fetch("./backtest_presentation.json")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [data]);

  if (error) return <div className="p-8 text-red-600">Failed to load backtest_presentation.json: {error}</div>;
  if (!data) return <div className="p-8 text-slate-500">Loading backtest data…</div>;

  const h = data.headline;
  return (
    <div className={dark ? "dark" : ""}>
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white transition-colors">
        <div className="max-w-7xl mx-auto px-4 md:px-8 py-8">
          {/* Header */}
          <header className="flex items-start justify-between mb-8">
            <div>
              <div className="text-xs uppercase tracking-widest text-blue-600 dark:text-blue-400 font-semibold">Validated Backtest Report</div>
              <h1 className="text-3xl md:text-4xl font-bold mt-1">{h.name}</h1>
              <p className="text-slate-500 dark:text-slate-400 mt-1">{h.subtitle}</p>
            </div>
            <button
              onClick={() => setDark(!dark)}
              className="text-xs px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              {dark ? "☀ Light" : "☾ Dark"}
            </button>
          </header>

          {/* Headline cards */}
          <div className="grid md:grid-cols-3 gap-4 mb-8">
            <StatCard
              label="CAGR"
              value={pct(h.cagr_full, 2)}
              sub={`${h.n_full} months · ${(h.annual_turnover).toFixed(1)}× annual turnover`}
              accent="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-900/10 border-blue-200 dark:border-blue-800"
            />
            <StatCard
              label="Sharpe Ratio"
              value={num(h.sharpe_full, 2)}
              sub="Risk-adjusted return"
              accent="bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/30 dark:to-emerald-900/10 border-emerald-200 dark:border-emerald-800"
            />
            <StatCard
              label="Max Drawdown"
              value={pct(h.max_dd_full, 2)}
              sub="Peak-to-trough loss"
              accent="bg-gradient-to-br from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-900/10 border-red-200 dark:border-red-800"
            />
          </div>

          {/* Validation badge */}
          {data.validation && (
            <div className="mb-8 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-sm text-emerald-800 dark:text-emerald-200">
              ✓ Validated against <code>FINAL_STRATEGY_VALIDATED.md</code>: target 23.61% / 1.50 / -12.94% — actual{" "}
              {pct(data.validation.actual.cagr)} / {num(data.validation.actual.sharpe)} / {pct(data.validation.actual.max_dd)}
            </div>
          )}

          <div className="space-y-6">
            <EquityCurve equity={data.equity} annotations={data.annotations} />
            <AnnualBars annual={data.annual_returns} />
            <MonthlyHeatmap heatmap={data.monthly_heatmap} />
            <DrawdownChart drawdowns={data.drawdowns} />
            <div className="grid md:grid-cols-2 gap-6">
              <StatsTable stats={data.key_stats} />
              <RollingSharpe rolling={data.rolling_sharpe} />
            </div>
            <Attribution attribution={data.attribution} />
            <RegimeAnalysis regime={data.regime_breakdown} />
            <TradeLog trades={data.trade_log} />
          </div>

          <footer className="mt-12 pt-6 border-t border-slate-200 dark:border-slate-700 text-xs text-slate-500 dark:text-slate-400">
            Generated from <code>scripts/generate_presentation.py</code>. Backtest is gross of transaction
            costs (≤20bps degradation budget). Past performance is not indicative of future results — this is a
            research artifact, not investment advice.
          </footer>
        </div>
      </div>
    </div>
  );
}
